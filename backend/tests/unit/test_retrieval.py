"""Unit tests for retrieval scoring and citation validation."""

from uuid import uuid4

from app.ai.retrieval import RetrievedChunk, analyze_query, validate_citations


def test_analyze_query_extracts_terms() -> None:
    result = analyze_query("Where is UserService authentication in app/security/tokens.py?")
    assert "UserService" in result["symbol_terms"] or "authentication" in result["concept_terms"]
    assert any(
        "tokens.py" in t or "app/security" in t
        for t in result["path_terms"] + result["concept_terms"]
    )


def test_validate_citations_discards_fabricated() -> None:
    chunk = RetrievedChunk(
        chunk_id=uuid4(),
        file_id=uuid4(),
        file_path="app/auth.py",
        symbol_name="login",
        line_start=10,
        line_end=40,
        content="def login():\n    pass\n",
        score=1.0,
    )
    citations = [
        {
            "file_path": "app/auth.py",
            "line_start": 12,
            "line_end": 20,
            "reason": "login handler",
        },
        {
            "file_path": "app/does_not_exist.py",
            "line_start": 1,
            "line_end": 2,
            "reason": "fabricated",
        },
    ]
    valid = validate_citations(
        citations,
        allowed_chunks=[chunk],
        known_paths={"app/auth.py"},
    )
    assert len(valid) == 1
    assert valid[0]["file_path"] == "app/auth.py"


def test_validate_citations_accepts_string_paths() -> None:
    chunk = RetrievedChunk(
        chunk_id=uuid4(),
        file_id=uuid4(),
        file_path="app/main.py",
        symbol_name="main",
        line_start=1,
        line_end=20,
        content="def main():\n    pass\n",
        score=1.0,
    )
    valid = validate_citations(
        ["app/main.py", "missing.py", 123],
        allowed_chunks=[chunk],
        known_paths={"app/main.py"},
    )
    assert len(valid) == 1
    assert valid[0]["file_path"] == "app/main.py"
    assert valid[0]["line_start"] == 1
