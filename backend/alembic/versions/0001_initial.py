"""Initial schema with pgvector.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "repositories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=520), nullable=False),
        sa.Column("github_url", sa.String(length=1024), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_branch", sa.String(length=255), nullable=False),
        sa.Column("primary_language", sa.String(length=100), nullable=True),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner", "name", name="uq_repositories_owner_name"),
    )

    op.create_table(
        "analyses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("repository_id", sa.UUID(), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("analyzer_version", sa.String(length=32), nullable=False),
        sa.Column("statistics", postgresql.JSONB(), nullable=True),
        sa.Column("deterministic_summary", postgresql.JSONB(), nullable=True),
        sa.Column("ai_overview", postgresql.JSONB(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id",
            "commit_sha",
            "analyzer_version",
            name="uq_analyses_repo_commit_version",
        ),
    )
    op.create_index("ix_analyses_status", "analyses", ["status"])
    op.create_index("ix_analyses_created_at", "analyses", ["created_at"])

    op.create_table(
        "analyzed_files",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("analysis_id", sa.UUID(), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("module_name", sa.String(length=1024), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("category_reasons", postgresql.JSONB(), nullable=True),
        sa.Column("line_count", sa.Integer(), nullable=False),
        sa.Column("estimated_complexity", sa.Integer(), nullable=False),
        sa.Column("importance_score", sa.Float(), nullable=False),
        sa.Column("incoming_count", sa.Integer(), nullable=False),
        sa.Column("outgoing_count", sa.Integer(), nullable=False),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        sa.Column("is_entry_point", sa.Boolean(), nullable=False),
        sa.Column("entrypoint_confidence", sa.String(length=16), nullable=True),
        sa.Column("entrypoint_reasons", postgresql.JSONB(), nullable=True),
        sa.Column("parse_status", sa.String(length=32), nullable=False),
        sa.Column("parse_warning", sa.Text(), nullable=True),
        sa.Column("docstring", sa.Text(), nullable=True),
        sa.Column("symbols", postgresql.JSONB(), nullable=True),
        sa.Column("external_imports", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_id", "path", name="uq_analyzed_files_analysis_path"),
    )
    op.create_index(
        "ix_analyzed_files_importance", "analyzed_files", ["analysis_id", "importance_score"]
    )
    op.create_index("ix_analyzed_files_category", "analyzed_files", ["analysis_id", "category"])
    op.create_index(
        "ix_analyzed_files_entry_point", "analyzed_files", ["analysis_id", "is_entry_point"]
    )

    op.create_table(
        "dependency_edges",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("analysis_id", sa.UUID(), nullable=False),
        sa.Column("source_file_id", sa.UUID(), nullable=False),
        sa.Column("target_file_id", sa.UUID(), nullable=False),
        sa.Column("imported_module", sa.String(length=1024), nullable=False),
        sa.Column("imported_names", postgresql.JSONB(), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column("resolution_confidence", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_file_id"], ["analyzed_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_file_id"], ["analyzed_files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dependency_edges_analysis", "dependency_edges", ["analysis_id"])
    op.create_index("ix_dependency_edges_source", "dependency_edges", ["source_file_id"])
    op.create_index("ix_dependency_edges_target", "dependency_edges", ["target_file_id"])

    op.create_table(
        "code_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("analysis_id", sa.UUID(), nullable=False),
        sa.Column("file_id", sa.UUID(), nullable=False),
        sa.Column("chunk_type", sa.String(length=64), nullable=False),
        sa.Column("symbol_name", sa.String(length=512), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["analyzed_files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_code_chunks_analysis", "code_chunks", ["analysis_id"])
    op.create_index("ix_code_chunks_file", "code_chunks", ["file_id"])
    op.create_index("ix_code_chunks_symbol", "code_chunks", ["analysis_id", "symbol_name"])
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_code_chunks_embedding "
        "ON code_chunks USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_code_chunks_search_text "
        "ON code_chunks USING gin (to_tsvector('english', search_text))"
    )

    op.create_table(
        "ai_query_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("analysis_id", sa.UUID(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", postgresql.JSONB(), nullable=True),
        sa.Column("retrieved_chunk_ids", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_query_logs_analysis", "ai_query_logs", ["analysis_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_query_logs_analysis", table_name="ai_query_logs")
    op.drop_table("ai_query_logs")
    op.execute("DROP INDEX IF EXISTS ix_code_chunks_search_text")
    op.execute("DROP INDEX IF EXISTS ix_code_chunks_embedding")
    op.drop_index("ix_code_chunks_symbol", table_name="code_chunks")
    op.drop_index("ix_code_chunks_file", table_name="code_chunks")
    op.drop_index("ix_code_chunks_analysis", table_name="code_chunks")
    op.drop_table("code_chunks")
    op.drop_index("ix_dependency_edges_target", table_name="dependency_edges")
    op.drop_index("ix_dependency_edges_source", table_name="dependency_edges")
    op.drop_index("ix_dependency_edges_analysis", table_name="dependency_edges")
    op.drop_table("dependency_edges")
    op.drop_index("ix_analyzed_files_entry_point", table_name="analyzed_files")
    op.drop_index("ix_analyzed_files_category", table_name="analyzed_files")
    op.drop_index("ix_analyzed_files_importance", table_name="analyzed_files")
    op.drop_table("analyzed_files")
    op.drop_index("ix_analyses_created_at", table_name="analyses")
    op.drop_index("ix_analyses_status", table_name="analyses")
    op.drop_table("analyses")
    op.drop_table("repositories")
