"""Strict internal JSON primitive readers for model-authority records."""

from __future__ import annotations

from typing import Any

from .model_authority import ModelAuthorityError, _array


def wire_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ModelAuthorityError(f"{field_name} must be a JSON string")
    return value


def wire_boolean(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ModelAuthorityError(f"{field_name} must be a JSON boolean")
    return value


def wire_integer(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ModelAuthorityError(f"{field_name} must be a JSON integer")
    return value


def wire_strings(value: Any, field_name: str) -> tuple[str, ...]:
    return tuple(
        wire_string(item, f"{field_name} item")
        for item in _array(value, field_name)
    )


__all__ = ["wire_boolean", "wire_integer", "wire_string", "wire_strings"]
