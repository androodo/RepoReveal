"""SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID as PyUUID
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.base import Base

_EMBEDDING_DIM = get_settings().embedding_dimensions


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("owner", "name", name="uq_repositories_owner_name"),)

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(520), nullable=False)
    github_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    primary_language: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    analyses: Mapped[list[Analysis]] = relationship(back_populates="repository")


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "commit_sha",
            "analyzer_version",
            name="uq_analyses_repo_commit_version",
        ),
        Index("ix_analyses_status", "status"),
        Index("ix_analyses_created_at", "created_at"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    stage: Mapped[str] = mapped_column(String(64), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    analyzer_version: Mapped[str] = mapped_column(String(32), nullable=False)
    statistics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    deterministic_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ai_overview: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    warnings: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    repository: Mapped[Repository] = relationship(back_populates="analyses")
    files: Mapped[list[AnalyzedFile]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    edges: Mapped[list[DependencyEdge]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    chunks: Mapped[list[CodeChunk]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )


class AnalyzedFile(Base):
    __tablename__ = "analyzed_files"
    __table_args__ = (
        UniqueConstraint("analysis_id", "path", name="uq_analyzed_files_analysis_path"),
        Index("ix_analyzed_files_importance", "analysis_id", "importance_score"),
        Index("ix_analyzed_files_category", "analysis_id", "category"),
        Index("ix_analyzed_files_entry_point", "analysis_id", "is_entry_point"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    analysis_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    module_name: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="Other")
    category_reasons: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    line_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_complexity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    importance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    incoming_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outgoing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_entry_point: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    entrypoint_confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    entrypoint_reasons: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    parse_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ok")
    parse_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    docstring: Mapped[str | None] = mapped_column(Text, nullable=True)
    symbols: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    external_imports: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analysis: Mapped[Analysis] = relationship(back_populates="files")
    chunks: Mapped[list[CodeChunk]] = relationship(back_populates="file")


class DependencyEdge(Base):
    __tablename__ = "dependency_edges"
    __table_args__ = (
        Index("ix_dependency_edges_analysis", "analysis_id"),
        Index("ix_dependency_edges_source", "source_file_id"),
        Index("ix_dependency_edges_target", "target_file_id"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    analysis_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
    )
    source_file_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyzed_files.id", ondelete="CASCADE"), nullable=False
    )
    target_file_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyzed_files.id", ondelete="CASCADE"), nullable=False
    )
    imported_module: Mapped[str] = mapped_column(String(1024), nullable=False)
    imported_names: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution_confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="high")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analysis: Mapped[Analysis] = relationship(back_populates="edges")


class CodeChunk(Base):
    __tablename__ = "code_chunks"
    __table_args__ = (
        Index("ix_code_chunks_analysis", "analysis_id"),
        Index("ix_code_chunks_file", "file_id"),
        Index("ix_code_chunks_symbol", "analysis_id", "symbol_name"),
    )

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    analysis_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyzed_files.id", ondelete="CASCADE"), nullable=False
    )
    chunk_type: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    line_start: Mapped[int] = mapped_column(Integer, nullable=False)
    line_end: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(_EMBEDDING_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analysis: Mapped[Analysis] = relationship(back_populates="chunks")
    file: Mapped[AnalyzedFile] = relationship(back_populates="chunks")


class AiQueryLog(Base):
    __tablename__ = "ai_query_logs"
    __table_args__ = (Index("ix_ai_query_logs_analysis", "analysis_id"),)

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    analysis_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    retrieved_chunk_ids: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
