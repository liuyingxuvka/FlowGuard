"""Small internal byte-fingerprint primitive."""

from __future__ import annotations

import hashlib


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


__all__ = ["sha256_bytes"]
