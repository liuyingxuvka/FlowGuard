"""Read-only declared-files peer adapter for WorkContext."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from ..model_authority import SUBJECT_NORMATIVE_TARGET
from ..work_context import (
    WORK_CONTEXT_ARTIFACT_ROLES,
    WorkContext,
    _artifact_from_path,
    _bounded_path,
    _finalize_context,
    _string_tuple,
)


DECLARED_FILES_ADAPTER_ID = "declared-files"


class DeclaredFilesWorkContextAdapter:
    """Normalize an explicitly declared bounded file inventory."""

    adapter_id = DECLARED_FILES_ADAPTER_ID
    native_owner_id = "declared-native-provider"

    def discover(
        self,
        root: str | Path,
        declaration: Mapping[str, Any] | None = None,
    ) -> tuple[str, ...]:
        declaration = dict(declaration or {})
        work_id = str(declaration.get("native_work_id", "")).strip()
        return (work_id,) if work_id else ()

    def read(
        self,
        root: str | Path,
        native_work_id: str,
        declaration: Mapping[str, Any] | None = None,
    ) -> WorkContext:
        project_root = Path(root).expanduser().resolve()
        declaration = dict(declaration or {})
        work_id = str(
            native_work_id or declaration.get("native_work_id", "")
        ).strip()
        if not work_id:
            raise ValueError("declared-files adapter requires native_work_id")
        context_root = _bounded_path(
            project_root,
            project_root / str(declaration.get("context_root", ".")),
            "declared context root",
        )
        artifact_rows = declaration.get("artifacts", ())
        if not isinstance(artifact_rows, Sequence) or isinstance(
            artifact_rows,
            (str, bytes),
        ):
            raise ValueError("declared-files artifacts must be a sequence")
        artifacts = []
        for index, raw in enumerate(artifact_rows):
            if not isinstance(raw, Mapping):
                raise ValueError(
                    "declared-files artifact row must be a mapping"
                )
            row = dict(raw)
            role = str(row.get("artifact_role", "")).strip()
            relative = str(row.get("path", "")).strip()
            if role not in WORK_CONTEXT_ARTIFACT_ROLES or not relative:
                raise ValueError(
                    "declared-files artifact requires current role and path"
                )
            path = _bounded_path(
                project_root,
                context_root / relative,
                "artifact path",
            )
            if not path.is_file():
                continue
            artifact_id = str(row.get("artifact_id", "")).strip() or (
                f"{self.adapter_id}:{work_id}:{role}:{index}"
            )
            artifacts.append(
                _artifact_from_path(
                    path,
                    project_root,
                    artifact_id=artifact_id,
                    role=role,
                )
            )
        context = WorkContext(
            context_id=str(declaration.get("context_id", "")).strip()
            or f"{self.adapter_id}:{work_id}",
            adapter_id=self.adapter_id,
            native_work_id=work_id,
            native_owner_id=str(
                declaration.get("native_owner_id", self.native_owner_id)
            ),
            project_root=str(project_root),
            context_root=str(context_root),
            artifacts=tuple(artifacts),
            required_artifact_roles=_string_tuple(
                declaration.get("required_artifact_roles", ())
            ),
            behavior_source_surface_ids=_string_tuple(
                declaration.get("behavior_source_surface_ids", ())
            ),
            subject_lane=str(
                declaration.get("subject_lane", SUBJECT_NORMATIVE_TARGET)
            ),
            current=True,
            native_metadata=dict(
                declaration.get("native_metadata", {})
            ),
        )
        return _finalize_context(context)


__all__ = [
    "DECLARED_FILES_ADAPTER_ID",
    "DeclaredFilesWorkContextAdapter",
]
