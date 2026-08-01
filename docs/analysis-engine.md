# Analysis Engine

RepoReveal’s analyzer inspects repository text only. It never imports, installs, or executes analyzed code.

## AST parsing

Each `.py` file is parsed independently with Python’s built-in `ast.parse`.

- Syntax errors become per-file warnings
- Repository analysis continues
- Extracted data includes docstrings, imports, top-level functions/classes, decorators, `__main__` blocks, and framework hints

## Module resolution

Paths become dotted module names:

```text
app/services/users.py → app.services.users
src/project/api.py → project.api
```

Supported layouts:

- package at repository root
- `src/` layout

Supported import forms:

- `import package.module`
- `from package import module`
- `from package.module import name`
- relative imports (`from .`, `from ..`)

Only resolved internal imports become graph edges. External/unresolved imports are stored separately.

## Dependency graph

A directed edge means:

```text
source file imports target file
```

NetworkX is used for traversal helpers. The API returns a bounded subgraph suitable for visualization.

## Entry-point detection

Heuristics (with stored reasons and confidence):

- filenames such as `main.py`, `app.py`, `manage.py`, `wsgi.py`, `asgi.py`, `__main__.py`
- `if __name__ == "__main__"`
- FastAPI / Flask / Typer / Click / Django patterns
- console script targets from `pyproject.toml`

## Estimated complexity

A lightweight structural score increments for:

- `if` / loops / `except`
- `match` cases
- conditional comprehensions
- boolean branches / ternary expressions

This is labeled **estimated complexity**, not true cyclomatic complexity.

## Importance score

```text
raw =
    incoming * 4.0
  + outgoing * 1.0
  + entry_bonus (25 if entry point else 0)
  + min(symbol_count, 20) * 1.5
  + category_bonus

importance = clamp(raw, 0, 100)
```

Incoming edges weigh more because widely imported modules are central. Category bonuses favor entry points, APIs, services, and domain modules.

## Change impact

Structural impact uses reverse dependency traversal to depth 2:

- direct dependents
- second-level dependents
- related tests
- affected entry points
- representative dependency paths

Language is careful: structural dependence is not a guarantee of runtime impact. AI does not choose the impacted file set.

## Limitations

- Python only
- Default branch only
- Static imports only (dynamic imports are unresolved)
- Heuristic entry-point and category detection
- Large repositories are rejected by configured limits
