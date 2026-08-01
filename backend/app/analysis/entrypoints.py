"""Explainable entry-point detection heuristics."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from app.analysis.parser import ParseResult

ENTRY_FILENAMES = {
    "main.py",
    "app.py",
    "server.py",
    "cli.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "__main__.py",
}

FRAMEWORK_HINT_LABELS = {
    "fastapi_app": "Defines a FastAPI application instance",
    "flask_app": "Defines a Flask application instance",
    "typer_app": "Defines a Typer CLI application",
    "uvicorn_run": "Calls uvicorn.run",
    "click_command": "Defines Click commands",
    "django_management": "Django management entry patterns",
    "django_asgi": "Django ASGI application",
    "django_wsgi": "Django WSGI application",
}


@dataclass(slots=True)
class EntryPointResult:
    is_entry_point: bool
    confidence: str | None
    reasons: list[str] = field(default_factory=list)
    related_symbols: list[str] = field(default_factory=list)


def detect_entry_point(
    path: str,
    parse: ParseResult,
    *,
    script_targets: set[str] | None = None,
) -> EntryPointResult:
    reasons: list[str] = []
    symbols: list[str] = []
    name = PurePosixPath(path).name
    script_targets = script_targets or set()

    if name in ENTRY_FILENAMES:
        reasons.append(f"Filename matches common entry-point pattern ({name})")
    if parse.has_main_block:
        reasons.append('Contains if __name__ == "__main__" block')
    for hint in parse.framework_hints:
        label = FRAMEWORK_HINT_LABELS.get(hint, hint)
        reasons.append(label)
    module = path.replace("/", ".").removesuffix(".py")
    for target in script_targets:
        if target.endswith(module) or module.endswith(target.replace(":", ".").split(":")[0]):
            reasons.append(f"Referenced by console script target ({target})")
            break
        # module:attr style
        mod_part = target.split(":")[0]
        if path.endswith(mod_part.replace(".", "/") + ".py") or path.endswith(
            mod_part.replace(".", "/") + "/__init__.py"
        ):
            reasons.append(f"Referenced by console script ({target})")
            break

    for symbol in parse.symbols:
        if symbol.name in {"main", "cli", "app", "create_app", "get_application"}:
            symbols.append(symbol.name)
            reasons.append(f"Defines notable symbol `{symbol.name}`")

    if not reasons:
        return EntryPointResult(
            is_entry_point=False, confidence=None, reasons=[], related_symbols=[]
        )

    # Confidence heuristics
    high_markers = {
        'Contains if __name__ == "__main__" block',
        "Defines a FastAPI application instance",
        "Defines a Flask application instance",
        "Django ASGI application",
        "Django WSGI application",
    }
    if any(r in high_markers for r in reasons) or name in {
        "__main__.py",
        "manage.py",
        "wsgi.py",
        "asgi.py",
    }:
        confidence = "high"
    elif name in ENTRY_FILENAMES or any(
        r.startswith("Referenced by console script") for r in reasons
    ):
        confidence = "medium"
    else:
        confidence = "low"

    # de-dupe reasons
    deduped: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            deduped.append(reason)

    return EntryPointResult(
        is_entry_point=True,
        confidence=confidence,
        reasons=deduped,
        related_symbols=sorted(set(symbols)),
    )


def extract_console_scripts(pyproject_text: str | None) -> set[str]:
    """Parse [project.scripts] and [tool.poetry.scripts] targets from pyproject.toml text."""
    if not pyproject_text:
        return set()
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover
        return set()

    try:
        data = tomllib.loads(pyproject_text)
    except Exception:
        return set()

    targets: set[str] = set()
    project_scripts = (data.get("project") or {}).get("scripts") or {}
    poetry_scripts = ((data.get("tool") or {}).get("poetry") or {}).get("scripts") or {}
    for mapping in (project_scripts, poetry_scripts):
        if isinstance(mapping, dict):
            for value in mapping.values():
                if isinstance(value, str):
                    targets.add(value)
    return targets


_SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"api[_-]?key\s*=\s*['\"][A-Za-z0-9_\-]{20,}", re.I),
    re.compile(r"secret\s*=\s*['\"][^'\"]{12,}", re.I),
]


def looks_like_secret(content: str) -> bool:
    return any(pattern.search(content) for pattern in _SECRET_PATTERNS)
