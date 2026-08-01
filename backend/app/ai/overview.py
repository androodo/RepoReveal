"""AI architecture overview generation."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts import OVERVIEW_SYSTEM
from app.analysis.pipeline import AnalysisBundle
from app.core.config import Settings
from app.db.models import Analysis

logger = logging.getLogger(__name__)


async def generate_overview(
    session: AsyncSession,
    analysis: Analysis,
    bundle: AnalysisBundle,
    *,
    settings: Settings,
) -> dict[str, Any] | None:
    if not settings.ai_available:
        return None

    repo = analysis.repository
    important = bundle.deterministic_summary.get("important_files", [])[:8]
    entry_points = bundle.deterministic_summary.get("entry_points", [])[:8]
    start_here = bundle.deterministic_summary.get("start_here", [])[:8]

    # Selected chunks from important files
    important_paths = {item["path"] for item in important}
    selected_chunks = [c for c in bundle.chunks if c.path in important_paths][:10]
    evidence = {
        "repository": {
            "full_name": repo.full_name if repo else None,
            "description": repo.description if repo else None,
            "default_branch": repo.default_branch if repo else None,
            "primary_language": repo.primary_language if repo else None,
        },
        "readme_excerpt": bundle.readme_excerpt,
        "statistics": bundle.statistics,
        "entry_points": entry_points,
        "important_files": important,
        "start_here": start_here,
        "category_counts": bundle.deterministic_summary.get("category_counts"),
        "code_chunks": [
            {
                "path": c.path,
                "symbol_name": c.symbol_name,
                "line_start": c.line_start,
                "line_end": c.line_end,
                "content": c.content[:1500],
            }
            for c in selected_chunks
        ],
    }

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )
    schema_hint = {
        "project_purpose": "...",
        "architecture_summary": "...",
        "main_components": [{"name": "...", "description": "...", "files": ["..."]}],
        "execution_flow": ["..."],
        "start_here": [{"file_path": "...", "reason": "..."}],
        "caveats": ["..."],
    }
    response = await client.chat.completions.create(
        model=settings.openai_chat_model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": OVERVIEW_SYSTEM},
            {
                "role": "user",
                "content": (
                    "Generate an architecture overview JSON with this shape:\n"
                    f"{json.dumps(schema_hint)}\n\nEvidence:\n"
                    f"{json.dumps(evidence)[: settings.ai_max_context_chars]}"
                ),
            },
        ],
    )
    content = response.choices[0].message.content or "{}"
    data = json.loads(content)
    return _validate_overview(data, known_paths={f.path for f in bundle.files})


def _validate_overview(data: dict[str, Any], *, known_paths: set[str]) -> dict[str, Any]:
    def filter_files(paths: list[Any]) -> list[str]:
        return [p for p in paths if isinstance(p, str) and p in known_paths]

    components = []
    for item in data.get("main_components") or []:
        if not isinstance(item, dict):
            continue
        components.append(
            {
                "name": str(item.get("name") or "Component"),
                "description": str(item.get("description") or ""),
                "files": filter_files(list(item.get("files") or [])),
            }
        )
    start_here = []
    for item in data.get("start_here") or []:
        if not isinstance(item, dict):
            continue
        path = item.get("file_path")
        if isinstance(path, str) and path in known_paths:
            start_here.append({"file_path": path, "reason": str(item.get("reason") or "")})

    return {
        "project_purpose": str(data.get("project_purpose") or ""),
        "architecture_summary": str(data.get("architecture_summary") or ""),
        "main_components": components,
        "execution_flow": [str(x) for x in (data.get("execution_flow") or [])],
        "start_here": start_here,
        "caveats": [str(x) for x in (data.get("caveats") or [])],
    }
