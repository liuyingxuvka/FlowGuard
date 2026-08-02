"""Small shared normalization primitives used across FlowGuard owners.

These functions preserve the exact behavior of the formerly repeated private
helpers.  They own no route, state, side effect, validation, or public API.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def string_tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,) if values else ()
    return tuple(str(value) for value in values if str(value))


def unique_strings(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


__all__ = ["string_tuple", "unique_strings"]
