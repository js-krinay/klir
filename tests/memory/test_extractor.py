"""Tests for memory extraction from session summaries."""

from __future__ import annotations

from klir.memory.extractor import (
    format_exchanges,
    parse_extraction_response,
)


def test_parse_extraction_response_single() -> None:
    """Parse a single memory from LLM response."""
    response = """
```memory
abstract: User prefers dark mode in all editors
category: preferences
---
User has explicitly requested dark mode for VS Code, terminal, and all
development tools. Apply dark themes by default.
```
"""
    candidates = parse_extraction_response(response)
    assert len(candidates) == 1
    assert candidates[0].abstract == "User prefers dark mode in all editors"
    assert candidates[0].category == "preferences"
    assert "dark mode" in candidates[0].content


def test_parse_extraction_response_multiple() -> None:
    """Parse multiple memories from LLM response."""
    response = """
```memory
abstract: User is a staff engineer at Acme Corp
category: profile
---
Staff-level backend engineer, 10 years experience.
```

```memory
abstract: Always run migrations before deploying
category: patterns
---
The team has a strict deploy process: migrations first, then deploy.
```
"""
    candidates = parse_extraction_response(response)
    assert len(candidates) == 2
    assert candidates[0].category == "profile"
    assert candidates[1].category == "patterns"


def test_parse_extraction_response_empty() -> None:
    """Empty or garbage input returns no candidates."""
    assert parse_extraction_response("") == []
    assert parse_extraction_response("No memories to extract.") == []
    assert parse_extraction_response("```python\nprint('hi')\n```") == []


def test_parse_extraction_response_invalid_category() -> None:
    """Invalid category is normalized to 'cases'."""
    response = """
```memory
abstract: Something happened
category: invalid_category
---
Content here.
```
"""
    candidates = parse_extraction_response(response)
    assert len(candidates) == 1
    assert candidates[0].category == "cases"


# --- format_exchanges tests ---


def test_format_exchanges_basic() -> None:
    """Formats message+response pairs."""
    exchanges = [
        ("How do I run tests?", "Use pytest with strict markers."),
        ("What about coverage?", "Add --cov flag for coverage reports."),
    ]
    result = format_exchanges(exchanges)
    assert "Exchange 1" in result
    assert "Exchange 2" in result
    assert "How do I run tests?" in result
    assert "pytest" in result


def test_format_exchanges_truncates_long_responses() -> None:
    """Long responses are truncated."""
    exchanges = [("short", "x" * 2000)]
    result = format_exchanges(exchanges)
    assert result.endswith("...")
    assert len(result) < 1200  # 1000 char limit + overhead


def test_format_exchanges_empty() -> None:
    """Empty list produces empty string."""
    assert format_exchanges([]) == ""
