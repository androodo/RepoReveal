"""File-level dependency graph construction and change-impact traversal."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from app.analysis.module_resolver import ResolvedImport


@dataclass(slots=True)
class GraphEdge:
    source_path: str
    target_path: str
    imported_module: str
    imported_names: list[str]
    line_number: int
    resolution_confidence: str


@dataclass(slots=True)
class DependencyGraph:
    graph: Any
    edges: list[GraphEdge] = field(default_factory=list)

    def incoming_count(self, path: str) -> int:
        if path not in self.graph:
            return 0
        return int(self.graph.in_degree(path))

    def outgoing_count(self, path: str) -> int:
        if path not in self.graph:
            return 0
        return int(self.graph.out_degree(path))


def build_dependency_graph(
    file_paths: list[str],
    resolved_imports: list[ResolvedImport],
) -> DependencyGraph:
    graph: Any = nx.DiGraph()
    graph.add_nodes_from(file_paths)
    edges: list[GraphEdge] = []
    seen: set[tuple[str, str, str, int]] = set()

    for item in resolved_imports:
        if not item.is_internal or not item.target_path:
            continue
        if item.source_path == item.target_path:
            continue
        key = (item.source_path, item.target_path, item.imported_module, item.line_number)
        if key in seen:
            continue
        seen.add(key)
        edge = GraphEdge(
            source_path=item.source_path,
            target_path=item.target_path,
            imported_module=item.imported_module,
            imported_names=item.imported_names,
            line_number=item.line_number,
            resolution_confidence=item.confidence,
        )
        edges.append(edge)
        graph.add_edge(
            item.source_path,
            item.target_path,
            imported_module=item.imported_module,
            line_number=item.line_number,
        )

    return DependencyGraph(graph=graph, edges=edges)


@dataclass(slots=True)
class ImpactPath:
    nodes: list[str]


@dataclass(slots=True)
class ChangeImpact:
    selected_path: str
    direct_dependents: list[str]
    second_level_dependents: list[str]
    related_tests: list[str]
    affected_entry_points: list[str]
    representative_paths: list[ImpactPath]
    disclaimer: str = (
        "These files may be structurally affected because they depend on the selected module. "
        "This is not a guarantee of runtime impact."
    )


def compute_change_impact(
    dep_graph: DependencyGraph,
    selected_path: str,
    *,
    entry_point_paths: set[str],
    test_paths: set[str],
    max_depth: int = 2,
) -> ChangeImpact:
    """Traverse reverse dependency edges up to max_depth."""
    reverse = dep_graph.graph.reverse(copy=False)
    if selected_path not in reverse:
        return ChangeImpact(
            selected_path=selected_path,
            direct_dependents=[],
            second_level_dependents=[],
            related_tests=[],
            affected_entry_points=[],
            representative_paths=[],
        )

    direct = sorted(reverse.successors(selected_path))
    second: set[str] = set()
    for dep in direct:
        for nxt in reverse.successors(dep):
            if nxt != selected_path and nxt not in direct:
                second.add(nxt)
    second_sorted = sorted(second)

    affected = set(direct) | second
    related_tests = sorted(path for path in affected if path in test_paths)
    affected_entry_points = sorted(path for path in affected if path in entry_point_paths)

    paths: list[ImpactPath] = []
    for dep in direct[:8]:
        paths.append(ImpactPath(nodes=[selected_path, dep]))
        for nxt in list(reverse.successors(dep))[:2]:
            if nxt != selected_path:
                paths.append(ImpactPath(nodes=[selected_path, dep, nxt]))
        if len(paths) >= 12:
            break

    return ChangeImpact(
        selected_path=selected_path,
        direct_dependents=direct,
        second_level_dependents=second_sorted,
        related_tests=related_tests,
        affected_entry_points=affected_entry_points,
        representative_paths=paths,
    )


def graph_to_serializable(
    dep_graph: DependencyGraph,
    *,
    node_meta: dict[str, dict[str, Any]],
    limit: int,
    include_tests: bool,
    entry_points_only: bool,
    category: str | None,
    search: str | None,
) -> dict[str, Any]:
    """Select a bounded subgraph for visualization."""
    candidates = list(dep_graph.graph.nodes)
    filtered: list[str] = []
    search_l = (search or "").lower().strip()

    for path in candidates:
        meta = node_meta.get(path, {})
        if not include_tests and meta.get("is_test"):
            continue
        if entry_points_only and not meta.get("is_entry_point"):
            continue
        if category and meta.get("category") != category:
            continue
        if search_l and search_l not in path.lower():
            continue
        filtered.append(path)

    # Prefer entry points and important files, then expand neighbors
    ranked = sorted(
        filtered,
        key=lambda p: (
            0 if node_meta.get(p, {}).get("is_entry_point") else 1,
            -float(node_meta.get(p, {}).get("importance_score") or 0),
        ),
    )

    selected: set[str] = set()
    for path in ranked:
        if len(selected) >= limit:
            break
        selected.add(path)
        # add direct neighbors
        for nbr in list(dep_graph.graph.successors(path)) + list(
            dep_graph.graph.predecessors(path)
        ):
            meta = node_meta.get(nbr, {})
            if not include_tests and meta.get("is_test"):
                continue
            selected.add(nbr)
            if len(selected) >= limit:
                break

    nodes = []
    for path in sorted(selected):
        meta = node_meta.get(path, {})
        nodes.append({"id": path, "path": path, **meta})

    edges = []
    for edge in dep_graph.edges:
        if edge.source_path in selected and edge.target_path in selected:
            edges.append(
                {
                    "source": edge.source_path,
                    "target": edge.target_path,
                    "imported_module": edge.imported_module,
                    "line_number": edge.line_number,
                }
            )

    return {"nodes": nodes, "edges": edges, "truncated": len(selected) < len(filtered)}
