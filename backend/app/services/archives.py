"""Safe archive download extraction for untrusted repository content."""

from __future__ import annotations

import io
import logging
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.core.exceptions import InvalidArchiveError, RepositoryTooLargeError
from app.core.security import is_safe_relative_path

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ExtractionResult:
    root: Path
    file_count: int
    total_bytes: int


def _strip_first_component(member_name: str) -> str:
    normalized = member_name.replace("\\", "/").lstrip("/")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if not parts:
        return ""
    # GitHub archives nest under owner-repo-sha/
    if len(parts) == 1:
        return ""
    return "/".join(parts[1:])


def extract_archive(
    data: bytes,
    destination: Path,
    *,
    max_extracted_bytes: int,
    max_extracted_files: int,
    filename_hint: str = "archive.tar.gz",
) -> ExtractionResult:
    """Extract a GitHub source archive with path-traversal and size guards."""
    destination.mkdir(parents=True, exist_ok=True)
    hint = filename_hint.lower()

    if hint.endswith(".zip"):
        return _extract_zip(
            data,
            destination,
            max_extracted_bytes=max_extracted_bytes,
            max_extracted_files=max_extracted_files,
        )
    return _extract_tar(
        data,
        destination,
        max_extracted_bytes=max_extracted_bytes,
        max_extracted_files=max_extracted_files,
    )


def _extract_tar(
    data: bytes,
    destination: Path,
    *,
    max_extracted_bytes: int,
    max_extracted_files: int,
) -> ExtractionResult:
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
            members = archive.getmembers()
            file_count = 0
            total_bytes = 0
            for member in members:
                if member.issym() or member.islnk():
                    raise InvalidArchiveError("Archives containing symlinks are not allowed.")
                if not member.isfile() and not member.isdir():
                    continue

                relative = _strip_first_component(member.name)
                if not relative:
                    continue
                if not is_safe_relative_path(relative):
                    raise InvalidArchiveError(f"Unsafe archive path rejected: {member.name}")

                target = destination / relative
                if not str(target.resolve()).startswith(str(destination.resolve())):
                    raise InvalidArchiveError(f"Path traversal rejected: {member.name}")

                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue

                file_count += 1
                if file_count > max_extracted_files:
                    raise RepositoryTooLargeError(
                        details={"max_extracted_files": max_extracted_files}
                    )

                size = int(member.size or 0)
                total_bytes += size
                if total_bytes > max_extracted_bytes:
                    raise RepositoryTooLargeError(
                        details={"max_extracted_bytes": max_extracted_bytes}
                    )

                target.parent.mkdir(parents=True, exist_ok=True)
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                with extracted, target.open("wb") as out:
                    out.write(extracted.read())

            return ExtractionResult(
                root=destination, file_count=file_count, total_bytes=total_bytes
            )
    except (tarfile.TarError, OSError) as exc:
        raise InvalidArchiveError("Downloaded archive is invalid or corrupt.") from exc


def _extract_zip(
    data: bytes,
    destination: Path,
    *,
    max_extracted_bytes: int,
    max_extracted_files: int,
) -> ExtractionResult:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            file_count = 0
            total_bytes = 0
            for info in archive.infolist():
                # Reject symlink-like entries (external attr / Unix mode)
                if info.external_attr >> 16 & 0o120000 == 0o120000:
                    raise InvalidArchiveError("Archives containing symlinks are not allowed.")

                relative = _strip_first_component(info.filename)
                if not relative:
                    continue
                if not is_safe_relative_path(relative):
                    raise InvalidArchiveError(f"Unsafe archive path rejected: {info.filename}")

                target = destination / relative
                if not str(target.resolve()).startswith(str(destination.resolve())):
                    raise InvalidArchiveError(f"Path traversal rejected: {info.filename}")

                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue

                file_count += 1
                if file_count > max_extracted_files:
                    raise RepositoryTooLargeError(
                        details={"max_extracted_files": max_extracted_files}
                    )

                total_bytes += int(info.file_size)
                if total_bytes > max_extracted_bytes:
                    raise RepositoryTooLargeError(
                        details={"max_extracted_bytes": max_extracted_bytes}
                    )

                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, target.open("wb") as out:
                    out.write(src.read())

            return ExtractionResult(
                root=destination, file_count=file_count, total_bytes=total_bytes
            )
    except zipfile.BadZipFile as exc:
        raise InvalidArchiveError("Downloaded archive is invalid or corrupt.") from exc
