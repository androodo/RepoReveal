"""Hybrid retrieval with graph-neighbor expansion and citation validation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import embed_texts
from app.core.config import Settings
from app.db.models import AnalyzedFile, CodeChunk, DependencyEdge


@dataclass(slots=True)
class RetrievedChunk:
    chunk_id: UUID
    file_id: UUID
    file_path: str
    symbol_name: str | None
    line_start: int
    line_end: int
    content: str
    score: float
    reasons: list[str] = field(default_factory=list)


def analyze_query(question: str) -> dict[str, list[str]]:
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_\./-]*", question)
    path_terms = [t for t in tokens if "/" in t or t.endswith(".py")]
    symbol_terms = [t for t in tokens if "_" in t or t[:1].isupper()]
    concept_terms = [t.lower() for t in tokens if len(t) > 3]
    return {
        "path_terms": path_terms,
        "symbol_terms": symbol_terms,
        "concept_terms": concept_terms,
    }


async def hybrid_retrieve(
    session: AsyncSession,
    analysis_id: UUID,
    question: str,
    *,
    settings: Settings,
    limit: int | None = None,
) -> list[RetrievedChunk]:
    """
    Retrieval scoring (documented):

        final_score =
            semantic_similarity
          + lexical_match
          + exact_symbol_bonus
          + exact_path_bonus
          + graph_neighbor_bonus
    """
    limit = limit or settings.ai_max_retrieved_chunks
    query = analyze_query(question)
    files = (
        (await session.execute(select(AnalyzedFile).where(AnalyzedFile.analysis_id == analysis_id)))
        .scalars()
        .all()
    )
    file_by_id = {f.id: f for f in files}
    path_by_id = {f.id: f.path for f in files}

    chunks = (
        (await session.execute(select(CodeChunk).where(CodeChunk.analysis_id == analysis_id)))
        .scalars()
        .all()
    )

    semantic: dict[UUID, float] = {}
    if settings.ai_available:
        try:
            vectors = await embed_texts(settings, [question])
            if vectors:
                qvec = vectors[0]
                # cosine distance via pgvector if embeddings exist
                result = await session.execute(
                    text(
                        """
                        SELECT id, 1 - (embedding <=> :embedding) AS score
                        FROM code_chunks
                        WHERE analysis_id = :analysis_id AND embedding IS NOT NULL
                        ORDER BY embedding <=> :embedding
                        LIMIT 40
                        """
                    ),
                    {"analysis_id": str(analysis_id), "embedding": str(qvec)},
                )
                for row in result.mappings():
                    semantic[row["id"]] = float(row["score"] or 0)
        except Exception:
            semantic = {}

    scored: list[RetrievedChunk] = []
    for chunk in chunks:
        path = path_by_id.get(chunk.file_id, "")
        lexical = 0.0
        reasons: list[str] = []
        search_l = chunk.search_text.lower()
        for term in query["concept_terms"]:
            if term in search_l:
                lexical += 0.15
        symbol_bonus = 0.0
        for term in query["symbol_terms"]:
            if chunk.symbol_name and term == chunk.symbol_name:
                symbol_bonus += 0.5
                reasons.append("exact_symbol")
            elif term.lower() in search_l:
                symbol_bonus += 0.2
        path_bonus = 0.0
        for term in query["path_terms"]:
            if term in path:
                path_bonus += 0.6
                reasons.append("exact_path")
        sem = semantic.get(chunk.id, 0.0)
        score = sem + lexical + symbol_bonus + path_bonus
        if score <= 0:
            continue
        scored.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                file_id=chunk.file_id,
                file_path=path,
                symbol_name=chunk.symbol_name,
                line_start=chunk.line_start,
                line_end=chunk.line_end,
                content=chunk.content,
                score=score,
                reasons=reasons,
            )
        )

    scored.sort(key=lambda c: c.score, reverse=True)
    top = scored[: max(limit, 6)]

    # Graph expansion for highly ranked files
    top_file_ids = {c.file_id for c in top[:5]}
    neighbor_ids = await _neighbor_file_ids(session, analysis_id, top_file_ids)
    existing_ids = {c.chunk_id for c in top}
    for chunk in chunks:
        if chunk.file_id in neighbor_ids and chunk.id not in existing_ids:
            path = path_by_id.get(chunk.file_id, "")
            file_row = file_by_id.get(chunk.file_id)
            bonus = 0.35
            if file_row and file_row.is_test:
                bonus = 0.25
            top.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    file_id=chunk.file_id,
                    file_path=path,
                    symbol_name=chunk.symbol_name,
                    line_start=chunk.line_start,
                    line_end=chunk.line_end,
                    content=chunk.content,
                    score=bonus,
                    reasons=["graph_neighbor"],
                )
            )
            existing_ids.add(chunk.id)
            if len(top) >= limit + 4:
                break

    top.sort(key=lambda c: c.score, reverse=True)
    return top[:limit]


async def _neighbor_file_ids(
    session: AsyncSession, analysis_id: UUID, seed_ids: set[UUID]
) -> set[UUID]:
    if not seed_ids:
        return set()
    edges = (
        (
            await session.execute(
                select(DependencyEdge).where(DependencyEdge.analysis_id == analysis_id)
            )
        )
        .scalars()
        .all()
    )
    neighbors: set[UUID] = set()
    for edge in edges:
        if edge.source_file_id in seed_ids:
            neighbors.add(edge.target_file_id)
        if edge.target_file_id in seed_ids:
            neighbors.add(edge.source_file_id)
    return neighbors - seed_ids


def validate_citations(
    citations: list[Any],
    *,
    allowed_chunks: list[RetrievedChunk],
    known_paths: set[str],
) -> list[dict[str, Any]]:
    allowed_ranges = {(c.file_path, c.line_start, c.line_end) for c in allowed_chunks}
    allowed_paths = {c.file_path for c in allowed_chunks} | known_paths
    valid: list[dict[str, Any]] = []
    for cite in citations:
        if isinstance(cite, str):
            path = cite
            if path not in allowed_paths:
                continue
            chunk = next((c for c in allowed_chunks if c.file_path == path), None)
            if chunk is None:
                continue
            valid.append(
                {
                    "file_path": path,
                    "line_start": chunk.line_start,
                    "line_end": chunk.line_end,
                    "reason": "Referenced in evidence",
                }
            )
            continue

        if not isinstance(cite, dict):
            continue

        raw_path = cite.get("file_path")
        start = cite.get("line_start")
        end = cite.get("line_end")
        if not isinstance(raw_path, str) or raw_path not in allowed_paths:
            continue
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        path = raw_path
        overlaps = any(
            c.file_path == path and not (end < c.line_start or start > c.line_end)
            for c in allowed_chunks
        )
        if (
            overlaps
            or (path, start, end) in allowed_ranges
            or path in {c.file_path for c in allowed_chunks}
        ):
            valid.append(
                {
                    "file_path": path,
                    "line_start": start,
                    "line_end": end,
                    "reason": str(cite.get("reason") or "Referenced in evidence"),
                }
            )
    return valid


def build_context(
    *,
    repository_meta: dict[str, Any],
    structural_facts: list[str],
    chunks: list[RetrievedChunk],
    max_chars: int,
) -> str:
    parts = [
        f"Repository: {repository_meta.get('full_name')}",
        f"Description: {repository_meta.get('description')}",
        "Structural facts:",
        *[f"- {fact}" for fact in structural_facts],
        "Source evidence:",
    ]
    used = "\n".join(parts)
    for chunk in chunks:
        block = (
            f"\n---\nFile: {chunk.file_path} lines {chunk.line_start}-{chunk.line_end}"
            f" symbol={chunk.symbol_name}\n{chunk.content}\n"
        )
        if len(used) + len(block) > max_chars:
            break
        used += block
    return used
