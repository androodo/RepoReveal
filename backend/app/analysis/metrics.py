"""File classification, complexity, and importance scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from app.analysis.parser import ParseResult

CATEGORIES = [
    "Entry Point",
    "API / Routes",
    "Services",
    "Models / Data",
    "Core / Domain",
    "Configuration",
    "CLI",
    "Scripts",
    "Tests",
    "Utilities",
    "Migrations",
    "Other",
]

CATEGORY_BONUS = {
    "Entry Point": 20,
    "API / Routes": 12,
    "Services": 10,
    "Models / Data": 8,
    "Core / Domain": 10,
    "Configuration": 6,
    "CLI": 8,
    "Scripts": 4,
    "Tests": 2,
    "Utilities": 4,
    "Migrations": 3,
    "Other": 0,
}


@dataclass(slots=True)
class Classification:
    category: str
    reasons: list[str] = field(default_factory=list)
    is_test: bool = False


def is_test_path(path: str) -> bool:
    pure = PurePosixPath(path)
    parts_l = [p.lower() for p in pure.parts]
    name = pure.name.lower()
    if "tests" in parts_l or "test" in parts_l:
        return True
    return name.startswith("test_") or name.endswith("_test.py")


def classify_file(
    path: str,
    parse: ParseResult,
    *,
    is_entry_point: bool,
    external_imports: list[str],
) -> Classification:
    reasons: list[str] = []
    pure = PurePosixPath(path)
    parts_l = [p.lower() for p in pure.parts]
    name = pure.name.lower()
    externals = {e.split(".")[0] for e in external_imports}

    if is_test_path(path):
        return Classification(
            category="Tests", reasons=["Path or filename indicates a test module"], is_test=True
        )

    if is_entry_point:
        reasons.append("Detected as an entry point")
        return Classification(category="Entry Point", reasons=reasons, is_test=False)

    if "migrations" in parts_l or name.startswith("0") and "alembic" in "/".join(parts_l):
        return Classification(
            category="Migrations", reasons=["Path indicates database migrations"], is_test=False
        )

    if any(p in parts_l for p in ("api", "routes", "routers", "views", "endpoints")):
        reasons.append("Directory suggests API / routing layer")
        return Classification(category="API / Routes", reasons=reasons)

    if any(p in parts_l for p in ("services", "service", "use_cases", "usecases")):
        reasons.append("Directory suggests service layer")
        return Classification(category="Services", reasons=reasons)

    if any(
        p in parts_l for p in ("models", "schemas", "entities", "db", "database", "repositories")
    ):
        reasons.append("Directory suggests models / data access")
        return Classification(category="Models / Data", reasons=reasons)

    if any(p in parts_l for p in ("core", "domain", "business")):
        reasons.append("Directory suggests core / domain logic")
        return Classification(category="Core / Domain", reasons=reasons)

    if any(p in parts_l for p in ("config", "settings", "conf")) or name in {
        "config.py",
        "settings.py",
        "configuration.py",
    }:
        reasons.append("Path or filename indicates configuration")
        return Classification(category="Configuration", reasons=reasons)

    if any(p in parts_l for p in ("cli", "commands")) or name in {"cli.py", "commands.py"}:
        reasons.append("Path indicates CLI tooling")
        return Classification(category="CLI", reasons=reasons)

    if "scripts" in parts_l:
        reasons.append("Located under scripts/")
        return Classification(category="Scripts", reasons=reasons)

    if any(p in parts_l for p in ("utils", "util", "helpers", "common")):
        reasons.append("Directory suggests utilities")
        return Classification(category="Utilities", reasons=reasons)

    decorators = {d for s in parse.symbols for d in s.decorators}
    if any(
        d.endswith("route") or d.endswith("get") or d.endswith("post") or "router" in d.lower()
        for d in decorators
    ):
        reasons.append("Route-like decorators detected")
        return Classification(category="API / Routes", reasons=reasons)

    if {"fastapi", "flask", "starlette"} & externals and any(
        "router" in s.name.lower() or "route" in s.name.lower() for s in parse.symbols
    ):
        reasons.append("Web framework imports with route symbols")
        return Classification(category="API / Routes", reasons=reasons)

    if {"sqlalchemy", "django", "tortoise", "peewee"} & externals:
        reasons.append("ORM / data library imports")
        return Classification(category="Models / Data", reasons=reasons)

    return Classification(category="Other", reasons=["No strong structural signal"], is_test=False)


def compute_importance(
    *,
    incoming: int,
    outgoing: int,
    is_entry_point: bool,
    symbol_count: int,
    category: str,
) -> tuple[float, str]:
    """
    Importance formula (documented, transparent):

        raw =
            incoming * 4.0
          + outgoing * 1.0
          + entry_bonus(25 if entry else 0)
          + min(symbol_count, 20) * 1.5
          + category_bonus

        importance = clamp(raw, 0, 100)

    Incoming dependencies weigh more because widely-imported modules are central.
    """
    entry_bonus = 25.0 if is_entry_point else 0.0
    category_bonus = float(CATEGORY_BONUS.get(category, 0))
    raw = (
        incoming * 4.0 + outgoing * 1.0 + entry_bonus + min(symbol_count, 20) * 1.5 + category_bonus
    )
    score = max(0.0, min(100.0, raw))
    sentence = (
        f"Imported by {incoming} internal module{'s' if incoming != 1 else ''}"
        f" with {outgoing} outgoing dependency edge{'s' if outgoing != 1 else ''}"
    )
    if is_entry_point:
        sentence += " and detected as an application entry point"
    sentence += f" (category: {category})."
    return score, sentence
