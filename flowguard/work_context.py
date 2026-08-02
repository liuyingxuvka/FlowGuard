"""Provider-neutral, read-only work context for FlowGuard planning.

External planning and specification systems retain their native authoring,
execution, validation, status, and lifecycle authority. FlowGuard reads
content-addressed artifacts through explicitly registered adapters and never
turns provider state into model or test evidence.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from ._normalization import string_tuple as _string_tuple
from .model_authority import SUBJECT_NORMATIVE_TARGET


WORK_CONTEXT_SCHEMA = "flowguard.work_context.v1"
WORK_CONTEXT_ROLE = "read_only_external"
WORK_CONTEXT_ARTIFACT_ROLES = (
    "scope",
    "requirement",
    "acceptance",
    "design",
    "plan",
    "task",
    "status",
    "history",
    "other",
)
_FORBIDDEN_AUTHORITY_KEYS = {
    "write",
    "write_requested",
    "execute",
    "execute_requested",
    "execution_owner",
    "check_owner",
    "session",
    "session_id",
    "cache",
    "cache_path",
    "receipt",
    "receipt_id",
    "archive_ready",
}
def _wire_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _bounded_path(project_root: Path, path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if resolved != project_root and project_root not in resolved.parents:
        raise ValueError(f"{label} escapes project root")
    return resolved


@dataclass(frozen=True)
class WorkContextArtifact:
    artifact_id: str
    artifact_role: str
    source_ref: str
    content_fingerprint: str
    size: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", str(self.artifact_id))
        object.__setattr__(self, "artifact_role", str(self.artifact_role))
        object.__setattr__(self, "source_ref", str(self.source_ref))
        object.__setattr__(self, "content_fingerprint", str(self.content_fingerprint))
        object.__setattr__(self, "size", int(self.size))

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_role": self.artifact_role,
            "source_ref": self.source_ref,
            "content_fingerprint": self.content_fingerprint,
            "size": self.size,
        }


@dataclass(frozen=True)
class WorkContext:
    context_id: str
    adapter_id: str
    native_work_id: str
    native_owner_id: str
    project_root: str
    context_root: str
    artifacts: tuple[WorkContextArtifact, ...]
    required_artifact_roles: tuple[str, ...] = ()
    behavior_source_surface_ids: tuple[str, ...] = ()
    subject_lane: str = SUBJECT_NORMATIVE_TARGET
    read_only: bool = True
    current: bool = True
    context_fingerprint: str = ""
    native_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "context_id", str(self.context_id))
        object.__setattr__(self, "adapter_id", str(self.adapter_id))
        object.__setattr__(self, "native_work_id", str(self.native_work_id))
        object.__setattr__(self, "native_owner_id", str(self.native_owner_id))
        object.__setattr__(self, "project_root", str(self.project_root))
        object.__setattr__(self, "context_root", str(self.context_root))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(
            self,
            "required_artifact_roles",
            _string_tuple(self.required_artifact_roles),
        )
        object.__setattr__(
            self,
            "behavior_source_surface_ids",
            _string_tuple(self.behavior_source_surface_ids),
        )
        object.__setattr__(self, "subject_lane", str(self.subject_lane))
        object.__setattr__(self, "read_only", bool(self.read_only))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(
            self,
            "context_fingerprint",
            str(self.context_fingerprint),
        )
        object.__setattr__(self, "native_metadata", dict(self.native_metadata))

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": WORK_CONTEXT_SCHEMA,
            "context_id": self.context_id,
            "adapter_id": self.adapter_id,
            "native_work_id": self.native_work_id,
            "native_owner_id": self.native_owner_id,
            "project_root": self.project_root,
            "context_root": self.context_root,
            "subject_lane": self.subject_lane,
            "read_only": self.read_only,
            "current": self.current,
            "required_artifact_roles": list(self.required_artifact_roles),
            "behavior_source_surface_ids": list(self.behavior_source_surface_ids),
            "artifacts": [item.to_dict() for item in self.artifacts],
            "native_metadata": dict(self.native_metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_work_context",
            **self.identity_payload(),
            "context_fingerprint": self.context_fingerprint,
            "claim_boundary": (
                "This is content-addressed read-only planning context. The native "
                "provider retains authoring, execution, validation, status, and "
                "lifecycle authority. Provider status is never FlowGuard model or "
                "test evidence."
            ),
        }


@dataclass(frozen=True)
class WorkContextFinding:
    code: str
    message: str
    source_ref: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True)
class WorkContextReview:
    context: WorkContext
    findings: tuple[WorkContextFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def finding_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_work_context_review",
            "schema_version": WORK_CONTEXT_SCHEMA,
            "ok": self.ok,
            "status": "pass" if self.ok else "blocked",
            "context": self.context.to_dict(),
            "findings": [item.to_dict() for item in self.findings],
            "claim_boundary": self.context.to_dict()["claim_boundary"],
        }


@dataclass(frozen=True)
class ProjectWorkContextReview:
    project_root: str
    contexts: tuple[WorkContext, ...]
    findings: tuple[WorkContextFinding, ...]
    declaration_fingerprint: str

    @property
    def ok(self) -> bool:
        return not self.findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_project_work_context_review",
            "schema_version": WORK_CONTEXT_SCHEMA,
            "ok": self.ok,
            "status": "pass" if self.ok else "blocked",
            "project_root": self.project_root,
            "contexts": [item.to_dict() for item in self.contexts],
            "findings": [item.to_dict() for item in self.findings],
            "declaration_fingerprint": self.declaration_fingerprint,
        }


class WorkContextAdapter(Protocol):
    adapter_id: str
    native_owner_id: str

    def discover(
        self,
        root: str | Path,
        declaration: Mapping[str, Any] | None = None,
    ) -> tuple[str, ...]:
        ...

    def read(
        self,
        root: str | Path,
        native_work_id: str,
        declaration: Mapping[str, Any] | None = None,
    ) -> WorkContext:
        ...


_ADAPTERS: dict[str, WorkContextAdapter] = {}


def register_work_context_adapter(
    adapter: WorkContextAdapter,
    *,
    replace: bool = False,
) -> None:
    adapter_id = str(getattr(adapter, "adapter_id", "")).strip()
    if not adapter_id:
        raise ValueError("work context adapter requires adapter_id")
    if adapter_id in _ADAPTERS and not replace:
        raise ValueError(f"work context adapter already registered: {adapter_id}")
    _ADAPTERS[adapter_id] = adapter


def registered_work_context_adapter_ids() -> tuple[str, ...]:
    return tuple(sorted(_ADAPTERS))


def _artifact_from_path(
    path: Path,
    project_root: Path,
    *,
    artifact_id: str,
    role: str,
) -> WorkContextArtifact:
    content = path.read_bytes()
    return WorkContextArtifact(
        artifact_id=artifact_id,
        artifact_role=role,
        source_ref=path.relative_to(project_root).as_posix(),
        content_fingerprint=_wire_hash(content),
        size=len(content),
    )


def _derived_artifact(
    *,
    artifact_id: str,
    role: str,
    source_ref: str,
    value: Mapping[str, Any],
) -> WorkContextArtifact:
    content = _canonical_json(value).encode("utf-8")
    return WorkContextArtifact(
        artifact_id=artifact_id,
        artifact_role=role,
        source_ref=source_ref,
        content_fingerprint=_wire_hash(content),
        size=len(content),
    )


def _finalize_context(context: WorkContext) -> WorkContext:
    payload = context.identity_payload()
    return replace(
        context,
        context_fingerprint=_wire_hash(
            _canonical_json(payload).encode("utf-8")
        ),
    )


def read_work_context(
    root: str | Path,
    native_work_id: str,
    *,
    adapter_id: str,
    declaration: Mapping[str, Any] | None = None,
) -> WorkContext:
    adapter = _ADAPTERS.get(str(adapter_id))
    if adapter is None:
        raise ValueError("work_context_adapter_unregistered")
    return adapter.read(root, native_work_id, declaration)


def discover_work_contexts(
    root: str | Path,
    *,
    adapter_id: str,
    declaration: Mapping[str, Any] | None = None,
) -> tuple[WorkContext, ...]:
    adapter = _ADAPTERS.get(str(adapter_id))
    if adapter is None:
        raise ValueError("work_context_adapter_unregistered")
    return tuple(
        adapter.read(root, work_id, declaration)
        for work_id in adapter.discover(root, declaration)
    )


def read_project_work_contexts(
    root: str | Path,
) -> ProjectWorkContextReview:
    """Read exact declared sources from ``.flowguard/project.toml``."""

    project_root = Path(root).expanduser().resolve()
    manifest_path = project_root / ".flowguard" / "project.toml"
    findings: list[WorkContextFinding] = []
    contexts: list[WorkContext] = []
    if not manifest_path.is_file():
        return ProjectWorkContextReview(
            str(project_root),
            (),
            (
                WorkContextFinding(
                    "work_context_project_manifest_missing",
                    "project WorkContext discovery requires .flowguard/project.toml",
                    str(manifest_path),
                ),
            ),
            "",
        )
    payload = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    work_context_section = payload.get("work_context", {})
    source_rows = (
        work_context_section.get("sources", ())
        if isinstance(work_context_section, Mapping)
        else ()
    )
    if not isinstance(source_rows, list):
        findings.append(
            WorkContextFinding(
                "work_context_source_declarations_invalid",
                "work_context.sources must be an array of source declarations",
                manifest_path.as_posix(),
            )
        )
        source_rows = ()
    seen_source_ids: set[str] = set()
    seen_context_ids: set[str] = set()
    canonical_rows: list[dict[str, Any]] = []
    for index, raw in enumerate(source_rows):
        if not isinstance(raw, Mapping):
            findings.append(
                WorkContextFinding(
                    "work_context_source_declaration_invalid",
                    "each WorkContext source declaration must be a table",
                    f"work_context.sources[{index}]",
                )
            )
            continue
        row = dict(raw)
        source_id = str(row.get("source_id", "")).strip()
        adapter_id = str(row.get("adapter_id", "")).strip()
        required = bool(row.get("required", False))
        if not source_id or not adapter_id:
            findings.append(
                WorkContextFinding(
                    "work_context_source_identity_missing",
                    "source declaration requires source_id and adapter_id",
                    f"work_context.sources[{index}]",
                )
            )
            continue
        if source_id in seen_source_ids:
            findings.append(
                WorkContextFinding(
                    "work_context_source_identity_duplicate",
                    "source declaration ids must be unique",
                    source_id,
                )
            )
            continue
        seen_source_ids.add(source_id)
        canonical_rows.append(row)
        adapter = _ADAPTERS.get(adapter_id)
        if adapter is None:
            findings.append(
                WorkContextFinding(
                    "work_context_adapter_unregistered",
                    "source declaration names an unregistered adapter",
                    source_id,
                )
            )
            continue
        native_work_id = str(row.get("native_work_id", "")).strip()
        work_ids = (
            (native_work_id,)
            if native_work_id
            else adapter.discover(project_root, row)
        )
        if required and not work_ids:
            findings.append(
                WorkContextFinding(
                    "required_work_context_source_empty",
                    "required source declaration discovered no native work",
                    source_id,
                )
            )
        for work_id in work_ids:
            try:
                context = adapter.read(project_root, work_id, row)
            except (OSError, ValueError) as exc:
                findings.append(
                    WorkContextFinding(
                        "work_context_source_read_failed",
                        str(exc),
                        source_id,
                    )
                )
                continue
            if context.context_id in seen_context_ids:
                findings.append(
                    WorkContextFinding(
                        "work_context_identity_duplicate",
                        "configured sources produced a duplicate context id",
                        context.context_id,
                    )
                )
                continue
            seen_context_ids.add(context.context_id)
            review = review_work_context(context)
            findings.extend(review.findings)
            contexts.append(context)
    return ProjectWorkContextReview(
        str(project_root),
        tuple(sorted(contexts, key=lambda item: item.context_id)),
        tuple(findings),
        _wire_hash(
            _canonical_json(
                sorted(canonical_rows, key=lambda row: str(row.get("source_id", "")))
            ).encode("utf-8")
        ),
    )


def review_work_context(context: WorkContext) -> WorkContextReview:
    findings: list[WorkContextFinding] = []
    if context.adapter_id not in _ADAPTERS:
        findings.append(
            WorkContextFinding(
                "work_context_adapter_unregistered",
                "context adapter is not explicitly registered",
            )
        )
    if context.read_only is not True:
        findings.append(
            WorkContextFinding(
                "work_context_write_authority_forbidden",
                "work context must be read-only",
            )
        )
    if not context.current:
        findings.append(
            WorkContextFinding(
                "work_context_not_current",
                "work context source is missing or stale",
            )
        )
    if not context.native_owner_id:
        findings.append(
            WorkContextFinding(
                "work_context_native_owner_missing",
                "native provider owner must remain explicit",
            )
        )
    try:
        project_root = Path(context.project_root).resolve()
        _bounded_path(project_root, Path(context.context_root), "context root")
    except (OSError, ValueError) as exc:
        findings.append(
            WorkContextFinding("work_context_root_unbounded", str(exc))
        )
    seen_ids: set[str] = set()
    roles: set[str] = set()
    for artifact in context.artifacts:
        if not artifact.artifact_id or artifact.artifact_id in seen_ids:
            findings.append(
                WorkContextFinding(
                    "work_context_artifact_identity_invalid",
                    "artifact ids must be non-empty and unique",
                    artifact.source_ref,
                )
            )
        seen_ids.add(artifact.artifact_id)
        if artifact.artifact_role not in WORK_CONTEXT_ARTIFACT_ROLES:
            findings.append(
                WorkContextFinding(
                    "work_context_artifact_role_invalid",
                    "artifact role is not part of the current generic role set",
                    artifact.source_ref,
                )
            )
        roles.add(artifact.artifact_role)
        if not artifact.content_fingerprint.startswith("sha256:"):
            findings.append(
                WorkContextFinding(
                    "work_context_artifact_fingerprint_missing",
                    "artifact needs a content fingerprint",
                    artifact.source_ref,
                )
            )
        source_ref = artifact.source_ref.strip()
        is_derived_ref = (
            source_ref.startswith("<")
            or Path(source_ref).name.startswith("@derived")
        )
        if source_ref and not is_derived_ref:
            try:
                source_path = _bounded_path(
                    project_root,
                    project_root / source_ref,
                    "work context artifact",
                )
            except (OSError, ValueError) as exc:
                findings.append(
                    WorkContextFinding(
                        "work_context_artifact_source_unbounded",
                        str(exc),
                        artifact.source_ref,
                    )
                )
                continue
            if not source_path.is_file():
                findings.append(
                    WorkContextFinding(
                        "work_context_artifact_source_missing",
                        "artifact source must still exist as a project-bounded file",
                        artifact.source_ref,
                    )
                )
                continue
            try:
                current_bytes = source_path.read_bytes()
            except OSError as exc:
                findings.append(
                    WorkContextFinding(
                        "work_context_artifact_source_unreadable",
                        str(exc),
                        artifact.source_ref,
                    )
                )
                continue
            if (
                _wire_hash(current_bytes) != artifact.content_fingerprint
                or len(current_bytes) != artifact.size
            ):
                findings.append(
                    WorkContextFinding(
                        "work_context_artifact_source_changed",
                        "artifact bytes no longer match the preserved snapshot",
                        artifact.source_ref,
                    )
                )
    for role in context.required_artifact_roles:
        if role not in roles:
            findings.append(
                WorkContextFinding(
                    "work_context_required_role_missing",
                    f"adapter-declared required artifact role is missing: {role}",
                )
            )
    forbidden = sorted(
        key for key in context.native_metadata if str(key) in _FORBIDDEN_AUTHORITY_KEYS
    )
    if forbidden:
        findings.append(
            WorkContextFinding(
                "work_context_provider_authority_forbidden",
                "work context carries forbidden provider execution authority: "
                + ", ".join(forbidden),
            )
        )
    expected = _wire_hash(
        _canonical_json(context.identity_payload()).encode("utf-8")
    )
    if context.context_fingerprint != expected:
        findings.append(
            WorkContextFinding(
                "work_context_fingerprint_stale",
                "context fingerprint does not match current artifacts and metadata",
            )
        )
    return WorkContextReview(context, tuple(findings))


__all__ = [
    "WORK_CONTEXT_ARTIFACT_ROLES",
    "WORK_CONTEXT_ROLE",
    "WORK_CONTEXT_SCHEMA",
    "WorkContext",
    "WorkContextAdapter",
    "WorkContextArtifact",
    "WorkContextFinding",
    "WorkContextReview",
    "ProjectWorkContextReview",
    "discover_work_contexts",
    "read_project_work_contexts",
    "read_work_context",
    "register_work_context_adapter",
    "registered_work_context_adapter_ids",
    "review_work_context",
]
