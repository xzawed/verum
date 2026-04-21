"""Recursive text chunker — splits long text into overlapping chunks."""
from __future__ import annotations

import re

_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def recursive_split(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
    separators: list[str] | None = None,
) -> list[str]:
    """Split text recursively by separator hierarchy.

    Tries to split on double-newlines first, then single newlines, then sentences,
    then words, then characters — whichever keeps chunks within chunk_size.
    """
    seps = separators if separators is not None else _SEPARATORS
    return _split(text, chunk_size, overlap, seps)


def _split(text: str, chunk_size: int, overlap: int, separators: list[str]) -> list[str]:
    if len(text) <= chunk_size:
        stripped = text.strip()
        return [stripped] if stripped else []

    sep = _pick_separator(text, separators, chunk_size)
    parts = text.split(sep) if sep else list(text)

    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = (current + sep + part).lstrip(sep) if current else part
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current.strip():
                chunks.append(current.strip())
            # part itself may be too long — recurse
            if len(part) > chunk_size:
                next_seps = separators[separators.index(sep) + 1:] if sep in separators else []
                chunks.extend(_split(part, chunk_size, overlap, next_seps or [""]))
                current = ""
            else:
                current = part

    if current.strip():
        chunks.append(current.strip())

    # Apply overlap: prepend tail of previous chunk to each chunk
    if overlap > 0 and len(chunks) > 1:
        overlapped: list[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-overlap:]
            overlapped.append((tail + " " + chunks[i]).strip())
        return overlapped

    return chunks


def _pick_separator(text: str, separators: list[str], chunk_size: int) -> str:
    for sep in separators:
        if sep == "":
            return sep
        parts = text.split(sep)
        # Good separator: produces multiple parts, most under chunk_size
        if len(parts) > 1 and any(len(p) <= chunk_size for p in parts):
            return sep
    return ""


_SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+')


def semantic_split(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
) -> list[str]:
    """Split text at sentence boundaries, grouping sentences until chunk_size.

    Overlap is applied by repeating the tail of the previous chunk.
    Fallback: if no sentence boundaries found, delegates to recursive_split.
    """
    sentences = _SENTENCE_ENDINGS.split(text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) <= 1:
        return recursive_split(text, chunk_size=chunk_size, overlap=overlap)

    chunks: list[str] = []
    current_sentences: list[str] = []
    current_len = 0

    for sentence in sentences:
        if current_len + len(sentence) + 1 > chunk_size and current_sentences:
            chunk = " ".join(current_sentences)
            chunks.append(chunk)
            # Keep last sentence as overlap seed
            tail = current_sentences[-1] if len(current_sentences[-1]) <= overlap else current_sentences[-1][-overlap:]
            current_sentences = [tail, sentence]
            current_len = len(tail) + len(sentence) + 1
        else:
            current_sentences.append(sentence)
            current_len += len(sentence) + 1

    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return [c for c in chunks if c.strip()]
