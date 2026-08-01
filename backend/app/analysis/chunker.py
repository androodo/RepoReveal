"""AST-aware source chunking for retrieval."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from app.analysis.entrypoints import looks_like_secret
from app.analysis.parser import ParseResult

MAX_CHUNK_LINES = 120


@dataclass(slots=True)
class CodeChunkData:
    path: str
    chunk_type: str
    symbol_name: str | None
    line_start: int
    line_end: int
    content: str
    search_text: str


def chunk_python_file(path: str, parse: ParseResult) -> list[CodeChunkData]:
    if parse.parse_status != "ok" or not parse.source:
        return []
    if looks_like_secret(parse.source):
        return []

    lines = parse.source.splitlines()
    chunks: list[CodeChunkData] = []

    # Module overview
    overview_parts = []
    if parse.docstring:
        overview_parts.append(parse.docstring)
    import_lines = [imp.raw for imp in parse.imports[:40]]
    if import_lines:
        overview_parts.append("Imports:\n" + "\n".join(import_lines))
    symbol_names = [f"{s.kind}:{s.name}" for s in parse.symbols]
    if symbol_names:
        overview_parts.append("Symbols: " + ", ".join(symbol_names))
    overview = "\n\n".join(overview_parts).strip() or f"Module {path}"
    chunks.append(
        CodeChunkData(
            path=path,
            chunk_type="module_overview",
            symbol_name=None,
            line_start=1,
            line_end=min(len(lines), 40) if lines else 1,
            content=overview,
            search_text=f"{path}\n{overview}",
        )
    )

    if parse.tree is None or not isinstance(parse.tree, ast.Module):
        return chunks

    # Module-level non-def statements
    module_level_nodes = [
        n
        for n in parse.tree.body
        if not isinstance(
            n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)
        )
    ]
    if module_level_nodes:
        start = min(n.lineno for n in module_level_nodes)
        end = max(getattr(n, "end_lineno", n.lineno) or n.lineno for n in module_level_nodes)
        content = _slice_lines(lines, start, end)
        chunks.append(
            CodeChunkData(
                path=path,
                chunk_type="module_level",
                symbol_name=None,
                line_start=start,
                line_end=end,
                content=content,
                search_text=f"{path}\nmodule_level\n{content}",
            )
        )

    for node in parse.tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno
            end = getattr(node, "end_lineno", node.lineno) or node.lineno
            kind = (
                "class"
                if isinstance(node, ast.ClassDef)
                else "async_function"
                if isinstance(node, ast.AsyncFunctionDef)
                else "function"
            )
            chunks.extend(_windowed_chunks(path, kind, node.name, lines, start, end))

    return chunks


def _windowed_chunks(
    path: str,
    chunk_type: str,
    symbol_name: str,
    lines: list[str],
    start: int,
    end: int,
) -> list[CodeChunkData]:
    total = end - start + 1
    if total <= MAX_CHUNK_LINES:
        content = _slice_lines(lines, start, end)
        return [
            CodeChunkData(
                path=path,
                chunk_type=chunk_type,
                symbol_name=symbol_name,
                line_start=start,
                line_end=end,
                content=content,
                search_text=f"{path}\n{symbol_name}\n{content}",
            )
        ]

    result: list[CodeChunkData] = []
    cursor = start
    while cursor <= end:
        window_end = min(cursor + MAX_CHUNK_LINES - 1, end)
        content = _slice_lines(lines, cursor, window_end)
        result.append(
            CodeChunkData(
                path=path,
                chunk_type=chunk_type,
                symbol_name=symbol_name,
                line_start=cursor,
                line_end=window_end,
                content=content,
                search_text=f"{path}\n{symbol_name}\n{content}",
            )
        )
        cursor = window_end + 1
    return result


def _slice_lines(lines: list[str], start: int, end: int) -> str:
    return "\n".join(lines[start - 1 : end])
