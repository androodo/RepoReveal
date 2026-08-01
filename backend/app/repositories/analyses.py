"""Data-access helpers for analyses."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Analysis, AnalyzedFile, DependencyEdge, Repository


async def get_analysis(session: AsyncSession, analysis_id: UUID) -> Analysis | None:
    stmt = (
        select(Analysis)
        .where(Analysis.id == analysis_id)
        .options(selectinload(Analysis.repository))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_cached_analysis(
    session: AsyncSession,
    repository_id: UUID,
    commit_sha: str,
    analyzer_version: str,
) -> Analysis | None:
    stmt = (
        select(Analysis)
        .where(
            Analysis.repository_id == repository_id,
            Analysis.commit_sha == commit_sha,
            Analysis.analyzer_version == analyzer_version,
            Analysis.status == "completed",
        )
        .options(selectinload(Analysis.repository))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create_repository(
    session: AsyncSession,
    *,
    owner: str,
    name: str,
    full_name: str,
    github_url: str,
    description: str | None,
    default_branch: str,
    primary_language: str | None,
    stars: int,
    is_archived: bool,
) -> Repository:
    stmt = select(Repository).where(Repository.owner == owner, Repository.name == name)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        existing.description = description
        existing.default_branch = default_branch
        existing.primary_language = primary_language
        existing.stars = stars
        existing.is_archived = is_archived
        existing.github_url = github_url
        existing.full_name = full_name
        return existing

    repo = Repository(
        owner=owner,
        name=name,
        full_name=full_name,
        github_url=github_url,
        description=description,
        default_branch=default_branch,
        primary_language=primary_language,
        stars=stars,
        is_archived=is_archived,
    )
    session.add(repo)
    await session.flush()
    return repo


async def list_files_query(
    analysis_id: UUID,
    *,
    search: str | None,
    category: str | None,
    entry_points: bool | None,
    tests: bool | None,
    parse_status: str | None,
    sort: str,
    order: str,
) -> Select[tuple[AnalyzedFile]]:
    stmt = select(AnalyzedFile).where(AnalyzedFile.analysis_id == analysis_id)
    if search:
        stmt = stmt.where(AnalyzedFile.path.ilike(f"%{search}%"))
    if category:
        stmt = stmt.where(AnalyzedFile.category == category)
    if entry_points is True:
        stmt = stmt.where(AnalyzedFile.is_entry_point.is_(True))
    if tests is True:
        stmt = stmt.where(AnalyzedFile.is_test.is_(True))
    if tests is False:
        stmt = stmt.where(AnalyzedFile.is_test.is_(False))
    if parse_status:
        stmt = stmt.where(AnalyzedFile.parse_status == parse_status)

    sort_map = {
        "importance": AnalyzedFile.importance_score,
        "incoming": AnalyzedFile.incoming_count,
        "outgoing": AnalyzedFile.outgoing_count,
        "lines": AnalyzedFile.line_count,
        "complexity": AnalyzedFile.estimated_complexity,
        "path": AnalyzedFile.path,
    }
    column = sort_map.get(sort, AnalyzedFile.importance_score)
    stmt = stmt.order_by(column.asc() if order == "asc" else column.desc(), AnalyzedFile.path.asc())
    return stmt


async def count_files(session: AsyncSession, stmt: Select[tuple[AnalyzedFile]]) -> int:
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    return int((await session.execute(count_stmt)).scalar_one())


async def get_file(session: AsyncSession, analysis_id: UUID, file_id: UUID) -> AnalyzedFile | None:
    stmt = select(AnalyzedFile).where(
        AnalyzedFile.analysis_id == analysis_id,
        AnalyzedFile.id == file_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_edges_for_file(
    session: AsyncSession, analysis_id: UUID, file_id: UUID
) -> tuple[list[DependencyEdge], list[DependencyEdge]]:
    outgoing = (
        (
            await session.execute(
                select(DependencyEdge).where(
                    DependencyEdge.analysis_id == analysis_id,
                    DependencyEdge.source_file_id == file_id,
                )
            )
        )
        .scalars()
        .all()
    )
    incoming = (
        (
            await session.execute(
                select(DependencyEdge).where(
                    DependencyEdge.analysis_id == analysis_id,
                    DependencyEdge.target_file_id == file_id,
                )
            )
        )
        .scalars()
        .all()
    )
    return list(outgoing), list(incoming)


async def files_by_ids(session: AsyncSession, file_ids: list[UUID]) -> dict[UUID, AnalyzedFile]:
    if not file_ids:
        return {}
    rows = (
        (await session.execute(select(AnalyzedFile).where(AnalyzedFile.id.in_(file_ids))))
        .scalars()
        .all()
    )
    return {row.id: row for row in rows}
