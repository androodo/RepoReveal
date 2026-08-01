"""Pydantic API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.services.github_urls import parse_github_url


class AnalysisCreateRequest(BaseModel):
    repository_url: str
    force: bool = False

    @field_validator("repository_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parse_github_url(value)
        return value.strip()


class AnalysisCreateResponse(BaseModel):
    analysis_id: UUID
    status: str
    cached: bool


class RepositorySummary(BaseModel):
    id: UUID
    owner: str
    name: str
    full_name: str
    github_url: str
    description: str | None
    default_branch: str
    primary_language: str | None
    stars: int
    is_archived: bool


class AnalysisStatusResponse(BaseModel):
    id: UUID
    status: str
    stage: str
    progress: int
    commit_sha: str | None = None
    analyzer_version: str
    repository: RepositorySummary | None = None
    statistics: dict[str, Any] | None = None
    deterministic_summary: dict[str, Any] | None = None
    ai_overview: dict[str, Any] | None = None
    ai_available: bool = False
    warnings: list[Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class FileListItem(BaseModel):
    id: UUID
    path: str
    module_name: str | None
    category: str
    line_count: int
    estimated_complexity: int
    importance_score: float
    incoming_count: int
    outgoing_count: int
    is_test: bool
    is_entry_point: bool
    parse_status: str
    flags: list[str] = Field(default_factory=list)


class FileListResponse(BaseModel):
    items: list[FileListItem]
    total: int
    page: int
    page_size: int


class FileDetailResponse(BaseModel):
    id: UUID
    path: str
    module_name: str | None
    category: str
    category_reasons: list[Any] | None
    line_count: int
    estimated_complexity: int
    importance_score: float
    incoming_count: int
    outgoing_count: int
    is_test: bool
    is_entry_point: bool
    entrypoint_confidence: str | None
    entrypoint_reasons: list[Any] | None
    parse_status: str
    parse_warning: str | None
    docstring: str | None
    symbols: list[Any] | None
    external_imports: list[Any] | None
    internal_dependencies: list[str]
    importers: list[str]
    github_url: str


class GraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    truncated: bool


class ImpactResponse(BaseModel):
    selected_path: str
    direct_dependents: list[str]
    second_level_dependents: list[str]
    related_tests: list[str]
    affected_entry_points: list[str]
    representative_paths: list[list[str]]
    disclaimer: str
    explanation: str | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class Citation(BaseModel):
    file_path: str
    line_start: int
    line_end: int
    reason: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    suggested_files: list[str]
    confidence: str
    limitations: list[str]
    starter_questions: list[str] | None = None


class ExplainResponse(BaseModel):
    answer: str
    citations: list[Citation]
    suggested_files: list[str]
    confidence: str
    limitations: list[str]
