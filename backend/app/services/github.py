"""GitHub API client for public repository metadata and archives."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import (
    AppError,
    GitHubRateLimitError,
    GitHubTimeoutError,
    RepositoryEmptyError,
    RepositoryNotFoundError,
    RepositoryPrivateError,
    RepositoryTooLargeError,
)
from app.services.github_urls import ParsedGitHubUrl

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GitHubRepositoryMeta:
    owner: str
    name: str
    full_name: str
    github_url: str
    description: str | None
    default_branch: str
    primary_language: str | None
    stars: int
    is_archived: bool
    is_private: bool
    size_kb: int


@dataclass(slots=True)
class GitHubCommitRef:
    sha: str
    branch: str


class GitHubClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._owns_client = client is None
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": settings.github_api_version,
            "User-Agent": "RepoReveal/0.1",
        }
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        self._client = client or httpx.AsyncClient(
            base_url=settings.github_api_base_url.rstrip("/"),
            headers=headers,
            timeout=settings.github_timeout_seconds,
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_repository(self, parsed: ParsedGitHubUrl) -> GitHubRepositoryMeta:
        data = await self._request_json("GET", f"/repos/{parsed.owner}/{parsed.name}")
        if data.get("private"):
            raise RepositoryPrivateError()
        default_branch = data.get("default_branch") or "main"
        return GitHubRepositoryMeta(
            owner=data.get("owner", {}).get("login", parsed.owner),
            name=data.get("name", parsed.name),
            full_name=data.get("full_name", parsed.full_name),
            github_url=data.get("html_url", parsed.github_url),
            description=data.get("description"),
            default_branch=default_branch,
            primary_language=data.get("language"),
            stars=int(data.get("stargazers_count") or 0),
            is_archived=bool(data.get("archived")),
            is_private=bool(data.get("private")),
            size_kb=int(data.get("size") or 0),
        )

    async def resolve_commit(self, parsed: ParsedGitHubUrl, branch: str) -> GitHubCommitRef:
        data = await self._request_json(
            "GET", f"/repos/{parsed.owner}/{parsed.name}/commits/{branch}"
        )
        sha = data.get("sha")
        if not sha:
            raise RepositoryEmptyError()
        return GitHubCommitRef(sha=sha, branch=branch)

    async def download_tarball(self, parsed: ParsedGitHubUrl, commit_sha: str) -> bytes:
        url = f"/repos/{parsed.owner}/{parsed.name}/tarball/{commit_sha}"
        try:
            async with self._client.stream("GET", url) as response:
                self._raise_for_status(response)
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > self._settings.max_archive_bytes:
                        raise RepositoryTooLargeError(
                            details={"max_archive_bytes": self._settings.max_archive_bytes}
                        )
                    chunks.append(chunk)
                if total == 0:
                    raise RepositoryEmptyError()
                return b"".join(chunks)
        except httpx.TimeoutException as exc:
            raise GitHubTimeoutError() from exc

    async def _request_json(self, method: str, path: str) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path)
        except httpx.TimeoutException as exc:
            raise GitHubTimeoutError() from exc
        self._raise_for_status(response)
        payload = response.json()
        if not isinstance(payload, dict):
            raise AppError("GITHUB_ERROR", "Unexpected GitHub API response.", status_code=502)
        return payload

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code == 404:
            raise RepositoryNotFoundError()
        if response.status_code == 403 and "rate limit" in response.text.lower():
            raise GitHubRateLimitError()
        if response.status_code == 403:
            # Could be private without auth appearing as 404, but keep generic private message
            raise RepositoryPrivateError()
        if response.status_code >= 400:
            raise AppError(
                "GITHUB_ERROR",
                "GitHub API request failed.",
                status_code=502,
                details={"status_code": response.status_code},
            )
