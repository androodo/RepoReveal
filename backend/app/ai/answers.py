"""Repository Q&A and file explanation."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts import ASK_SYSTEM, EXPLAIN_SYSTEM
from app.ai.retrieval import (
    RetrievedChunk,
    build_context,
    hybrid_retrieve,
    validate_citations,
)
from app.core.config import Settings
from app.core.exceptions import AiUnavailableError, InsufficientEvidenceError, NotFoundError
from app.db.models import AiQueryLog, Analysis, AnalyzedFile, CodeChunk
from app.repositories import analyses as repo

logger = logging.getLogger(__name__)


async def ask_repository(
    session: AsyncSession,
    analysis_id: UUID,
    question: str,
    *,
    settings: Settings,
) -> dict[str, Any]:
    analysis = await repo.get_analysis(session, analysis_id)
    if analysis is None or analysis.status != "completed":
        raise NotFoundError("Completed analysis not found.")
    if not settings.ai_available:
        raise AiUnavailableError()

    chunks = await hybrid_retrieve(session, analysis_id, question, settings=settings)
    if not chunks:
        raise InsufficientEvidenceError()

    structural = _structural_facts(analysis)
    context = build_context(
        repository_meta={
            "full_name": analysis.repository.full_name if analysis.repository else "",
            "description": analysis.repository.description if analysis.repository else "",
        },
        structural_facts=structural,
        chunks=chunks,
        max_chars=settings.ai_max_context_chars,
    )
    raw = await _chat_json(settings, ASK_SYSTEM, f"Question: {question}\n\n{context}")
    known_paths = await _known_paths(session, analysis_id)
    result = _normalize_answer(raw, chunks=chunks, known_paths=known_paths)
    session.add(
        AiQueryLog(
            analysis_id=analysis_id,
            question=question,
            answer=result,
            retrieved_chunk_ids=[str(c.chunk_id) for c in chunks],
        )
    )
    await session.commit()
    result["starter_questions"] = suggest_questions(analysis)
    return result


async def explain_file(
    session: AsyncSession,
    analysis_id: UUID,
    file_id: UUID,
    *,
    settings: Settings,
) -> dict[str, Any]:
    analysis = await repo.get_analysis(session, analysis_id)
    if analysis is None or analysis.status != "completed":
        raise NotFoundError("Completed analysis not found.")
    if not settings.ai_available:
        raise AiUnavailableError()

    file_row = await repo.get_file(session, analysis_id, file_id)
    if file_row is None:
        raise NotFoundError("File not found.")

    chunks = (
        (
            await session.execute(
                select(CodeChunk).where(
                    CodeChunk.analysis_id == analysis_id,
                    CodeChunk.file_id == file_id,
                )
            )
        )
        .scalars()
        .all()
    )
    outgoing, incoming = await repo.get_edges_for_file(session, analysis_id, file_id)
    related_ids = [e.target_file_id for e in outgoing] + [e.source_file_id for e in incoming]
    related_files = await repo.files_by_ids(session, related_ids)

    neighbor_chunks: list[CodeChunk] = []
    if related_ids:
        neighbor_chunks = list(
            (
                await session.execute(
                    select(CodeChunk)
                    .where(
                        CodeChunk.analysis_id == analysis_id,
                        CodeChunk.file_id.in_(related_ids[:8]),
                    )
                    .limit(8)
                )
            )
            .scalars()
            .all()
        )

    retrieved: list[RetrievedChunk] = []
    for chunk in list(chunks) + list(neighbor_chunks):
        if chunk.file_id == file_id:
            path = file_row.path
        else:
            related = related_files.get(chunk.file_id)
            path = related.path if related is not None else "unknown"
        retrieved.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                file_id=chunk.file_id,
                file_path=path,
                symbol_name=chunk.symbol_name,
                line_start=chunk.line_start,
                line_end=chunk.line_end,
                content=chunk.content,
                score=1.0,
            )
        )

    dep_paths = [
        related_files[e.target_file_id].path for e in outgoing if e.target_file_id in related_files
    ]
    importer_paths = [
        related_files[e.source_file_id].path for e in incoming if e.source_file_id in related_files
    ]
    facts = [
        f"File path: {file_row.path}",
        f"Category: {file_row.category}",
        f"Entry point: {file_row.is_entry_point}",
        f"Incoming: {file_row.incoming_count}, Outgoing: {file_row.outgoing_count}",
        f"Symbols: {json.dumps(file_row.symbols or [])[:2000]}",
        f"Dependencies: {dep_paths}",
        f"Importers: {importer_paths}",
        f"Entrypoint reasons: {file_row.entrypoint_reasons}",
    ]
    context = build_context(
        repository_meta={
            "full_name": analysis.repository.full_name if analysis.repository else "",
            "description": analysis.repository.description if analysis.repository else "",
        },
        structural_facts=facts,
        chunks=retrieved,
        max_chars=settings.ai_max_context_chars,
    )
    raw = await _chat_json(
        settings,
        EXPLAIN_SYSTEM,
        f"Explain this file for a new developer.\n\n{context}",
    )
    known_paths = await _known_paths(session, analysis_id)
    return _normalize_answer(raw, chunks=retrieved, known_paths=known_paths)


def suggest_questions(analysis: Analysis) -> list[str]:
    summary = analysis.deterministic_summary or {}
    questions = [
        "Where does the application start?",
        "How are the main components organized?",
        "Which files should I read first?",
    ]
    categories = summary.get("category_counts") or {}
    if "API / Routes" in categories:
        questions.append("Where are API routes defined?")
    if "Models / Data" in categories:
        questions.append("Where is data access or model logic implemented?")
    if "Configuration" in categories:
        questions.append("Where is configuration loaded?")
    return questions[:4]


async def _chat_json(settings: Settings, system: str, user: str) -> dict[str, Any]:
    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )
    response = await client.chat.completions.create(
        model=settings.openai_chat_model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = response.choices[0].message.content or "{}"
    parsed: Any = json.loads(content)
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _normalize_answer(
    raw: dict[str, Any],
    *,
    chunks: list[RetrievedChunk],
    known_paths: set[str],
) -> dict[str, Any]:
    citations = validate_citations(
        list(raw.get("citations") or []),
        allowed_chunks=chunks,
        known_paths=known_paths,
    )
    suggested = [
        p for p in (raw.get("suggested_files") or []) if isinstance(p, str) and p in known_paths
    ]
    answer = str(raw.get("answer") or "").strip()
    confidence = str(raw.get("confidence") or "low")
    limitations = [str(x) for x in (raw.get("limitations") or [])]
    if not answer or (not citations and confidence == "high"):
        answer = "RepoReveal could not find enough repository evidence to answer confidently."
        confidence = "low"
        limitations.append("Insufficient grounded evidence after citation validation.")
    return {
        "answer": answer,
        "citations": citations,
        "suggested_files": suggested,
        "confidence": confidence,
        "limitations": limitations,
    }


def _structural_facts(analysis: Analysis) -> list[str]:
    stats = analysis.statistics or {}
    summary = analysis.deterministic_summary or {}
    facts = [
        f"Python files: {stats.get('python_file_count')}",
        f"Internal edges: {stats.get('internal_dependency_edges')}",
        f"Entry points: {[e.get('path') for e in summary.get('entry_points') or []]}",
        f"Important files: {[f.get('path') for f in (summary.get('important_files') or [])[:8]]}",
    ]
    return facts


async def _known_paths(session: AsyncSession, analysis_id: UUID) -> set[str]:
    rows = (
        (
            await session.execute(
                select(AnalyzedFile.path).where(AnalyzedFile.analysis_id == analysis_id)
            )
        )
        .scalars()
        .all()
    )
    return set(rows)
