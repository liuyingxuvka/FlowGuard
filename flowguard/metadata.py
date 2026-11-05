"""Deterministic metadata values shared by trace and native replay records."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

FrozenMetadata = tuple[tuple[str, Any], ...]


def freeze_metadata(metadata: Mapping[str, Any] | Iterable[tuple[str, Any]] | None) -> FrozenMetadata:
    """Return metadata as a deterministic tuple of key/value pairs."""
    if metadata is None:
        return ()
    pairs = tuple(metadata.items()) if isinstance(metadata, Mapping) else tuple(metadata)
    return tuple(sorted(((str(key), value) for key, value in pairs), key=lambda item: item[0]))
