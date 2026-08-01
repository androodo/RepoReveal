"""Integration tests with mocked GitHub/OpenAI HTTP."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import create_app

DEMO_ROOT = Path(__file__).resolve().parents[3] / "examples" / "demo_repository"


def _tar_from_demo() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for path in DEMO_ROOT.rglob("*"):
            if path.is_file():
                rel = path.relative_to(DEMO_ROOT).as_posix()
                arcname = f"owner-demo-sha/{rel}"
                archive.add(path, arcname=arcname)
    return buffer.getvalue()


class FakeGitHubClient:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self._archive = _tar_from_demo()

    async def aclose(self) -> None:
        return None

    async def get_repository(self, parsed: Any) -> Any:
        from app.services.github import GitHubRepositoryMeta

        return GitHubRepositoryMeta(
            owner=parsed.owner,
            name=parsed.name,
            full_name=parsed.full_name,
            github_url=parsed.github_url,
            description="Demo",
            default_branch="main",
            primary_language="Python",
            stars=1,
            is_archived=False,
            is_private=False,
            size_kb=10,
        )

    async def resolve_commit(self, parsed: Any, branch: str) -> Any:
        from app.services.github import GitHubCommitRef

        return GitHubCommitRef(sha="abc123def456", branch=branch)

    async def download_tarball(self, parsed: Any, commit_sha: str) -> bytes:
        return self._archive


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.asyncio
async def test_health() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_analysis_flow_with_mocks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    End-to-end-ish flow without a live database:
    exercise URL validation, fake GitHub acquisition, and static analysis on the demo archive.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "temp_dir", str(tmp_path))
    monkeypatch.setattr(settings, "ai_enabled", False)
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr("app.services.analyses.GitHubClient", FakeGitHubClient)
    monkeypatch.setattr("app.services.github.GitHubClient", FakeGitHubClient)

    from app.analysis.pipeline import run_static_analysis
    from app.services.archives import extract_archive
    from app.services.github_urls import parse_github_url

    parsed = parse_github_url("https://github.com/demo/service")
    client = FakeGitHubClient()
    meta = await client.get_repository(parsed)
    commit = await client.resolve_commit(parsed, meta.default_branch)
    archive = await client.download_tarball(parsed, commit.sha)
    out = tmp_path / "src"
    extract_archive(archive, out, max_extracted_bytes=50_000_000, max_extracted_files=5000)
    bundle = run_static_analysis(
        out,
        max_python_files=2000,
        max_single_file_bytes=1_000_000,
        max_extracted_files=5000,
    )
    assert bundle.statistics["python_file_count"] >= 8
    assert bundle.deterministic_summary["entry_points"]
    assert any(f.is_entry_point for f in bundle.files)

    # AI-disabled overview path
    assert settings.ai_available is False
