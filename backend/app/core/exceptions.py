"""Typed application errors with stable API codes."""

from typing import Any


class AppError(Exception):
    """Base application error exposed via the API error envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", *, details: Any = None) -> None:
        super().__init__("NOT_FOUND", message, status_code=404, details=details)


class ValidationAppError(AppError):
    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__("VALIDATION_ERROR", message, status_code=400, details=details)


class RepositoryNotFoundError(AppError):
    def __init__(self, message: str = "GitHub repository not found.") -> None:
        super().__init__("REPOSITORY_NOT_FOUND", message, status_code=404)


class RepositoryPrivateError(AppError):
    def __init__(self, message: str = "Private repositories are not supported.") -> None:
        super().__init__("REPOSITORY_PRIVATE", message, status_code=403)


class RepositoryEmptyError(AppError):
    def __init__(self, message: str = "Repository appears to be empty.") -> None:
        super().__init__("REPOSITORY_EMPTY", message, status_code=400)


class NoPythonFilesError(AppError):
    def __init__(self, message: str = "No Python files were found in this repository.") -> None:
        super().__init__("NO_PYTHON_FILES", message, status_code=400)


class RepositoryTooLargeError(AppError):
    def __init__(
        self,
        message: str = "This repository exceeds RepoReveal's current analysis limit.",
        *,
        details: Any = None,
    ) -> None:
        super().__init__("REPOSITORY_TOO_LARGE", message, status_code=400, details=details)


class GitHubRateLimitError(AppError):
    def __init__(self, message: str = "GitHub API rate limit exceeded. Try again later.") -> None:
        super().__init__("GITHUB_RATE_LIMIT", message, status_code=429)


class GitHubTimeoutError(AppError):
    def __init__(self, message: str = "Timed out while contacting GitHub.") -> None:
        super().__init__("GITHUB_TIMEOUT", message, status_code=504)


class InvalidArchiveError(AppError):
    def __init__(self, message: str = "Downloaded archive is invalid or unsafe.") -> None:
        super().__init__("INVALID_ARCHIVE", message, status_code=400)


class AnalysisTimeoutError(AppError):
    def __init__(self, message: str = "Analysis exceeded the configured timeout.") -> None:
        super().__init__("ANALYSIS_TIMEOUT", message, status_code=408)


class AiUnavailableError(AppError):
    def __init__(
        self,
        message: str = "AI features are unavailable. Configure OPENAI_API_KEY to enable them.",
    ) -> None:
        super().__init__("AI_UNAVAILABLE", message, status_code=503)


class InsufficientEvidenceError(AppError):
    def __init__(
        self,
        message: str = (
            "RepoReveal could not find enough repository evidence to answer confidently."
        ),
    ) -> None:
        super().__init__("INSUFFICIENT_EVIDENCE", message, status_code=422)
