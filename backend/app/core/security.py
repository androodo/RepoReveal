"""Security helpers for untrusted repository content."""

from pathlib import PurePosixPath


def is_safe_relative_path(path: str) -> bool:
    """Return True when path is a relative path without traversal or absolute roots."""
    if not path or path.startswith("/") or path.startswith("\\"):
        return False
    # Reject Windows drive letters
    if len(path) >= 2 and path[1] == ":":
        return False
    pure = PurePosixPath(path.replace("\\", "/"))
    if pure.is_absolute():
        return False
    parts = pure.parts
    if ".." in parts:
        return False
    return not any(part.startswith("/") for part in parts)
