"""AST-based Python parsing without executing code."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ImportInfo:
    module: str | None
    names: list[str]
    level: int
    line_number: int
    is_from: bool
    raw: str


@dataclass(slots=True)
class SymbolInfo:
    name: str
    kind: str  # function | async_function | class
    line_start: int
    line_end: int
    decorators: list[str] = field(default_factory=list)
    docstring: str | None = None


@dataclass(slots=True)
class ParseResult:
    path: str
    parse_status: str
    parse_warning: str | None = None
    docstring: str | None = None
    imports: list[ImportInfo] = field(default_factory=list)
    symbols: list[SymbolInfo] = field(default_factory=list)
    has_main_block: bool = False
    framework_hints: list[str] = field(default_factory=list)
    estimated_complexity: int = 0
    line_count: int = 0
    source: str = ""
    tree: ast.AST | None = None


def parse_python_source(path: str, source: str) -> ParseResult:
    line_count = source.count("\n") + (1 if source and not source.endswith("\n") else 0)
    result = ParseResult(path=path, parse_status="ok", line_count=line_count, source=source)
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        result.parse_status = "error"
        result.parse_warning = f"SyntaxError: {exc.msg} (line {exc.lineno})"
        return result

    result.tree = tree
    result.docstring = ast.get_docstring(tree)
    result.imports = _extract_imports(tree)
    result.symbols = _extract_symbols(tree)
    result.has_main_block = _has_main_block(tree)
    result.framework_hints = _detect_framework_hints(tree, source)
    result.estimated_complexity = estimate_complexity(tree)
    return result


def estimate_complexity(tree: ast.AST) -> int:
    """Lightweight structural complexity estimate (not cyclomatic complexity)."""
    score = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler)):
            score += 1
        elif isinstance(node, ast.BoolOp):
            score += max(0, len(node.values) - 1)
        elif isinstance(node, ast.Match):
            score += len(node.cases)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            score += sum(1 for gen in node.generators if gen.ifs)
            score += 1
        elif isinstance(node, ast.IfExp):
            score += 1
    return score


def _extract_imports(tree: ast.AST) -> list[ImportInfo]:
    imports: list[ImportInfo] = []
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    ImportInfo(
                        module=alias.name,
                        names=[alias.asname or alias.name.split(".")[-1]],
                        level=0,
                        line_number=node.lineno,
                        is_from=False,
                        raw=f"import {alias.name}",
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            names = [alias.asname or alias.name for alias in node.names]
            module = node.module
            imports.append(
                ImportInfo(
                    module=module,
                    names=names,
                    level=node.level or 0,
                    line_number=node.lineno,
                    is_from=True,
                    raw=f"from {'.' * (node.level or 0)}{module or ''} import {', '.join(n.name for n in node.names)}",
                )
            )
    return imports


def _extract_symbols(tree: ast.AST) -> list[SymbolInfo]:
    symbols: list[SymbolInfo] = []
    if not isinstance(tree, ast.Module):
        return symbols
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = (
                "class"
                if isinstance(node, ast.ClassDef)
                else "async_function"
                if isinstance(node, ast.AsyncFunctionDef)
                else "function"
            )
            symbols.append(
                SymbolInfo(
                    name=node.name,
                    kind=kind,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno) or node.lineno,
                    decorators=[_decorator_name(d) for d in node.decorator_list],
                    docstring=ast.get_docstring(node),
                )
            )
    return symbols


def _decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _decorator_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return type(node).__name__


def _has_main_block(tree: ast.AST) -> bool:
    if not isinstance(tree, ast.Module):
        return False
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value == "__main__"
        ):
            return True
    return False


def _detect_framework_hints(tree: ast.AST, source: str) -> list[str]:
    hints: list[str] = []
    text_checks = [
        ("FastAPI(", "fastapi_app"),
        ("Flask(", "flask_app"),
        ("Typer(", "typer_app"),
        ("uvicorn.run(", "uvicorn_run"),
        ("click.command", "click_command"),
        ("@click.command", "click_command"),
        ("django.core.management", "django_management"),
        ("get_asgi_application", "django_asgi"),
        ("get_wsgi_application", "django_wsgi"),
    ]
    for needle, hint in text_checks:
        if needle in source:
            hints.append(hint)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _decorator_name(node.func)
            if name.endswith("FastAPI"):
                hints.append("fastapi_app")
            elif name.endswith("Flask"):
                hints.append("flask_app")
            elif name.endswith("Typer"):
                hints.append("typer_app")
    # de-dupe preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for hint in hints:
        if hint not in seen:
            seen.add(hint)
            unique.append(hint)
    return unique


def symbols_to_json(symbols: list[SymbolInfo]) -> list[dict[str, Any]]:
    return [
        {
            "name": s.name,
            "kind": s.kind,
            "line_start": s.line_start,
            "line_end": s.line_end,
            "decorators": s.decorators,
            "docstring": s.docstring,
        }
        for s in symbols
    ]
