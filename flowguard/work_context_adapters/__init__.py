"""Built-in peer adapters for the provider-neutral WorkContext boundary."""

from __future__ import annotations

from ..work_context import (
    register_work_context_adapter,
    registered_work_context_adapter_ids,
)
from .declared_files import (
    DECLARED_FILE_SOURCE_PROFILES,
    DECLARED_PROFILE_CHANGELOG,
    DECLARED_PROFILE_OPENSPARK,
    DECLARED_PROFILE_SPARK,
    DeclaredFilesWorkContextAdapter,
    declared_files_source_profile,
)
from .openspec import OpenSpecWorkContextAdapter


def register_builtin_work_context_adapters() -> None:
    """Register each built-in peer without replacing an existing authority."""

    registered = set(registered_work_context_adapter_ids())
    for adapter in (
        OpenSpecWorkContextAdapter(),
        DeclaredFilesWorkContextAdapter(),
    ):
        if adapter.adapter_id not in registered:
            register_work_context_adapter(adapter)
            registered.add(adapter.adapter_id)


__all__ = [
    "DeclaredFilesWorkContextAdapter",
    "DECLARED_FILE_SOURCE_PROFILES",
    "DECLARED_PROFILE_CHANGELOG",
    "DECLARED_PROFILE_OPENSPARK",
    "DECLARED_PROFILE_SPARK",
    "OpenSpecWorkContextAdapter",
    "register_builtin_work_context_adapters",
    "declared_files_source_profile",
]
