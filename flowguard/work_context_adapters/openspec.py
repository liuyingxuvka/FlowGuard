"""Read-only OpenSpec peer adapter for WorkContext."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from ..model_authority import SUBJECT_NORMATIVE_TARGET
from ..work_context import (
    WorkContext,
    _artifact_from_path,
    _bounded_path,
    _derived_artifact,
    _finalize_context,
    _string_tuple,
)


OPEN_SPEC_ADAPTER_ID = "openspec"
_TASK_PATTERN = re.compile(
    r"^\s*[-*]\s+\[(?P<state>[ xX])\]\s+",
    re.MULTILINE,
)


def _task_status(tasks_path: Path) -> tuple[str, int, int]:
    if not tasks_path.is_file():
        return "missing", 0, 0
    text = tasks_path.read_text(encoding="utf-8")
    states = tuple(
        match.group("state").casefold()
        for match in _TASK_PATTERN.finditer(text)
    )
    if not states:
        return "proposed", 0, 0
    completed = sum(state == "x" for state in states)
    if completed == len(states):
        return "complete", len(states), completed
    if completed:
        return "in-progress", len(states), completed
    return "proposed", len(states), 0


class OpenSpecWorkContextAdapter:
    """Normalize one bounded OpenSpec change without taking provider authority."""

    adapter_id = OPEN_SPEC_ADAPTER_ID
    native_owner_id = "official-openspec"

    def discover(
        self,
        root: str | Path,
        declaration: Mapping[str, Any] | None = None,
    ) -> tuple[str, ...]:
        project_root = Path(root).expanduser().resolve()
        changes_root = project_root / "openspec" / "changes"
        if not changes_root.is_dir():
            return ()
        return tuple(
            path.name
            for path in sorted(changes_root.iterdir())
            if path.is_dir()
            and not path.name.startswith(".")
            and path.name != "archive"
        )

    def read(
        self,
        root: str | Path,
        native_work_id: str,
        declaration: Mapping[str, Any] | None = None,
    ) -> WorkContext:
        project_root = Path(root).expanduser().resolve()
        work_id = str(native_work_id).strip()
        if not work_id or Path(work_id).name != work_id:
            raise ValueError(
                "native_work_id must be one safe OpenSpec change directory name"
            )
        context_root = _bounded_path(
            project_root,
            project_root / "openspec" / "changes" / work_id,
            "OpenSpec context root",
        )
        artifacts = []
        for name, role in (
            ("proposal.md", "scope"),
            ("design.md", "design"),
            ("tasks.md", "task"),
        ):
            path = context_root / name
            if path.is_file():
                artifacts.append(
                    _artifact_from_path(
                        path,
                        project_root,
                        artifact_id=f"openspec:{work_id}:{role}:{name}",
                        role=role,
                    )
                )
        specs_root = context_root / "specs"
        if specs_root.is_dir():
            for path in sorted(specs_root.rglob("*.md")):
                if path.is_file():
                    artifacts.append(
                        _artifact_from_path(
                            path,
                            project_root,
                            artifact_id=(
                                f"openspec:{work_id}:requirement:"
                                f"{path.relative_to(project_root).as_posix()}"
                            ),
                            role="requirement",
                        )
                    )
        status, task_count, completed_task_count = _task_status(
            context_root / "tasks.md"
        )
        artifacts.append(
            _derived_artifact(
                artifact_id=f"openspec:{work_id}:status:derived",
                role="status",
                source_ref=f"openspec/changes/{work_id}/@derived-status",
                value={
                    "status": status,
                    "task_count": task_count,
                    "completed_task_count": completed_task_count,
                },
            )
        )
        declaration = dict(declaration or {})
        context = WorkContext(
            context_id=f"openspec:{work_id}",
            adapter_id=self.adapter_id,
            native_work_id=work_id,
            native_owner_id=self.native_owner_id,
            project_root=str(project_root),
            context_root=str(context_root),
            artifacts=tuple(artifacts),
            required_artifact_roles=_string_tuple(
                declaration.get(
                    "required_artifact_roles",
                    ("scope", "design", "requirement", "task", "status"),
                )
            ),
            behavior_source_surface_ids=_string_tuple(
                declaration.get("behavior_source_surface_ids", ())
            ),
            subject_lane=str(
                declaration.get("subject_lane", SUBJECT_NORMATIVE_TARGET)
            ),
            current=context_root.is_dir(),
            native_metadata={
                "status": status,
                "task_count": task_count,
                "completed_task_count": completed_task_count,
            },
        )
        return _finalize_context(context)


__all__ = ["OPEN_SPEC_ADAPTER_ID", "OpenSpecWorkContextAdapter"]
