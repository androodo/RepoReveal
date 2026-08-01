"""Analysis orchestration service."""

from __future__ import annotations

import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ANALYZER_VERSION
from app.analysis.graph_builder import graph_to_serializable
from app.analysis.pipeline import run_static_analysis
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, NotFoundError
from app.db.models import Analysis, AnalyzedFile, CodeChunk, DependencyEdge
from app.db.session import AsyncSessionLocal
from app.repositories import analyses as repo
from app.services.archives import extract_archive
from app.services.github import GitHubClient
from app.services.github_urls import parse_github_url

logger = logging.getLogger(__name__)

STAGES = [
    ("fetching_repository", "Fetching repository", 5),
    ("downloading_source", "Downloading source", 15),
    ("scanning_files", "Scanning files", 30),
    ("parsing_python", "Parsing Python", 45),
    ("building_graph", "Building dependency graph", 60),
    ("creating_index", "Creating code index", 75),
    ("generating_overview", "Generating AI overview", 90),
    ("complete", "Complete", 100),
]


async def start_analysis(
    session: AsyncSession,
    *,
    repository_url: str,
    force: bool,
    settings: Settings | None = None,
) -> tuple[Analysis, bool]:
    settings = settings or get_settings()
    parsed = parse_github_url(repository_url)
    client = GitHubClient(settings)
    try:
        meta = await client.get_repository(parsed)
        commit = await client.resolve_commit(parsed, meta.default_branch)
    finally:
        await client.aclose()

    repository = await repo.get_or_create_repository(
        session,
        owner=meta.owner,
        name=meta.name,
        full_name=meta.full_name,
        github_url=meta.github_url,
        description=meta.description,
        default_branch=meta.default_branch,
        primary_language=meta.primary_language,
        stars=meta.stars,
        is_archived=meta.is_archived,
    )
    await session.flush()

    if not force:
        cached = await repo.get_cached_analysis(
            session, repository.id, commit.sha, ANALYZER_VERSION
        )
        if cached:
            return cached, True

    analysis = Analysis(
        id=uuid4(),
        repository_id=repository.id,
        commit_sha=commit.sha,
        status="queued",
        stage="queued",
        progress=0,
        analyzer_version=ANALYZER_VERSION,
        warnings=[],
    )
    session.add(analysis)
    await session.commit()
    await session.refresh(analysis)
    # ensure repository relationship loaded for response
    await session.refresh(analysis, attribute_names=["repository"])
    return analysis, False


async def run_analysis_job(analysis_id: UUID) -> None:
    """Background analysis entrypoint with its own DB session."""
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        analysis = await repo.get_analysis(session, analysis_id)
        if analysis is None:
            return
        analysis.status = "processing"
        analysis.started_at = datetime.now(UTC)
        analysis.stage = "fetching_repository"
        analysis.progress = 5
        await session.commit()

        work_dir = Path(settings.temp_dir) / str(analysis_id)
        try:
            await _execute_pipeline(session, analysis_id, work_dir, settings)
        except AppError as exc:
            await _fail(session, analysis_id, exc.code, exc.message)
        except Exception:
            logger.exception("Analysis failed unexpectedly: %s", analysis_id)
            await _fail(session, analysis_id, "ANALYSIS_FAILED", "Analysis failed unexpectedly.")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


async def _execute_pipeline(
    session: AsyncSession,
    analysis_id: UUID,
    work_dir: Path,
    settings: Settings,
) -> None:
    analysis = await repo.get_analysis(session, analysis_id)
    if analysis is None or analysis.repository is None:
        return

    parsed = parse_github_url(analysis.repository.github_url)
    client = GitHubClient(settings)
    try:
        await _set_stage(session, analysis_id, "downloading_source", 15)
        archive = await client.download_tarball(parsed, analysis.commit_sha)
    finally:
        await client.aclose()

    extract_dir = work_dir / "src"
    extract_dir.mkdir(parents=True, exist_ok=True)
    extract_archive(
        archive,
        extract_dir,
        max_extracted_bytes=settings.max_extracted_bytes,
        max_extracted_files=settings.max_extracted_files,
    )

    await _set_stage(session, analysis_id, "scanning_files", 30)

    # CPU-heavy work off the event loop
    import asyncio

    bundle = await asyncio.to_thread(
        run_static_analysis,
        extract_dir,
        max_python_files=settings.max_python_files,
        max_single_file_bytes=settings.max_single_file_bytes,
        max_extracted_files=settings.max_extracted_files,
    )

    await _set_stage(session, analysis_id, "parsing_python", 50)
    await _set_stage(session, analysis_id, "building_graph", 60)

    analysis = await repo.get_analysis(session, analysis_id)
    if analysis is None:
        return

    path_to_file: dict[str, AnalyzedFile] = {}
    for item in bundle.files:
        row = AnalyzedFile(
            analysis_id=analysis.id,
            path=item.path,
            module_name=item.module_name,
            category=item.category,
            category_reasons=item.category_reasons,
            line_count=item.line_count,
            estimated_complexity=item.estimated_complexity,
            importance_score=item.importance_score,
            incoming_count=item.incoming_count,
            outgoing_count=item.outgoing_count,
            is_test=item.is_test,
            is_entry_point=item.is_entry_point,
            entrypoint_confidence=item.entrypoint_confidence,
            entrypoint_reasons=item.entrypoint_reasons,
            parse_status=item.parse_status,
            parse_warning=item.parse_warning,
            docstring=item.docstring,
            symbols=item.symbols,
            external_imports=item.external_imports,
        )
        session.add(row)
        path_to_file[item.path] = row
    await session.flush()

    for edge in bundle.edges:
        source = path_to_file.get(edge["source_path"])
        target = path_to_file.get(edge["target_path"])
        if not source or not target:
            continue
        session.add(
            DependencyEdge(
                analysis_id=analysis.id,
                source_file_id=source.id,
                target_file_id=target.id,
                imported_module=edge["imported_module"],
                imported_names=edge["imported_names"],
                line_number=edge["line_number"],
                resolution_confidence=edge["resolution_confidence"],
            )
        )

    await _set_stage(session, analysis_id, "creating_index", 75)

    # Persist chunks (embeddings filled in AI phase if enabled)
    for chunk in bundle.chunks:
        file_row = path_to_file.get(chunk.path)
        if not file_row:
            continue
        session.add(
            CodeChunk(
                analysis_id=analysis.id,
                file_id=file_row.id,
                chunk_type=chunk.chunk_type,
                symbol_name=chunk.symbol_name,
                line_start=chunk.line_start,
                line_end=chunk.line_end,
                content=chunk.content,
                search_text=chunk.search_text,
                embedding=None,
            )
        )

    analysis.statistics = bundle.statistics
    analysis.deterministic_summary = bundle.deterministic_summary
    analysis.warnings = bundle.warnings

    await _set_stage(session, analysis_id, "generating_overview", 90)
    ai_overview = None
    if settings.ai_available:
        try:
            from app.ai.overview import generate_overview

            ai_overview = await generate_overview(
                session,
                analysis,
                bundle,
                settings=settings,
            )
        except Exception:
            logger.exception("AI overview generation failed; continuing without it")
            warnings = list(analysis.warnings or [])
            warnings.append(
                "AI overview generation failed; deterministic results are still available."
            )
            analysis.warnings = warnings
    analysis.ai_overview = ai_overview

    # Optional embedding generation
    if settings.ai_available:
        try:
            from app.ai.embeddings import embed_analysis_chunks

            await embed_analysis_chunks(session, analysis.id, settings=settings)
        except Exception:
            logger.exception("Embedding generation failed; keyword retrieval still works")

    analysis.status = "completed"
    analysis.stage = "complete"
    analysis.progress = 100
    analysis.completed_at = datetime.now(UTC)
    await session.commit()


async def _set_stage(session: AsyncSession, analysis_id: UUID, stage: str, progress: int) -> None:
    analysis = await repo.get_analysis(session, analysis_id)
    if analysis is None:
        return
    analysis.stage = stage
    analysis.progress = progress
    analysis.status = "processing"
    await session.commit()


async def _fail(session: AsyncSession, analysis_id: UUID, code: str, message: str) -> None:
    analysis = await repo.get_analysis(session, analysis_id)
    if analysis is None:
        return
    analysis.status = "failed"
    analysis.error_code = code
    analysis.error_message = message
    analysis.completed_at = datetime.now(UTC)
    await session.commit()


async def get_analysis_payload(session: AsyncSession, analysis_id: UUID) -> dict[str, Any]:
    analysis = await repo.get_analysis(session, analysis_id)
    if analysis is None:
        raise NotFoundError("Analysis not found.")
    settings = get_settings()
    repository = None
    if analysis.repository is not None:
        repository = {
            "id": analysis.repository.id,
            "owner": analysis.repository.owner,
            "name": analysis.repository.name,
            "full_name": analysis.repository.full_name,
            "github_url": analysis.repository.github_url,
            "description": analysis.repository.description,
            "default_branch": analysis.repository.default_branch,
            "primary_language": analysis.repository.primary_language,
            "stars": analysis.repository.stars,
            "is_archived": analysis.repository.is_archived,
        }
    return {
        "id": analysis.id,
        "status": analysis.status,
        "stage": analysis.stage,
        "progress": analysis.progress,
        "commit_sha": analysis.commit_sha,
        "analyzer_version": analysis.analyzer_version,
        "repository": repository,
        "statistics": analysis.statistics,
        "deterministic_summary": analysis.deterministic_summary,
        "ai_overview": analysis.ai_overview,
        "ai_available": settings.ai_available,
        "warnings": analysis.warnings,
        "error_code": analysis.error_code,
        "error_message": analysis.error_message,
        "created_at": analysis.created_at,
        "started_at": analysis.started_at,
        "completed_at": analysis.completed_at,
    }


async def build_graph_response(
    session: AsyncSession,
    analysis_id: UUID,
    *,
    limit: int,
    include_tests: bool,
    entry_points_only: bool,
    category: str | None,
    search: str | None,
) -> dict[str, Any]:
    analysis = await repo.get_analysis(session, analysis_id)
    if analysis is None:
        raise NotFoundError("Analysis not found.")
    if analysis.status != "completed":
        raise AppError("ANALYSIS_NOT_READY", "Analysis is not completed yet.", status_code=409)

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
    import networkx as nx

    from app.analysis.graph_builder import DependencyGraph, GraphEdge

    graph: Any = nx.DiGraph()
    graph.add_nodes_from([f.path for f in files])
    graph_edges: list[GraphEdge] = []
    for edge in edges:
        source = id_to_path.get(edge.source_file_id)
        target = id_to_path.get(edge.target_file_id)
        if not source or not target:
            continue
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
    node_meta = {
        f.path: {
            "id": str(f.id),
            "file_id": str(f.id),
            "category": f.category,
            "is_entry_point": f.is_entry_point,
            "is_test": f.is_test,
            "importance_score": f.importance_score,
            "module_name": f.module_name,
            "line_count": f.line_count,
        }
        for f in files
    }
    return graph_to_serializable(
        dep,
        node_meta=node_meta,
        limit=limit,
        include_tests=include_tests,
        entry_points_only=entry_points_only,
        category=category,
        search=search,
    )


async def reanalyze(session: AsyncSession, analysis_id: UUID) -> tuple[Analysis, bool]:
    analysis = await repo.get_analysis(session, analysis_id)
    if analysis is None or analysis.repository is None:
        raise NotFoundError("Analysis not found.")
    return await start_analysis(
        session,
        repository_url=analysis.repository.github_url,
        force=True,
    )
