# AI Retrieval

RepoReveal’s AI features are optional. Without `OPENAI_API_KEY` (or with `AI_ENABLED=false`), deterministic analysis, graph exploration, files, and change impact remain fully usable.

## AST-aware chunking

Preferred chunks:

- module overview (docstring, imports, symbol names)
- one top-level function per chunk
- one class per chunk
- module-level definitions
- bounded line windows for oversized symbols

Chunks store file path, symbol, line range, content, search text, and optional embedding.

Obvious secret-like content is skipped.

## Embeddings

When AI is enabled, chunk embeddings are generated with the configured OpenAI embedding model and stored in pgvector.

## Hybrid retrieval

1. **Query analysis** — extract path, symbol, and concept terms locally
2. **Candidate retrieval** — keyword/text match + vector similarity + exact path/symbol bonuses
3. **Graph expansion** — add limited direct dependencies, dependents, and related tests for top files
4. **Reranking**

```text
final_score =
    semantic_similarity
  + lexical_match
  + exact_symbol_bonus
  + exact_path_bonus
  + graph_neighbor_bonus
```

5. **Context construction** — bounded characters/chunks; never the whole repository
6. **Grounded answer** — structured JSON with citations

## Citation validation

Returned citations are validated against:

- known repository file paths
- retrieved chunk line ranges / overlap

Fabricated citations are discarded. If evidence is insufficient after validation, RepoReveal returns a careful fallback message.

## Hallucination limitations

LLMs can still mis-summarize retrieved text. RepoReveal reduces risk by:

- restricting context to retrieved evidence
- validating citations
- keeping deterministic graph/file analysis authoritative
- avoiding whole-repository prompts
