"""Small internal fingerprint helpers (pure, no stored authority)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CANONICAL_TEXT_SUFFIXES = frozenset({".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"})


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical_fingerprint(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(text.encode("utf-8"))


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
    return sha256_bytes(canonical_source_bytes(path))


__all__ = [
    "CANONICAL_TEXT_SUFFIXES",
    "canonical_fingerprint",
    "canonical_source_bytes",
    "sha256_bytes",
    "source_file_fingerprint",
]
