"""OpenAI embedding helpers."""

from __future__ import annotations

import logging
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import CodeChunk

logger = logging.getLogger(__name__)


def get_openai_client(settings: Settings) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )


async def embed_texts(settings: Settings, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = get_openai_client(settings)
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )
    return [list(item.embedding) for item in response.data]


async def embed_analysis_chunks(
    session: AsyncSession,
    analysis_id: UUID,
    *,
    settings: Settings,
    batch_size: int = 32,
) -> None:
    chunks = (
        (
            await session.execute(
                select(CodeChunk).where(
                    CodeChunk.analysis_id == analysis_id,
                    CodeChunk.embedding.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        texts = [c.search_text[:6000] for c in batch]
        vectors = await embed_texts(settings, texts)
        for chunk, vector in zip(batch, vectors, strict=True):
            chunk.embedding = vector
    await session.flush()
