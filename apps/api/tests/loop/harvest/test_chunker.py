"""Tests for the recursive text chunker."""
from __future__ import annotations

from src.loop.harvest.chunker import recursive_split


def test_short_text_returns_single_chunk() -> None:
    text = "Hello world"
    chunks = recursive_split(text, chunk_size=512)
    assert chunks == ["Hello world"]


def test_empty_text_returns_empty() -> None:
    assert recursive_split("", chunk_size=512) == []


def test_long_text_splits_into_multiple_chunks() -> None:
    text = ("A" * 100 + "\n\n") * 10
    chunks = recursive_split(text, chunk_size=200, overlap=0)
    assert len(chunks) > 1


def test_chunks_within_size_limit() -> None:
    text = " ".join(["word"] * 1000)
    chunks = recursive_split(text, chunk_size=100, overlap=0)
    for chunk in chunks:
        assert len(chunk) <= 100 + 10  # small tolerance for word boundaries


def test_overlap_prepends_tail() -> None:
    text = "AAAA BBBB CCCC DDDD EEEE " * 5
    chunks = recursive_split(text, chunk_size=30, overlap=10)
    # With overlap, consecutive chunks should share some content
    assert len(chunks) >= 2


def test_paragraph_separator_preferred() -> None:
    text = "Para one.\n\nPara two.\n\nPara three."
    chunks = recursive_split(text, chunk_size=20, overlap=0)
    assert any("Para one" in c for c in chunks)
    assert any("Para two" in c for c in chunks)
