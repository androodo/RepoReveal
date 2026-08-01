"""Analysis API routes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import networkx as nx
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.answers import ask_repository, explain_file, suggest_questions
from app.analysis.graph_builder import DependencyGraph, GraphEdge, compute_change_impact
from app.api.dependencies import get_app_settings, get_db
from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.db.models import AnalyzedFile, DependencyEdge
from app.repositories import analyses as repo
from app.schemas.analyses import (
    AnalysisCreateRequest,
    AnalysisCreateResponse,
    AnalysisStatusResponse,
    AskRequest,
    AskResponse,
    ExplainResponse,
    FileDetailResponse,
    FileListItem,
    FileListResponse,
    GraphResponse,
    ImpactResponse,
)
from app.services import analyses as analyses_service

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("", response_model=AnalysisCreateResponse)
async def create_analysis(
    body: AnalysisCreateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> AnalysisCreateResponse:
    analysis, cached = await analyses_service.start_analysis(
        session,
        repository_url=body.repository_url,
        force=body.force,
        settings=settings,
    )
    if not cached and analysis.status == "queued":
        background_tasks.add_task(analyses_service.run_analysis_job, analysis.id)
    return AnalysisCreateResponse(
        analysis_id=analysis.id,
        status=analysis.status if cached else "queued",
        cached=cached,
    )


@router.get("/{analysis_id}", response_model=AnalysisStatusResponse)
async def get_analysis(
    analysis_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> AnalysisStatusResponse:
    payload = await analyses_service.get_analysis_payload(session, analysis_id)
    return AnalysisStatusResponse.model_validate(payload)


@router.get("/{analysis_id}/graph", response_model=GraphResponse)
async def get_graph(
    analysis_id: UUID,
    limit: int = Query(50, ge=10, le=200),
    include_tests: bool = False,
    entry_points_only: bool = False,
    category: str | None = None,
    search: str | None = None,
    session: AsyncSession = Depends(get_db),
) -> GraphResponse:
    data = await analyses_service.build_graph_response(
        session,
        analysis_id,
        limit=limit,
        include_tests=include_tests,
        entry_points_only=entry_points_only,
        category=category,
        search=search,
    )
    return GraphResponse.model_validate(data)


@router.get("/{analysis_id}/files", response_model=FileListResponse)
async def list_files(
    analysis_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: str | None = None,
    category: str | None = None,
    entry_points: bool | None = None,
    tests: bool | None = None,
    parse_status: str | None = None,
    sort: str = Query("importance"),
    order: str = Query("desc"),
    session: AsyncSession = Depends(get_db),
) -> FileListResponse:
    analysis = await repo.get_analysis(session, analysis_id)
    if analysis is None:
        raise NotFoundError("Analysis not found.")
    stmt = await repo.list_files_query(
        analysis_id,
        search=search,
        category=category,
        entry_points=entry_points,
        tests=tests,
        parse_status=parse_status,
        sort=sort,
        order=order,
    )
    total = await repo.count_files(session, stmt)
    rows = (
        (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size)))
        .scalars()
        .all()
    )
    items = []
    for row in rows:
        flags = []
        if row.is_entry_point:
            flags.append("entry")
        if row.is_test:
            flags.append("test")
        if row.parse_status != "ok":
            flags.append("parse-warning")
        items.append(
            FileListItem(
                id=row.id,
                path=row.path,
                module_name=row.module_name,
                category=row.category,
                line_count=row.line_count,
                estimated_complexity=row.estimated_complexity,
                importance_score=row.importance_score,
                incoming_count=row.incoming_count,
                outgoing_count=row.outgoing_count,
                is_test=row.is_test,
                is_entry_point=row.is_entry_point,
                parse_status=row.parse_status,
                flags=flags,
            )
        )
    return FileListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{analysis_id}/files/{file_id}", response_model=FileDetailResponse)
async def get_file_detail(
    analysis_id: UUID,
    file_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> FileDetailResponse:
    analysis = await repo.get_analysis(session, analysis_id)
    if analysis is None or analysis.repository is None:
        raise NotFoundError("Analysis not found.")
    file_row = await repo.get_file(session, analysis_id, file_id)
    if file_row is None:
        raise NotFoundError("File not found.")
    outgoing, incoming = await repo.get_edges_for_file(session, analysis_id, file_id)
    related = await repo.files_by_ids(
        session,
        [e.target_file_id for e in outgoing] + [e.source_file_id for e in incoming],
    )
    deps = [related[e.target_file_id].path for e in outgoing if e.target_file_id in related]
    importers = [related[e.source_file_id].path for e in incoming if e.source_file_id in related]
    github_url = f"{analysis.repository.github_url}/blob/{analysis.commit_sha}/{file_row.path}"
    return FileDetailResponse(
        id=file_row.id,
        path=file_row.path,
        module_name=file_row.module_name,
        category=file_row.category,
        category_reasons=file_row.category_reasons,
        line_count=file_row.line_count,
        estimated_complexity=file_row.estimated_complexity,
        importance_score=file_row.importance_score,
        incoming_count=file_row.incoming_count,
        outgoing_count=file_row.outgoing_count,
        is_test=file_row.is_test,
        is_entry_point=file_row.is_entry_point,
        entrypoint_confidence=file_row.entrypoint_confidence,
        entrypoint_reasons=file_row.entrypoint_reasons,
        parse_status=file_row.parse_status,
        parse_warning=file_row.parse_warning,
        docstring=file_row.docstring,
        symbols=file_row.symbols,
        external_imports=file_row.external_imports,
        internal_dependencies=deps,
        importers=importers,
        github_url=github_url,
    )


@router.get("/{analysis_id}/files/{file_id}/impact", response_model=ImpactResponse)
async def get_impact(
    analysis_id: UUID,
    file_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> ImpactResponse:
    analysis = await repo.get_analysis(session, analysis_id)
    if analysis is None or analysis.status != "completed":
        raise NotFoundError("Completed analysis not found.")
    file_row = await repo.get_file(session, analysis_id, file_id)
    if file_row is None:
        raise NotFoundError("File not found.")

    files = (
        (await session.execute(select(AnalyzedFile).where(AnalyzedFile.analysis_id == analysis_id)))
        .scalars()
        .all()
    )
    edges = (
        (
            await session.execute(
                select(DependencyEdge).where(DependencyEdge.analysis_id == analysis_id)
            )
        )
        .scalars()
        .all()
    )
    id_to_path = {f.id: f.path for f in files}
    graph: Any = nx.DiGraph()
    graph.add_nodes_from(id_to_path.values())
    graph_edges: list[GraphEdge] = []
    for edge in edges:
        source = id_to_path.get(edge.source_file_id)
        target = id_to_path.get(edge.target_file_id)
        if source and target:
            graph.add_edge(source, target)
            graph_edges.append(
                GraphEdge(
                    source_path=source,
                    target_path=target,
                    imported_module=edge.imported_module,
                    imported_names=edge.imported_names or [],
                    line_number=edge.line_number or 0,
                    resolution_confidence=edge.resolution_confidence,
                )
            )
    dep = DependencyGraph(graph=graph, edges=graph_edges)
    impact = compute_change_impact(
        dep,
        file_row.path,
        entry_point_paths={f.path for f in files if f.is_entry_point},
        test_paths={f.path for f in files if f.is_test},
    )
    return ImpactResponse(
        selected_path=impact.selected_path,
        direct_dependents=impact.direct_dependents,
        second_level_dependents=impact.second_level_dependents,
        related_tests=impact.related_tests,
        affected_entry_points=impact.affected_entry_points,
        representative_paths=[p.nodes for p in impact.representative_paths],
        disclaimer=impact.disclaimer,
    )


@router.post("/{analysis_id}/files/{file_id}/explain", response_model=ExplainResponse)
async def explain(
    analysis_id: UUID,
    file_id: UUID,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> ExplainResponse:
    result = await explain_file(session, analysis_id, file_id, settings=settings)
    return ExplainResponse.model_validate(result)


@router.post("/{analysis_id}/ask", response_model=AskResponse)
async def ask(
    analysis_id: UUID,
    body: AskRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> AskResponse:
    result = await ask_repository(session, analysis_id, body.question, settings=settings)
    return AskResponse.model_validate(result)


@router.get("/{analysis_id}/starter-questions")
async def starter_questions(
    analysis_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    analysis = await repo.get_analysis(session, analysis_id)
    if analysis is None:
        raise NotFoundError("Analysis not found.")
    return {"questions": suggest_questions(analysis)}


@router.post("/{analysis_id}/reanalyze", response_model=AnalysisCreateResponse)
async def reanalyze(
    analysis_id: UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
) -> AnalysisCreateResponse:
    analysis, cached = await analyses_service.reanalyze(session, analysis_id)
    if not cached and analysis.status == "queued":
        background_tasks.add_task(analyses_service.run_analysis_job, analysis.id)
    return AnalysisCreateResponse(
        analysis_id=analysis.id,
        status=analysis.status if cached else "queued",
        cached=cached,
    )
