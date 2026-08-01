"""Deterministic analysis pipeline orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.analysis.chunker import CodeChunkData, chunk_python_file
from app.analysis.entrypoints import detect_entry_point, extract_console_scripts
from app.analysis.graph_builder import (
    DependencyGraph,
    build_dependency_graph,
    compute_change_impact,
)
from app.analysis.metrics import classify_file, compute_importance
from app.analysis.module_resolver import ResolvedImport, build_module_map, resolve_import
from app.analysis.parser import ParseResult, parse_python_source, symbols_to_json
from app.analysis.scanner import ScanResult, scan_repository
from app.core.exceptions import NoPythonFilesError


@dataclass(slots=True)
class AnalyzedFileResult:
    path: str
    module_name: str | None
    category: str
    category_reasons: list[str]
    line_count: int
    estimated_complexity: int
    importance_score: float
    importance_reason: str
    incoming_count: int
    outgoing_count: int
    is_test: bool
    is_entry_point: bool
    entrypoint_confidence: str | None
    entrypoint_reasons: list[str]
    parse_status: str
    parse_warning: str | None
    docstring: str | None
    symbols: list[dict[str, Any]]
    external_imports: list[str]
    related_symbols: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AnalysisBundle:
    files: list[AnalyzedFileResult]
    edges: list[dict[str, Any]]
    chunks: list[CodeChunkData]
    statistics: dict[str, Any]
    deterministic_summary: dict[str, Any]
    warnings: list[str]
    dependency_graph: DependencyGraph
    file_index: dict[str, AnalyzedFileResult]
    readme_excerpt: str | None = None
    pyproject_text: str | None = None


def run_static_analysis(
    root: Path,
    *,
    max_python_files: int,
    max_single_file_bytes: int,
    max_extracted_files: int,
) -> AnalysisBundle:
    scan = scan_repository(
        root,
        max_python_files=max_python_files,
        max_single_file_bytes=max_single_file_bytes,
        max_extracted_files=max_extracted_files,
    )
    if not scan.python_files:
        raise NoPythonFilesError()

    pyproject_text = _read_meta(scan, "pyproject.toml")
    readme_excerpt = _readme_excerpt(scan)
    script_targets = extract_console_scripts(pyproject_text)

    parses: dict[str, ParseResult] = {}
    for scanned in scan.python_files:
        source = scanned.absolute_path.read_text(encoding="utf-8", errors="replace")
        parses[scanned.path] = parse_python_source(scanned.path, source)

    module_map = build_module_map([p.path for p in scan.python_files])
    resolved: list[ResolvedImport] = []
    external_by_file: dict[str, list[str]] = {p.path: [] for p in scan.python_files}

    for path, parse in parses.items():
        for imp in parse.imports:
            for item in resolve_import(path, imp, module_map):
                resolved.append(item)
                if not item.is_internal and item.imported_module:
                    external_by_file[path].append(item.imported_module)

    dep_graph = build_dependency_graph([p.path for p in scan.python_files], resolved)

    files: list[AnalyzedFileResult] = []
    for scanned in scan.python_files:
        parse = parses[scanned.path]
        entry = detect_entry_point(scanned.path, parse, script_targets=script_targets)
        externals = sorted(set(external_by_file.get(scanned.path, [])))
        classification = classify_file(
            scanned.path,
            parse,
            is_entry_point=entry.is_entry_point,
            external_imports=externals,
        )
        incoming = dep_graph.incoming_count(scanned.path)
        outgoing = dep_graph.outgoing_count(scanned.path)
        importance, importance_reason = compute_importance(
            incoming=incoming,
            outgoing=outgoing,
            is_entry_point=entry.is_entry_point,
            symbol_count=len(parse.symbols),
            category=classification.category,
        )
        files.append(
            AnalyzedFileResult(
                path=scanned.path,
                module_name=module_map.path_to_module.get(scanned.path),
                category=classification.category,
                category_reasons=classification.reasons,
                line_count=parse.line_count,
                estimated_complexity=parse.estimated_complexity,
                importance_score=importance,
                importance_reason=importance_reason,
                incoming_count=incoming,
                outgoing_count=outgoing,
                is_test=classification.is_test,
                is_entry_point=entry.is_entry_point,
                entrypoint_confidence=entry.confidence,
                entrypoint_reasons=entry.reasons,
                parse_status=parse.parse_status,
                parse_warning=parse.parse_warning,
                docstring=parse.docstring,
                symbols=symbols_to_json(parse.symbols),
                external_imports=externals,
                related_symbols=entry.related_symbols,
            )
        )

    files.sort(key=lambda f: (-f.importance_score, f.path))
    file_index = {f.path: f for f in files}

    chunks: list[CodeChunkData] = []
    for path, parse in parses.items():
        chunks.extend(chunk_python_file(path, parse))

    edges = [
        {
            "source_path": e.source_path,
            "target_path": e.target_path,
            "imported_module": e.imported_module,
            "imported_names": e.imported_names,
            "line_number": e.line_number,
            "resolution_confidence": e.resolution_confidence,
        }
        for e in dep_graph.edges
    ]

    entry_points = [f for f in files if f.is_entry_point]
    important = [f for f in files if not f.is_test][:12]
    start_here = _build_start_here(files, entry_points)

    statistics = {
        "python_file_count": len(files),
        "lines_of_python": sum(f.line_count for f in files),
        "internal_dependency_edges": len(edges),
        "entry_point_count": len(entry_points),
        "test_file_count": sum(1 for f in files if f.is_test),
        "parse_warning_count": sum(1 for f in files if f.parse_status != "ok"),
        "chunk_count": len(chunks),
    }

    deterministic_summary = {
        "entry_points": [
            {
                "path": f.path,
                "confidence": f.entrypoint_confidence,
                "reasons": f.entrypoint_reasons,
                "category": f.category,
            }
            for f in entry_points
        ],
        "important_files": [
            {
                "path": f.path,
                "category": f.category,
                "importance_score": f.importance_score,
                "reason": f.importance_reason,
                "is_entry_point": f.is_entry_point,
            }
            for f in important
        ],
        "start_here": start_here,
        "category_counts": _category_counts(files),
    }

    warnings = list(scan.warnings)
    warnings.extend(f"{f.path}: {f.parse_warning}" for f in files if f.parse_warning)

    return AnalysisBundle(
        files=files,
        edges=edges,
        chunks=chunks,
        statistics=statistics,
        deterministic_summary=deterministic_summary,
        warnings=warnings,
        dependency_graph=dep_graph,
        file_index=file_index,
        readme_excerpt=readme_excerpt,
        pyproject_text=pyproject_text,
    )


def impact_for_file(bundle: AnalysisBundle, path: str) -> dict[str, Any]:
    entry_paths = {f.path for f in bundle.files if f.is_entry_point}
    test_paths = {f.path for f in bundle.files if f.is_test}
    impact = compute_change_impact(
        bundle.dependency_graph,
        path,
        entry_point_paths=entry_paths,
        test_paths=test_paths,
    )
    return {
        "selected_path": impact.selected_path,
        "direct_dependents": impact.direct_dependents,
        "second_level_dependents": impact.second_level_dependents,
        "related_tests": impact.related_tests,
        "affected_entry_points": impact.affected_entry_points,
        "representative_paths": [p.nodes for p in impact.representative_paths],
        "disclaimer": impact.disclaimer,
    }


def _build_start_here(
    files: list[AnalyzedFileResult],
    entry_points: list[AnalyzedFileResult],
) -> list[dict[str, Any]]:
    selected: list[AnalyzedFileResult] = []
    seen: set[str] = set()

    def add(file: AnalyzedFileResult) -> None:
        if file.path in seen or file.is_test:
            return
        seen.add(file.path)
        selected.append(file)

    for f in entry_points:
        add(f)
    for f in files:
        if f.category in {"API / Routes", "Services", "Core / Domain", "Configuration"}:
            add(f)
        if len(selected) >= 8:
            break
    for f in files:
        add(f)
        if len(selected) >= 8:
            break

    result = []
    for f in selected[:8]:
        why = (
            "Detected entry point — a natural place to begin."
            if f.is_entry_point
            else f.importance_reason
        )
        result.append(
            {
                "path": f.path,
                "category": f.category,
                "why": why,
                "is_entry_point": f.is_entry_point,
                "importance_score": f.importance_score,
            }
        )
    return result


def _category_counts(files: list[AnalyzedFileResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in files:
        counts[f.category] = counts.get(f.category, 0) + 1
    return counts


def _read_meta(scan: ScanResult, filename: str) -> str | None:
    for meta in scan.metadata_files:
        if meta.path.endswith(filename) or PureName(meta.path) == filename:
            try:
                return meta.absolute_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None
    return None


def PureName(path: str) -> str:
    return Path(path).name


def _readme_excerpt(scan: ScanResult) -> str | None:
    for name in ("README.md", "README.rst", "Readme.md"):
        text = _read_meta(scan, name)
        if text:
            return text[:4000]
    # case-insensitive search
    for meta in scan.metadata_files:
        if Path(meta.path).name.lower().startswith("readme"):
            try:
                return meta.absolute_path.read_text(encoding="utf-8", errors="replace")[:4000]
            except OSError:
                return None
    return None
