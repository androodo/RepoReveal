"""Unit tests for safe archive extraction."""

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from app.core.exceptions import InvalidArchiveError, RepositoryTooLargeError
from app.core.security import is_safe_relative_path
from app.services.archives import extract_archive


def _make_tar(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def test_safe_relative_path() -> None:
    assert is_safe_relative_path("src/app.py")
    assert not is_safe_relative_path("../etc/passwd")
    assert not is_safe_relative_path("/etc/passwd")
    assert not is_safe_relative_path("C:/Windows/System32")


def test_extract_tar_strips_root_and_writes_files(tmp_path: Path) -> None:
    data = _make_tar(
        {
            "owner-repo-sha/README.md": b"hello",
            "owner-repo-sha/src/app.py": b"print(1)\n",
        }
    )
    result = extract_archive(
        data,
        tmp_path / "out",
        max_extracted_bytes=10_000,
        max_extracted_files=100,
    )
    assert (tmp_path / "out" / "README.md").read_text(encoding="utf-8") == "hello"
    assert (tmp_path / "out" / "src" / "app.py").exists()
    assert result.file_count == 2


def test_path_traversal_rejected(tmp_path: Path) -> None:
    data = _make_tar({"owner-repo-sha/../../evil.py": b"x"})
    with pytest.raises(InvalidArchiveError):
        extract_archive(
            data,
            tmp_path / "out",
            max_extracted_bytes=10_000,
            max_extracted_files=100,
        )


def test_file_limit(tmp_path: Path) -> None:
    members = {f"owner-repo-sha/f{i}.py": b"x" for i in range(5)}
    data = _make_tar(members)
    with pytest.raises(RepositoryTooLargeError):
        extract_archive(
            data,
            tmp_path / "out",
            max_extracted_bytes=10_000,
            max_extracted_files=3,
        )


def test_zip_symlink_rejected(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        info = zipfile.ZipInfo("owner-repo-sha/link")
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        archive.writestr(info, b"")
    with pytest.raises(InvalidArchiveError):
        extract_archive(
            buffer.getvalue(),
            tmp_path / "out",
            max_extracted_bytes=10_000,
            max_extracted_files=100,
            filename_hint="archive.zip",
        )
