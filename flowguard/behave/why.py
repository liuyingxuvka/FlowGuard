"""Reprove a stored witness on current code; the cache is never its verdict."""

import json

from .engine import cache_root, prove
from .report import item_id


def why(root, identifier):
    if len(identifier) not in {6, 8} or identifier[:2] not in {"W-", "N-", "S-", "L-", "C-", "A-"} or any(char not in "0123456789abcdef" for char in identifier[2:]):
        raise ValueError("unknown witness id")
    path = cache_root(root) / "witnesses" / (identifier + ".json")
    try:
        candidate = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("no stored proof recipe for " + identifier) from exc
    if item_id(candidate["semantic"], length=len(identifier) - 2) != identifier:
        raise ValueError("stored witness semantic identity changed")
    return prove(root, candidate, persist=False)
