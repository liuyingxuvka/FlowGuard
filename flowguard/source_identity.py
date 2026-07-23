"""Stable repository-source identity across equivalent text checkouts."""

from __future__ import annotations

import hashlib
from pathlib import Path


CANONICAL_TEXT_SUFFIXES = frozenset(
    {
        ".json",
        ".md",
        ".py",
        ".toml",
        ".txt",
        ".yaml",
        ".yml",
    }
)


def canonical_source_bytes(path: str | Path) -> bytes:
    """Normalize text newlines while preserving non-text inputs byte-for-byte."""

    source = Path(path)
    payload = source.read_bytes()
    if source.suffix.casefold() not in CANONICAL_TEXT_SUFFIXES:
        return payload
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def source_file_fingerprint(path: str | Path) -> str:
    return f"sha256:{hashlib.sha256(canonical_source_bytes(path)).hexdigest()}"


__all__ = [
    "CANONICAL_TEXT_SUFFIXES",
    "canonical_source_bytes",
    "source_file_fingerprint",
]
