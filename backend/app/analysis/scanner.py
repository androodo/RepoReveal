"""Repository file scanning without executing code."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

IGNORE_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "site-packages",
    "vendor",
}

INTERESTING_NON_PYTHON = {
    "README.md",
    "README.rst",
    "pyproject.toml",
    "setup.cfg",
    "requirements.txt",
    "pytest.ini",
    "tox.ini",
}


@dataclass(slots=True)
class ScannedFile:
    path: str
    absolute_path: Path
    size_bytes: int
    is_python: bool


@dataclass(slots=True)
class ScanResult:
    files: list[ScannedFile] = field(default_factory=list)
    python_files: list[ScannedFile] = field(default_factory=list)
    metadata_files: list[ScannedFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def scan_repository(
    root: Path,
    *,
    max_python_files: int,
    max_single_file_bytes: int,
    max_extracted_files: int,
) -> ScanResult:
    result = ScanResult()
    if not root.exists():
        result.warnings.append("Repository root does not exist.")
        return result

    total_files = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            relative_parts = path.relative_to(root).parts
        except ValueError:
            continue

        if any(part in IGNORE_DIR_NAMES for part in relative_parts[:-1]):
            continue

        total_files += 1
        if total_files > max_extracted_files:
            result.warnings.append("File count limit reached while scanning.")
            break

        rel = path.relative_to(root).as_posix()
        size = path.stat().st_size
        name = path.name
        is_python = path.suffix == ".py"
        is_meta = name in INTERESTING_NON_PYTHON or name.upper() in {
            "README.MD",
            "README.RST",
        }

        if not is_python and not is_meta:
            continue

        if size > max_single_file_bytes:
            result.warnings.append(f"Skipped oversized file: {rel}")
            continue

        scanned = ScannedFile(
            path=rel,
            absolute_path=path,
            size_bytes=size,
            is_python=is_python,
        )
        result.files.append(scanned)
        if is_python:
            result.python_files.append(scanned)
            if len(result.python_files) > max_python_files:
                from app.core.exceptions import RepositoryTooLargeError

                raise RepositoryTooLargeError(
                    message="Too many Python files for analysis.",
                    details={"max_python_files": max_python_files},
                )
        else:
            result.metadata_files.append(scanned)

    return result
