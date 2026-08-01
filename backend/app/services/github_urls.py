"""GitHub repository URL validation and normalization."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.exceptions import ValidationAppError

_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_GITHUB_HTTPS_RE = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/?#]+?)(?:\.git)?/?$"
)


@dataclass(frozen=True, slots=True)
class ParsedGitHubUrl:
    owner: str
    name: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def github_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}"


def parse_github_url(raw: str) -> ParsedGitHubUrl:
    """Validate and normalize a public GitHub HTTPS repository URL to owner/name."""
    if raw is None:
        raise ValidationAppError("Repository URL is required.")

    value = raw.strip()
    if not value:
        raise ValidationAppError("Repository URL is required.")

    lower = value.lower()
    if lower.startswith("git@"):
        raise ValidationAppError("SSH URLs are not supported. Use https://github.com/owner/repo.")
    if "github.com" not in lower:
        raise ValidationAppError("Only github.com repository URLs are supported.")
    if any(
        marker in lower
        for marker in ("/issues", "/pull/", "/pulls", "/blob/", "/tree/", "/commit/", "/raw/")
    ):
        raise ValidationAppError(
            "Provide a repository root URL, not an issue, pull request, or file URL."
        )

    match = _GITHUB_HTTPS_RE.match(value)
    if not match:
        raise ValidationAppError(
            "Invalid GitHub URL. Expected https://github.com/owner/repository."
        )

    owner = match.group("owner")
    repo = match.group("repo")
    if repo.endswith(".git"):
        repo = repo[:-4]

    if not _OWNER_RE.match(owner):
        raise ValidationAppError("Invalid GitHub owner name.")
    if not _REPO_RE.match(repo) or repo in {".", ".."}:
        raise ValidationAppError("Invalid GitHub repository name.")

    return ParsedGitHubUrl(owner=owner, name=repo)


def normalize_github_url(raw: str) -> str:
    """Return canonical owner/repository form."""
    return parse_github_url(raw).full_name
