"""Small shared normalization primitives used across FlowGuard owners.

These functions preserve the exact behavior of the formerly repeated private
helpers.  They own no route, state, side effect, validation, or public API.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from typing import Any


def canonical_json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def nonempty_string_sequence(
    values: Sequence[str] | None,
) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values if str(value))


def string_tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,) if values else ()
    return tuple(str(value) for value in values if str(value))


def string_sequence(values: Sequence[str] | None) -> tuple[str, ...]:
    """Preserve every supplied sequence position while coercing it to text."""

    if values is None:
        return ()
    return tuple(str(value) for value in values)


def string_set(values: Sequence[str]) -> set[str]:
    return {str(value) for value in values}


def unique_strings(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def unique_sorted_strings(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


__all__ = [
    "canonical_json_text",
    "nonempty_string_sequence",
    "string_sequence",
    "string_set",
    "string_tuple",
    "unique_sorted_strings",
    "unique_strings",
]
