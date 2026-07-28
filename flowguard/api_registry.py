"""Deterministic ownership for the package public-API name registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class PublicAPIRegistry:
    """One exact ordered public-name projection and its ownership findings."""

    names: tuple[str, ...]
    duplicate_names: tuple[str, ...]
    missing_names: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.duplicate_names and not self.missing_names


def build_public_api_registry(
    namespace: Mapping[str, Any],
    groups: Sequence[Sequence[str]],
) -> PublicAPIRegistry:
    names: list[str] = []
    seen: set[str] = set()
    duplicates: set[str] = set()
    for group in groups:
        for raw_name in group:
            name = str(raw_name)
            if name in seen:
                duplicates.add(name)
                continue
            seen.add(name)
            names.append(name)
    missing = tuple(name for name in names if name not in namespace)
    return PublicAPIRegistry(
        names=tuple(names),
        duplicate_names=tuple(sorted(duplicates)),
        missing_names=missing,
    )


def dedupe_public_names(*groups: Sequence[str]) -> list[str]:
    """Compatibility-preserving list projection used by ``flowguard.__all__``."""

    names: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for name in group:
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


__all__ = [
    "PublicAPIRegistry",
    "build_public_api_registry",
    "dedupe_public_names",
]
