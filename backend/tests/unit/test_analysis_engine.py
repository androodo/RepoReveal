"""Unit tests for the static analysis engine using the demo fixture."""

from pathlib import Path

from app.analysis.entrypoints import detect_entry_point, extract_console_scripts
from app.analysis.graph_builder import compute_change_impact
from app.analysis.metrics import classify_file, compute_importance, is_test_path
from app.analysis.module_resolver import build_module_map, path_to_module_name, resolve_import
from app.analysis.parser import ImportInfo, parse_python_source
from app.analysis.pipeline import run_static_analysis
from app.analysis.scanner import IGNORE_DIR_NAMES, scan_repository

DEMO_ROOT = Path(__file__).resolve().parents[3] / "examples" / "demo_repository"


def test_scanner_ignores_venv_keeps_tests(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "x.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text(
        "def test_a():\n    assert True\n", encoding="utf-8"
    )
    result = scan_repository(
        tmp_path,
        max_python_files=100,
        max_single_file_bytes=1_000_000,
        max_extracted_files=1000,
    )
    paths = {f.path for f in result.python_files}
    assert "app.py" in paths
    assert "tests/test_a.py" in paths
    assert not any(".venv" in p for p in paths)
    assert "venv" in IGNORE_DIR_NAMES


def test_syntax_error_isolated() -> None:
    result = parse_python_source("bad.py", "def oops(\n")
    assert result.parse_status == "error"
    assert result.parse_warning


def test_symbol_and_import_extraction() -> None:
    source = '''"""Module."""
import os
from demo_service.utils import ids

async def get_thing():
    return 1

class Thing:
    pass

if __name__ == "__main__":
    get_thing()
'''
    result = parse_python_source("mod.py", source)
    assert result.docstring == "Module."
    assert result.has_main_block
    names = {s.name for s in result.symbols}
    assert names == {"get_thing", "Thing"}
    assert any(i.module == "os" for i in result.imports)


def test_path_to_module_and_src_layout() -> None:
    assert path_to_module_name("src/demo_service/api/routes.py") == "demo_service.api.routes"
    assert path_to_module_name("app/services/users.py") == "app.services.users"
    module_map = build_module_map(
        [
            "src/demo_service/api/routes.py",
            "src/demo_service/api/helpers.py",
            "src/demo_service/services/users.py",
        ]
    )
    assert module_map.resolve_module("demo_service.api.routes")


def test_relative_and_absolute_resolution() -> None:
    module_map = build_module_map(
        [
            "src/demo_service/api/routes.py",
            "src/demo_service/api/helpers.py",
            "src/demo_service/models/user.py",
            "src/demo_service/services/users.py",
        ]
    )
    abs_imp = ImportInfo(
        module="demo_service.services.users",
        names=["UserService"],
        level=0,
        line_number=1,
        is_from=True,
        raw="from demo_service.services.users import UserService",
    )
    resolved = resolve_import("src/demo_service/api/routes.py", abs_imp, module_map)
    assert resolved[0].is_internal
    assert resolved[0].target_path == "src/demo_service/services/users.py"

    rel_imp = ImportInfo(
        module=None,
        names=["helpers"],
        level=1,
        line_number=2,
        is_from=True,
        raw="from . import helpers",
    )
    rel = resolve_import("src/demo_service/api/routes.py", rel_imp, module_map)
    assert rel[0].is_internal
    assert rel[0].target_path == "src/demo_service/api/helpers.py"

    ext = ImportInfo(
        module="fastapi",
        names=["APIRouter"],
        level=0,
        line_number=1,
        is_from=True,
        raw="from fastapi import APIRouter",
    )
    external = resolve_import("src/demo_service/api/routes.py", ext, module_map)
    assert not external[0].is_internal


def test_entry_point_and_scripts() -> None:
    pyproject = DEMO_ROOT.joinpath("pyproject.toml").read_text(encoding="utf-8")
    scripts = extract_console_scripts(pyproject)
    assert any("demo_service.main" in s for s in scripts)
    parse = parse_python_source(
        "src/demo_service/main.py",
        DEMO_ROOT.joinpath("src/demo_service/main.py").read_text(encoding="utf-8"),
    )
    entry = detect_entry_point("src/demo_service/main.py", parse, script_targets=scripts)
    assert entry.is_entry_point
    assert entry.confidence in {"high", "medium"}


def test_classification_complexity_importance() -> None:
    assert is_test_path("tests/test_users.py")
    parse = parse_python_source(
        "src/demo_service/api/routes.py",
        "from fastapi import APIRouter\nrouter=APIRouter()\n",
    )
    classification = classify_file(
        "src/demo_service/api/routes.py",
        parse,
        is_entry_point=False,
        external_imports=["fastapi"],
    )
    assert classification.category == "API / Routes"
    score, reason = compute_importance(
        incoming=11,
        outgoing=2,
        is_entry_point=True,
        symbol_count=5,
        category="Entry Point",
    )
    assert 0 <= score <= 100
    assert "entry point" in reason.lower()


def test_full_demo_pipeline_and_impact() -> None:
    bundle = run_static_analysis(
        DEMO_ROOT,
        max_python_files=200,
        max_single_file_bytes=1_000_000,
        max_extracted_files=1000,
    )
    assert bundle.statistics["python_file_count"] >= 8
    assert bundle.statistics["internal_dependency_edges"] >= 3
    assert any(f.is_entry_point for f in bundle.files)
    assert any(f.is_test for f in bundle.files)
    assert bundle.chunks

    users = "src/demo_service/services/users.py"
    impact = compute_change_impact(
        bundle.dependency_graph,
        users,
        entry_point_paths={f.path for f in bundle.files if f.is_entry_point},
        test_paths={f.path for f in bundle.files if f.is_test},
    )
    assert (
        "src/demo_service/api/routes.py" in impact.direct_dependents or users in bundle.file_index
    )
