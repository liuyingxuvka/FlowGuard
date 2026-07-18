"""Read-only OpenSpec context for FlowGuard planning and modeling.

OpenSpec owns its proposal, design, specifications, tasks, status, validation,
and archive lifecycle. FlowGuard may read the authored artifacts as context,
but it does not open provider sessions, execute provider checks, cache their
results, issue receipts, or project provider execution ownership.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


SPEC_CONTEXT_SCHEMA = "flowguard.spec_context.v1"
SPEC_CONTEXT_PROVIDER = "openspec"
SPEC_CONTEXT_ROLE = "read_only_external"
_TASK_PATTERN = re.compile(r"^\s*[-*]\s+\[(?P<state>[ xX])\]\s+", re.MULTILINE)


def _wire_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class SpecContextArtifact:
    artifact_id: str
    artifact_kind: str
    relative_path: str
    content_hash: str
    size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_kind": self.artifact_kind,
            "relative_path": self.relative_path,
            "content_hash": self.content_hash,
            "size": self.size,
        }


@dataclass(frozen=True)
class SpecContext:
    context_id: str
    change_id: str
    project_root: str
    change_root: str
    status: str
    task_count: int
    completed_task_count: int
    artifacts: tuple[SpecContextArtifact, ...]
    provider_id: str = SPEC_CONTEXT_PROVIDER
    provider_role: str = SPEC_CONTEXT_ROLE
    read_only: bool = True
    current: bool = True
    context_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_spec_context",
            "schema_version": SPEC_CONTEXT_SCHEMA,
            "context_id": self.context_id,
            "provider_id": self.provider_id,
            "provider_role": self.provider_role,
            "read_only": self.read_only,
            "current": self.current,
            "change_id": self.change_id,
            "project_root": self.project_root,
            "change_root": self.change_root,
            "status": self.status,
            "task_count": self.task_count,
            "completed_task_count": self.completed_task_count,
            "artifacts": [item.to_dict() for item in self.artifacts],
            "context_hash": self.context_hash,
            "claim_boundary": (
                "This is read-only planning context. OpenSpec retains proposal, design, "
                "specification, task, status, validation, and archive authority. The "
                "context carries no session, cache, receipt, check owner, or execution authority."
            ),
        }


@dataclass(frozen=True)
class SpecContextFinding:
    code: str
    message: str
    relative_path: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "relative_path": self.relative_path,
        }


@dataclass(frozen=True)
class SpecContextReview:
    context: SpecContext
    findings: tuple[SpecContextFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def finding_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_spec_context_review",
            "schema_version": SPEC_CONTEXT_SCHEMA,
            "ok": self.ok,
            "status": "pass" if self.ok else "blocked",
            "context": self.context.to_dict(),
            "findings": [item.to_dict() for item in self.findings],
            "claim_boundary": self.context.to_dict()["claim_boundary"],
        }


def _artifact(path: Path, project_root: Path, change_id: str, kind: str) -> SpecContextArtifact:
    content = path.read_bytes()
    relative_path = path.relative_to(project_root).as_posix()
    return SpecContextArtifact(
        artifact_id=f"openspec:{change_id}:{kind}:{relative_path}",
        artifact_kind=kind,
        relative_path=relative_path,
        content_hash=_wire_hash(content),
        size=len(content),
    )


def _status_artifact(
    change_id: str,
    *,
    status: str,
    task_count: int,
    completed_task_count: int,
) -> SpecContextArtifact:
    content = _canonical_json(
        {
            "status": status,
            "task_count": task_count,
            "completed_task_count": completed_task_count,
        }
    ).encode("utf-8")
    return SpecContextArtifact(
        artifact_id=f"openspec:{change_id}:status:derived",
        artifact_kind="status",
        relative_path=f"openspec/changes/{change_id}/@derived-status",
        content_hash=_wire_hash(content),
        size=len(content),
    )


def _task_status(tasks_path: Path) -> tuple[str, int, int]:
    if not tasks_path.is_file():
        return "missing", 0, 0
    text = tasks_path.read_text(encoding="utf-8")
    states = tuple(match.group("state").casefold() for match in _TASK_PATTERN.finditer(text))
    if not states:
        return "proposed", 0, 0
    completed = sum(state == "x" for state in states)
    if completed == len(states):
        return "complete", len(states), completed
    if completed:
        return "in-progress", len(states), completed
    return "proposed", len(states), 0


def read_openspec_context(root: str | Path, change_id: str) -> SpecContext:
    project_root = Path(root).expanduser().resolve()
    normalized_change_id = str(change_id).strip()
    if not normalized_change_id or Path(normalized_change_id).name != normalized_change_id:
        raise ValueError("change_id must be one safe OpenSpec change directory name")
    change_root = project_root / "openspec" / "changes" / normalized_change_id
    artifact_rows: list[SpecContextArtifact] = []
    for name, kind in (
        ("proposal.md", "proposal"),
        ("design.md", "design"),
        ("tasks.md", "tasks"),
    ):
        path = change_root / name
        if path.is_file():
            artifact_rows.append(_artifact(path, project_root, normalized_change_id, kind))
    specs_root = change_root / "specs"
    if specs_root.is_dir():
        for path in sorted(specs_root.rglob("*.md")):
            if path.is_file():
                artifact_rows.append(
                    _artifact(path, project_root, normalized_change_id, "specification")
                )
    status, task_count, completed_task_count = _task_status(change_root / "tasks.md")
    artifact_rows.append(
        _status_artifact(
            normalized_change_id,
            status=status,
            task_count=task_count,
            completed_task_count=completed_task_count,
        )
    )
    identity: Mapping[str, Any] = {
        "schema_version": SPEC_CONTEXT_SCHEMA,
        "provider_id": SPEC_CONTEXT_PROVIDER,
        "provider_role": SPEC_CONTEXT_ROLE,
        "read_only": True,
        "change_id": normalized_change_id,
        "status": status,
        "task_count": task_count,
        "completed_task_count": completed_task_count,
        "artifacts": [item.to_dict() for item in artifact_rows],
    }
    context_hash = _wire_hash(_canonical_json(identity).encode("utf-8"))
    return SpecContext(
        context_id=f"openspec:{normalized_change_id}",
        change_id=normalized_change_id,
        project_root=str(project_root),
        change_root=str(change_root),
        status=status,
        task_count=task_count,
        completed_task_count=completed_task_count,
        artifacts=tuple(artifact_rows),
        current=change_root.is_dir(),
        context_hash=context_hash,
    )


def review_spec_context(context: SpecContext) -> SpecContextReview:
    findings: list[SpecContextFinding] = []
    if context.provider_id != SPEC_CONTEXT_PROVIDER:
        findings.append(
            SpecContextFinding("unsupported_spec_provider", "only official OpenSpec context is supported")
        )
    if context.provider_role != SPEC_CONTEXT_ROLE or context.read_only is not True:
        findings.append(
            SpecContextFinding(
                "spec_context_not_read_only",
                "OpenSpec may be consumed only as read-only external context",
            )
        )
    if not context.current:
        findings.append(
            SpecContextFinding("openspec_change_missing", "the requested OpenSpec change is absent")
        )
    kinds = {item.artifact_kind for item in context.artifacts}
    for required in ("proposal", "design", "tasks", "specification", "status"):
        if required not in kinds:
            findings.append(
                SpecContextFinding(
                    f"openspec_{required}_missing",
                    f"OpenSpec context is missing {required} material",
                )
            )
    if not context.context_hash.startswith("sha256:"):
        findings.append(
            SpecContextFinding("spec_context_hash_missing", "context needs a current content identity")
        )
    return SpecContextReview(context, tuple(findings))


def discover_openspec_contexts(root: str | Path) -> tuple[SpecContext, ...]:
    project_root = Path(root).expanduser().resolve()
    changes_root = project_root / "openspec" / "changes"
    if not changes_root.is_dir():
        return ()
    return tuple(
        read_openspec_context(project_root, path.name)
        for path in sorted(changes_root.iterdir())
        if path.is_dir() and not path.name.startswith(".")
    )


def read_spec_context(
    root: str | Path,
    change_id: str,
    *,
    provider_id: str = SPEC_CONTEXT_PROVIDER,
) -> SpecContext:
    if provider_id != SPEC_CONTEXT_PROVIDER:
        raise ValueError("unsupported_spec_provider")
    return read_openspec_context(root, change_id)


__all__ = [
    "SPEC_CONTEXT_PROVIDER",
    "SPEC_CONTEXT_ROLE",
    "SPEC_CONTEXT_SCHEMA",
    "SpecContext",
    "SpecContextArtifact",
    "SpecContextFinding",
    "SpecContextReview",
    "discover_openspec_contexts",
    "read_openspec_context",
    "read_spec_context",
    "review_spec_context",
]
