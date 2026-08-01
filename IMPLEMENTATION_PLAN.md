# RepoReveal Implementation Plan

## Status

Phases 1–9 implemented in the greenfield repository.

- Foundation, acquisition, analyzer, API, frontend, graph, AI, docs, and CI are in place.
- Backend unit/integration tests pass without external credentials.
- Frontend unit tests, typecheck, and production build pass.

## Product summary

RepoReveal analyzes public Python GitHub repositories without executing code. It builds a file-level dependency graph, ranks important files, detects entry points, and answers grounded questions via hybrid retrieval + LLM.

## Architectural decisions

| Decision | Choice | Rationale |
|---|---|---|
| Monorepo layout | `frontend/`, `backend/`, `docs/`, `examples/` | Matches suggested structure; keeps deploy units clear |
| Backend package manager | `uv`/`pip` via `pyproject.toml` | Standard FastAPI packaging; single lock-friendly file |
| Frontend bootstrap | Next.js App Router + TypeScript strict + Tailwind + shadcn/ui | Spec requirement; Client Components only where interactive |
| DB | PostgreSQL 16 + `pgvector` | Vector similarity for embeddings + relational analysis data |
| Async DB driver | SQLAlchemy 2 + asyncpg | Matches FastAPI async handlers |
| Background work | FastAPI `BackgroundTasks` | Personal project; document restart-loss limitation |
| CPU-heavy AST | `asyncio.to_thread` | Avoid blocking the event loop |
| Graph library | NetworkX in analyzer; React Flow + Dagre in UI | Separation of analysis vs visualization |
| AI | OpenAI SDK; skip when `AI_ENABLED=false` or no key | App remains useful without AI |
| Caching | Unique `(repository_id, commit_sha, analyzer_version)` | Reuse completed analyses |
| Auth | None | Out of scope |
| Queue/Redis/Celery | None | Out of scope; keep finishable |

## Assumptions

1. Default branch only; no branch picker.
2. Python-only repositories; non-Python repos fail with a clear error.
3. Optional `GITHUB_TOKEN` for rate limits; unauthenticated GitHub API works for demos at lower limits.
4. Embedding dimension follows configured OpenAI embedding model (default `text-embedding-3-small` → 1536).
5. Analyzer version string bumps invalidate cache intentionally.
6. Demo repository URL defaults to a small public FastAPI-related repo; local `examples/demo_repository` powers unit/integration tests.
7. Windows PowerShell is a first-class local-dev path alongside Docker Compose.

## Resource limit defaults

| Variable | Default |
|---|---|
| `MAX_ARCHIVE_BYTES` | 50 MiB |
| `MAX_EXTRACTED_BYTES` | 150 MiB |
| `MAX_EXTRACTED_FILES` | 5,000 |
| `MAX_PYTHON_FILES` | 2,000 |
| `MAX_SINGLE_FILE_BYTES` | 1 MiB |
| `ANALYSIS_TIMEOUT_SECONDS` | 300 |
| `AI_MAX_CONTEXT_CHARS` | 24,000 |
| `AI_MAX_RETRIEVED_CHUNKS` | 12 |

## Implementation phases

### Phase 1 — Foundation
Scaffold backend/frontend, Docker Compose (Postgres+pgvector, API, web), env example, health endpoint, SQLAlchemy models, Alembic initial migration. Verify containers/health.

### Phase 2 — Repository acquisition
GitHub URL validation/normalization, metadata + commit SHA, archive download, safe extraction with path/symlink/size guards, unit tests.

### Phase 3 — Static analyzer
Scanner, AST parser, module resolver, graph builder, entry points, classification, metrics/importance, change-impact traversal, demo fixture, extensive unit tests.

### Phase 4 — Persistence & API
Persist analysis artifacts, background pipeline, polling, graph/files/impact endpoints, cache-by-commit, typed errors.

### Phase 5 — Core frontend
Landing page, URL form, progress polling, results workspace (Overview + Files + details), dark/light mode.

### Phase 6 — Architecture graph
React Flow graph, Dagre layout, filters, node limit, details panel.

### Phase 7 — AI indexing & overview
AST chunking, embeddings, pgvector, overview generation, AI-disabled fallback.

### Phase 8 — AI Q&A & explanations
Hybrid retrieval, graph expansion, citation validation, file explain + ask endpoints + UI.

### Phase 9 — Polish
Docs, CI, accessibility, final lint/test/build verification.

## Verification gates

After each major phase: run relevant unit tests, lint (Ruff / ESLint), typecheck (Mypy / `tsc`), and Docker/build checks where applicable. Fix failures before advancing.

## Out of scope (explicit non-goals)

Auth, private repos, multi-language, Redis/Celery/Kafka/K8s, microservices, billing, PR automation, browser IDE.
