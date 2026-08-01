# RepoReveal Architecture

## Overview

RepoReveal is a monorepo with one Next.js frontend, one FastAPI backend, and one PostgreSQL database with the `pgvector` extension.

```text
Browser → Next.js (App Router)
        → FastAPI (/api/v1)
        → PostgreSQL + pgvector
```

## Frontend

- Next.js App Router with TypeScript strict mode
- TanStack Query for analysis polling and server state
- React Flow + Dagre for the dependency graph
- Client Components only where interactivity is required

Primary routes:

- `/` landing page and repository URL form
- `/analyses/[analysisId]` results workspace (Overview, Architecture, Files, Ask)

## Backend

- FastAPI application with typed Pydantic schemas
- SQLAlchemy 2 async models via `asyncpg`
- Alembic migrations
- Analysis pipeline under `app/analysis/`
- GitHub acquisition under `app/services/`
- Grounded AI helpers under `app/ai/`

## Database

Tables:

- `repositories`
- `analyses` (cached by repository + commit SHA + analyzer version)
- `analyzed_files`
- `dependency_edges`
- `code_chunks` (optional embeddings)
- `ai_query_logs`

## Analysis pipeline

1. Validate GitHub URL
2. Fetch repository metadata and resolve default-branch commit
3. Return cached analysis when available
4. Download tarball for the exact commit
5. Safely extract with size/path/symlink guards
6. Scan, parse (AST), resolve imports, build graph
7. Classify files, detect entry points, score importance
8. Chunk source for retrieval
9. Optionally embed chunks and generate an AI overview
10. Persist results and mark completed

## Background processing

`POST /api/v1/analyses` creates a row and schedules a FastAPI `BackgroundTasks` job.

The background task opens its own database session. CPU-heavy AST work runs in a worker thread via `asyncio.to_thread`.

**Limitation:** in-process background tasks can be lost if the backend process restarts mid-analysis. This personal-project version intentionally avoids Redis/Celery/Kafka. Failed or interrupted analyses can be retried with **Reanalyze**.

## Caching

Completed analyses are uniquely keyed by:

```text
repository_id + commit_sha + analyzer_version
```

Reanalyze with `force=true` creates a fresh analysis for the current commit.

## Why no distributed queue

RepoReveal is a finishable portfolio project. FastAPI background tasks are enough to demonstrate asynchronous analysis and polling without enterprise infrastructure.
