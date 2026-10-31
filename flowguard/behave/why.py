"""Reprove a stored witness on current code; the cache is never its verdict."""

import json

from .engine import cache_root, prove
from .report import item_id


def why(root, identifier):
    if not identifier.startswith("W-") or len(identifier) != 18 or any(char not in "0123456789abcdef" for char in identifier[2:]):
        raise ValueError("unknown witness id")
    path = cache_root(root) / "witnesses" / (identifier + ".json")
    try:
        candidate = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("no stored proof recipe for " + identifier) from exc
    if item_id(candidate["semantic"]) != identifier:
        raise ValueError("stored witness semantic identity changed")
    return prove(root, candidate, persist=False)
