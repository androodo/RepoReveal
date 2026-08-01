"""Unit tests for GitHub URL parsing."""

import pytest

from app.core.exceptions import ValidationAppError
from app.services.github_urls import normalize_github_url, parse_github_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://github.com/owner/repository", "owner/repository"),
        ("https://github.com/owner/repository/", "owner/repository"),
        ("https://github.com/owner/repository.git", "owner/repository"),
        ("https://github.com/Owner-Name/repo.name", "Owner-Name/repo.name"),
    ],
)
def test_normalize_valid_urls(raw: str, expected: str) -> None:
    assert normalize_github_url(raw) == expected
    parsed = parse_github_url(raw)
    assert parsed.full_name == expected


@pytest.mark.parametrize(
    "raw",
    [
        "https://gitlab.com/owner/repo",
        "git@github.com:owner/repo.git",
        "https://github.com/owner/repo/issues/1",
        "https://github.com/owner/repo/pull/2",
        "https://github.com/owner/repo/blob/main/a.py",
        "https://example.com/file.zip",
        "not a url",
        "",
    ],
)
def test_reject_invalid_urls(raw: str) -> None:
    with pytest.raises(ValidationAppError):
        parse_github_url(raw)
