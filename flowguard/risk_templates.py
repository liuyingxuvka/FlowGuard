"""Reusable risk template library helpers for minimum valuable models."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable


TEMPLATE_LIBRARY_ENV_VAR = "FLOWGUARD_TEMPLATE_LIBRARY_ROOT"
RISK_TEMPLATE_STATUSES = ("trusted", "candidate", "rejected")
RISK_TEMPLATE_SOURCES = ("public", "local", "merged")
TEMPLATE_HARVEST_DISPOSITIONS = ("written", "merged", "duplicate_linked", "not_harvestable")
TEMPLATE_HARVEST_WITH_TEMPLATE_ID = ("written", "merged", "duplicate_linked")
NOT_HARVESTABLE_REASONS = (
    "not_reusable_project_specific",
    "no_new_pattern",
    "missing_known_bad_case",
    "missing_completion_evidence",
    "write_blocked",
    "human_deferred",
)
KNOWN_BAD_PROOF_CAUGHT_STATUSES = (
    "failed",
    "rejected",
    "blocked",
    "invariant_violation",
    "expected_violation",
)
KNOWN_BAD_PROOF_PASS_STATUSES = ("pass", "passed", "ok", "clean")
KNOWN_BAD_PROOF_NOT_CURRENT_STATUSES = (
    "stale",
    "skipped",
    "not_run",
    "running",
    "progress_only",
)


def _normalize_text_items(values: Iterable[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        raw_values = (values,)
    else:
        raw_values = values
    return tuple(str(item).strip() for item in raw_values if str(item).strip())


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return tuple(result)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value).strip().lower()).strip("-")
    return slug or "risk-template"


def _tokens(values: Iterable[str] | str) -> set[str]:
    if isinstance(values, str):
        text = values
    else:
        text = " ".join(str(value) for value in values)
    return {
        token
        for token in re.split(r"[^a-zA-Z0-9]+", text.lower())
        if len(token) >= 2
    }


@dataclass(frozen=True)
class RiskTemplate:
    """Small reusable card for a model-risk pattern."""

    template_id: str
    title: str
    summary: str = ""
    workflow_families: tuple[str, ...] = ()
    protected_error_classes: tuple[str, ...] = ()
    required_state: tuple[str, ...] = ()
    required_side_effects: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()
    known_bad_cases: tuple[str, ...] = ()
    merge_keys: tuple[str, ...] = ()
    source: str = "public"
    status: str = "trusted"
    source_template_ids: tuple[str, ...] = ()
    false_friend_rationales: tuple[str, ...] = ()
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        source = str(self.source or "public").strip().lower()
        if source not in RISK_TEMPLATE_SOURCES:
            raise ValueError(f"source must be one of {RISK_TEMPLATE_SOURCES!r}")
        status = str(self.status or "trusted").strip().lower()
        if status not in RISK_TEMPLATE_STATUSES:
            raise ValueError(f"status must be one of {RISK_TEMPLATE_STATUSES!r}")
        object.__setattr__(self, "template_id", _slug(self.template_id))
        object.__setattr__(self, "title", str(self.title))
        object.__setattr__(self, "summary", str(self.summary or ""))
        object.__setattr__(self, "workflow_families", _unique(_normalize_text_items(self.workflow_families)))
        object.__setattr__(
            self,
            "protected_error_classes",
            _unique(_normalize_text_items(self.protected_error_classes)),
        )
        object.__setattr__(self, "required_state", _unique(_normalize_text_items(self.required_state)))
        object.__setattr__(
            self,
            "required_side_effects",
            _unique(_normalize_text_items(self.required_side_effects)),
        )
        object.__setattr__(self, "required_evidence", _unique(_normalize_text_items(self.required_evidence)))
        object.__setattr__(self, "known_bad_cases", _unique(_normalize_text_items(self.known_bad_cases)))
        object.__setattr__(self, "merge_keys", _unique(_normalize_text_items(self.merge_keys)))
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self,
            "source_template_ids",
            _unique(_normalize_text_items(self.source_template_ids or (self.template_id,))),
        )
        object.__setattr__(
            self,
            "false_friend_rationales",
            _unique(_normalize_text_items(self.false_friend_rationales)),
        )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RiskTemplate":
        return cls(
            template_id=str(data.get("template_id", data.get("id", ""))),
            title=str(data.get("title", "")),
            summary=str(data.get("summary", "")),
            workflow_families=data.get("workflow_families", ()),
            protected_error_classes=data.get("protected_error_classes", ()),
            required_state=data.get("required_state", ()),
            required_side_effects=data.get("required_side_effects", ()),
            required_evidence=data.get("required_evidence", ()),
            known_bad_cases=data.get("known_bad_cases", ()),
            merge_keys=data.get("merge_keys", ()),
            source=str(data.get("source", "local")),
            status=str(data.get("status", "candidate")),
            source_template_ids=data.get("source_template_ids", ()),
            false_friend_rationales=data.get("false_friend_rationales", ()),
            metadata=data.get("metadata"),
        )

    @property
    def reusable_terms(self) -> tuple[str, ...]:
        return _unique(
            (
                self.template_id,
                self.title,
                self.summary,
                *self.workflow_families,
                *self.protected_error_classes,
                *self.required_state,
                *self.required_side_effects,
                *self.required_evidence,
                *self.known_bad_cases,
                *self.merge_keys,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "title": self.title,
            "summary": self.summary,
            "workflow_families": list(self.workflow_families),
            "protected_error_classes": list(self.protected_error_classes),
            "required_state": list(self.required_state),
            "required_side_effects": list(self.required_side_effects),
            "required_evidence": list(self.required_evidence),
            "known_bad_cases": list(self.known_bad_cases),
            "merge_keys": list(self.merge_keys),
            "source": self.source,
            "status": self.status,
            "source_template_ids": list(self.source_template_ids),
            "false_friend_rationales": list(self.false_friend_rationales),
            "metadata": to_jsonable(self.metadata),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


@dataclass(frozen=True)
class RiskTemplateMatch:
    """One search match against a reusable risk template."""

    template: RiskTemplate
    score: int
    matched_terms: tuple[str, ...] = ()
    layer: str = "public"

    def __post_init__(self) -> None:
        object.__setattr__(self, "score", int(self.score))
        object.__setattr__(self, "matched_terms", _unique(_normalize_text_items(self.matched_terms)))
        object.__setattr__(self, "layer", str(self.layer or self.template.source))

    def to_dict(self) -> dict[str, Any]:
        return {
            "template": self.template.to_dict(),
            "score": self.score,
            "matched_terms": list(self.matched_terms),
            "layer": self.layer,
        }


@dataclass(frozen=True)
class RiskTemplateSearchReport:
    """Search report for public and local risk templates."""

    query: str = ""
    matches: tuple[RiskTemplateMatch, ...] = ()
    searched_layers: tuple[str, ...] = ()
    local_root: str = ""
    findings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not any(finding.startswith("error:") for finding in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "matches": [match.to_dict() for match in self.matches],
            "searched_layers": list(self.searched_layers),
            "local_root": self.local_root,
            "findings": list(self.findings),
        }

    def format_text(self, max_matches: int = 8) -> str:
        lines = [
            "=== flowguard risk template search ===",
            f"query: {self.query or '(none)'}",
            f"searched_layers: {', '.join(self.searched_layers) if self.searched_layers else '(none)'}",
            f"matches: {len(self.matches)}",
        ]
        for match in self.matches[:max_matches]:
            lines.append(
                f"- {match.template.template_id} [{match.layer}] score={match.score}: {match.template.title}"
            )
        for finding in self.findings:
            lines.append(f"finding: {finding}")
        return "\n".join(lines)


@dataclass(frozen=True)
class TemplateReuseReview:
    """Structured record that a model looked for reusable templates."""

    used_template_ids: tuple[str, ...] = ()
    no_match_reason: str = ""
    searched_layers: tuple[str, ...] = ()
    match_template_ids: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()

    def __init__(
        self,
        *,
        used_template_ids: Iterable[str] | str = (),
        no_match_reason: str = "",
        searched_layers: Iterable[str] | str = (),
        match_template_ids: Iterable[str] | str = (),
        findings: Iterable[str] | str = (),
    ) -> None:
        object.__setattr__(self, "used_template_ids", _unique(_normalize_text_items(used_template_ids)))
        object.__setattr__(self, "no_match_reason", str(no_match_reason or ""))
        object.__setattr__(self, "searched_layers", _unique(_normalize_text_items(searched_layers)))
        object.__setattr__(self, "match_template_ids", _unique(_normalize_text_items(match_template_ids)))
        object.__setattr__(self, "findings", _unique(_normalize_text_items(findings)))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TemplateReuseReview":
        return cls(
            used_template_ids=data.get("used_template_ids", ()),
            no_match_reason=str(data.get("no_match_reason", "")),
            searched_layers=data.get("searched_layers", ()),
            match_template_ids=data.get("match_template_ids", ()),
            findings=data.get("findings", ()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "used_template_ids": list(self.used_template_ids),
            "no_match_reason": self.no_match_reason,
            "searched_layers": list(self.searched_layers),
            "match_template_ids": list(self.match_template_ids),
            "findings": list(self.findings),
        }


@dataclass(frozen=True)
class MinimumModelContract:
    """Minimum useful model declaration for model-first checks."""

    protected_error_classes: tuple[str, ...] = ()
    modeled_state: tuple[str, ...] = ()
    modeled_side_effects: tuple[str, ...] = ()
    completion_evidence: tuple[str, ...] = ()
    known_bad_cases: tuple[str, ...] = ()

    def __init__(
        self,
        *,
        protected_error_classes: Iterable[str] | str = (),
        modeled_state: Iterable[str] | str = (),
        modeled_side_effects: Iterable[str] | str = (),
        completion_evidence: Iterable[str] | str = (),
        known_bad_cases: Iterable[str] | str = (),
    ) -> None:
        object.__setattr__(
            self,
            "protected_error_classes",
            _unique(_normalize_text_items(protected_error_classes)),
        )
        object.__setattr__(self, "modeled_state", _unique(_normalize_text_items(modeled_state)))
        object.__setattr__(
            self,
            "modeled_side_effects",
            _unique(_normalize_text_items(modeled_side_effects)),
        )
        object.__setattr__(self, "completion_evidence", _unique(_normalize_text_items(completion_evidence)))
        object.__setattr__(self, "known_bad_cases", _unique(_normalize_text_items(known_bad_cases)))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MinimumModelContract":
        return cls(
            protected_error_classes=data.get("protected_error_classes", ()),
            modeled_state=data.get("modeled_state", ()),
            modeled_side_effects=data.get("modeled_side_effects", ()),
            completion_evidence=data.get("completion_evidence", ()),
            known_bad_cases=data.get("known_bad_cases", ()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "protected_error_classes": list(self.protected_error_classes),
            "modeled_state": list(self.modeled_state),
            "modeled_side_effects": list(self.modeled_side_effects),
            "completion_evidence": list(self.completion_evidence),
            "known_bad_cases": list(self.known_bad_cases),
        }


@dataclass(frozen=True)
class KnownBadProof:
    """Structured proof that one declared known-bad case is caught."""

    case_id: str
    protected_error_class: str = ""
    method: str = ""
    expected_failure: str = "failed"
    observed_status: str = ""
    observed_failure: str = ""
    evidence_id: str = ""
    proof_artifact_id: str = ""
    current: bool = True
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", str(self.case_id or "").strip())
        object.__setattr__(self, "protected_error_class", str(self.protected_error_class or "").strip())
        object.__setattr__(self, "method", str(self.method or "").strip())
        object.__setattr__(self, "expected_failure", str(self.expected_failure or "").strip().lower())
        object.__setattr__(self, "observed_status", str(self.observed_status or "").strip().lower())
        object.__setattr__(self, "observed_failure", str(self.observed_failure or "").strip())
        object.__setattr__(self, "evidence_id", str(self.evidence_id or "").strip())
        object.__setattr__(self, "proof_artifact_id", str(self.proof_artifact_id or "").strip())
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "KnownBadProof":
        return cls(
            case_id=str(data.get("case_id", data.get("known_bad_case", ""))),
            protected_error_class=str(data.get("protected_error_class", "")),
            method=str(data.get("method", data.get("proof_method", ""))),
            expected_failure=str(data.get("expected_failure", data.get("expected_result", "failed"))),
            observed_status=str(data.get("observed_status", data.get("observed_result", ""))),
            observed_failure=str(data.get("observed_failure", "")),
            evidence_id=str(data.get("evidence_id", data.get("check_id", ""))),
            proof_artifact_id=str(data.get("proof_artifact_id", "")),
            current=bool(data.get("current", True)),
            metadata=data.get("metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "protected_error_class": self.protected_error_class,
            "method": self.method,
            "expected_failure": self.expected_failure,
            "observed_status": self.observed_status,
            "observed_failure": self.observed_failure,
            "evidence_id": self.evidence_id,
            "proof_artifact_id": self.proof_artifact_id,
            "current": self.current,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class MinimumModelReviewReport:
    """Review result for a minimum valuable model declaration."""

    ok: bool
    status: str
    findings: tuple[str, ...] = ()
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "summary": self.summary,
            "findings": list(self.findings),
        }

    def format_text(self) -> str:
        lines = [
            "=== flowguard minimum valuable model review ===",
            f"status: {self.status}",
            self.summary,
        ]
        for finding in self.findings:
            lines.append(f"- {finding}")
        return "\n".join(lines)


@dataclass(frozen=True)
class RiskTemplateHarvestReport:
    """Result of attempting to save a local template candidate."""

    ok: bool
    status: str
    findings: tuple[str, ...] = ()
    template: RiskTemplate | None = None
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "findings": list(self.findings),
            "template": self.template.to_dict() if self.template is not None else None,
            "path": self.path,
        }

    def format_text(self) -> str:
        lines = [
            "=== flowguard risk template harvest ===",
            f"status: {self.status}",
            f"ok: {self.ok}",
        ]
        if self.template is not None:
            lines.append(f"template: {self.template.template_id}")
        if self.path:
            lines.append(f"path: {self.path}")
        for finding in self.findings:
            lines.append(f"- {finding}")
        return "\n".join(lines)


@dataclass(frozen=True)
class TemplateHarvestReview:
    """Final closure row for the local template harvest step."""

    disposition: str
    written_template_ids: tuple[str, ...] = ()
    merged_template_ids: tuple[str, ...] = ()
    linked_template_ids: tuple[str, ...] = ()
    not_harvestable_reason: str = ""
    local_root: str = ""
    findings: tuple[str, ...] = ()
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        disposition = str(self.disposition or "").strip().lower().replace("-", "_")
        object.__setattr__(self, "disposition", disposition)
        object.__setattr__(self, "written_template_ids", _unique(_normalize_text_items(self.written_template_ids)))
        object.__setattr__(self, "merged_template_ids", _unique(_normalize_text_items(self.merged_template_ids)))
        object.__setattr__(self, "linked_template_ids", _unique(_normalize_text_items(self.linked_template_ids)))
        object.__setattr__(self, "not_harvestable_reason", str(self.not_harvestable_reason or "").strip().lower())
        object.__setattr__(self, "local_root", str(self.local_root or ""))
        object.__setattr__(self, "findings", _unique(_normalize_text_items(self.findings)))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TemplateHarvestReview":
        return cls(
            disposition=str(data.get("disposition", "")),
            written_template_ids=data.get("written_template_ids", ()),
            merged_template_ids=data.get("merged_template_ids", ()),
            linked_template_ids=data.get("linked_template_ids", ()),
            not_harvestable_reason=str(data.get("not_harvestable_reason", data.get("reason", ""))),
            local_root=str(data.get("local_root", "")),
            findings=data.get("findings", ()),
            metadata=data.get("metadata"),
        )

    @property
    def template_ids(self) -> tuple[str, ...]:
        return _unique((*self.written_template_ids, *self.merged_template_ids, *self.linked_template_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition,
            "written_template_ids": list(self.written_template_ids),
            "merged_template_ids": list(self.merged_template_ids),
            "linked_template_ids": list(self.linked_template_ids),
            "not_harvestable_reason": self.not_harvestable_reason,
            "local_root": self.local_root,
            "findings": list(self.findings),
            "metadata": to_jsonable(self.metadata),
        }

    def format_text(self) -> str:
        lines = [
            "=== flowguard template harvest closure ===",
            f"disposition: {self.disposition or '(missing)'}",
            f"templates: {', '.join(self.template_ids) or '(none)'}",
        ]
        if self.not_harvestable_reason:
            lines.append(f"not_harvestable_reason: {self.not_harvestable_reason}")
        if self.local_root:
            lines.append(f"local_root: {self.local_root}")
        for finding in self.findings:
            lines.append(f"- {finding}")
        return "\n".join(lines)


def builtin_risk_templates() -> tuple[RiskTemplate, ...]:
    """Return packaged public templates available on every installed machine."""

    return (
        RiskTemplate(
            "completion_requires_evidence",
            "Completion requires evidence",
            summary="Do not mark work complete from an ACK, return value, or intent without durable output evidence.",
            workflow_families=("task", "generation", "download", "publish", "work_package"),
            protected_error_classes=("premature_completion", "evidence_overclaim"),
            required_state=("pending", "evidence_recorded", "completed"),
            required_side_effects=("output_write", "status_commit"),
            required_evidence=("durable_output_ref", "completion_receipt"),
            known_bad_cases=("ack_without_output_marked_completed",),
            merge_keys=("completion", "evidence", "ack"),
        ),
        RiskTemplate(
            "side_effect_at_most_once",
            "Side effect happens at most once",
            summary="Retries and duplicates must not repeat durable side effects for the same logical request.",
            workflow_families=("retry", "deduplication", "queue", "publish"),
            protected_error_classes=("duplicate_side_effect", "idempotency_break"),
            required_state=("request_seen", "side_effect_done"),
            required_side_effects=("external_write", "publish", "send"),
            required_evidence=("side_effect_key",),
            known_bad_cases=("same_request_retry_writes_twice",),
            merge_keys=("side_effect", "at_most_once", "retry"),
        ),
        RiskTemplate(
            "partial_failure_consistency",
            "Partial failure leaves consistent state",
            summary="A workflow with multiple writes must not commit final state after only part of the work succeeds.",
            workflow_families=("multi_step_write", "import", "sync", "migration"),
            protected_error_classes=("partial_failure_inconsistent_state",),
            required_state=("started", "partial", "failed", "completed"),
            required_side_effects=("first_write", "second_write"),
            required_evidence=("rollback_or_failure_receipt",),
            known_bad_cases=("second_write_fails_but_completed_state_written",),
            merge_keys=("partial_failure", "consistency"),
        ),
        RiskTemplate(
            "stale_result_overwrite",
            "Old result cannot overwrite newer state",
            summary="Long-running or repeated work must prevent older results from replacing newer accepted results.",
            workflow_families=("refresh", "async", "cache", "analysis"),
            protected_error_classes=("stale_result_overwrite",),
            required_state=("request_generation", "active_generation", "result_committed"),
            required_side_effects=("state_update",),
            required_evidence=("generation_token", "freshness_check"),
            known_bad_cases=("old_generation_result_commits_after_new_generation",),
            merge_keys=("stale", "overwrite", "generation"),
        ),
        RiskTemplate(
            "artifact_payload_real_surface",
            "Artifact payload exercises the real surface",
            summary="File, import/export, or generated artifact claims need accepted and rejected cases on the real payload surface.",
            workflow_families=("file", "import", "export", "artifact", "work_package"),
            protected_error_classes=("fake_payload_evidence", "schema_surface_gap"),
            required_state=("payload_seen", "payload_accepted", "payload_rejected"),
            required_side_effects=("file_read", "file_write"),
            required_evidence=("accepted_payload_case", "rejected_payload_case", "execution_proof"),
            known_bad_cases=("synthetic_internal_object_passes_without_real_file_surface",),
            merge_keys=("artifact", "payload", "real_surface"),
        ),
    )


def default_local_template_library_root() -> Path:
    """Return a portable per-user local template root."""

    override = os.environ.get(TEMPLATE_LIBRARY_ENV_VAR)
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Roaming"
        return root / "FlowGuard" / "risk_templates"
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".local" / "share"
    return root / "flowguard" / "risk_templates"


def load_local_risk_templates(root: str | Path | None = None) -> tuple[RiskTemplate, ...]:
    """Load local template JSON cards from the per-machine library."""

    library_root = Path(root) if root is not None else default_local_template_library_root()
    if not library_root.exists():
        return ()
    templates: list[RiskTemplate] = []
    for path in sorted(library_root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            template = RiskTemplate.from_dict(data)
        except Exception:
            continue
        if template.source != "local":
            template = RiskTemplate(**{**template.to_dict(), "source": "local"})
        templates.append(template)
    return tuple(templates)


def write_local_risk_template(
    template: RiskTemplate,
    root: str | Path | None = None,
    *,
    overwrite: bool = False,
) -> Path:
    """Write one local template card."""

    library_root = Path(root) if root is not None else default_local_template_library_root()
    library_root.mkdir(parents=True, exist_ok=True)
    local_template = RiskTemplate(**{**template.to_dict(), "source": "local"})
    target = library_root / f"{local_template.template_id}.json"
    if target.exists() and not overwrite:
        raise FileExistsError(f"risk template already exists: {target}")
    target.write_text(local_template.to_json_text() + "\n", encoding="utf-8")
    return target


def search_risk_templates(
    query: str = "",
    *,
    workflow_families: Sequence[str] = (),
    protected_error_classes: Sequence[str] = (),
    include_public: bool = True,
    include_local: bool = True,
    local_root: str | Path | None = None,
    max_results: int = 8,
) -> RiskTemplateSearchReport:
    """Search public and local risk templates using simple deterministic scoring."""

    query_terms = _tokens((query, *workflow_families, *protected_error_classes))
    templates: list[RiskTemplate] = []
    searched_layers: list[str] = []
    findings: list[str] = []
    if include_public:
        templates.extend(builtin_risk_templates())
        searched_layers.append("public")
    local_library_root = default_local_template_library_root() if local_root is None else Path(local_root)
    if include_local:
        templates.extend(load_local_risk_templates(local_library_root))
        searched_layers.append("local")

    matches: list[RiskTemplateMatch] = []
    for template in templates:
        template_terms = _tokens(template.reusable_terms)
        if query_terms:
            matched = sorted(query_terms.intersection(template_terms))
            score = len(matched)
        else:
            matched = []
            score = 1 if template.source == "public" else 0
        protected_overlap = set(item.lower() for item in protected_error_classes).intersection(
            item.lower() for item in template.protected_error_classes
        )
        workflow_overlap = set(item.lower() for item in workflow_families).intersection(
            item.lower() for item in template.workflow_families
        )
        score += 3 * len(protected_overlap) + 2 * len(workflow_overlap)
        if score > 0:
            matches.append(
                RiskTemplateMatch(
                    template=template,
                    score=score,
                    matched_terms=matched,
                    layer=template.source,
                )
            )
    matches.sort(key=lambda match: (-match.score, match.template.template_id))
    if include_local and not local_library_root.exists():
        findings.append(f"local_library_not_found: {local_library_root}")
    return RiskTemplateSearchReport(
        query=query,
        matches=tuple(matches[:max_results]),
        searched_layers=tuple(searched_layers),
        local_root=str(local_library_root),
        findings=tuple(findings),
    )


def review_template_reuse(review: TemplateReuseReview | Mapping[str, Any] | None) -> MinimumModelReviewReport:
    """Review whether a model creation flow performed template reuse search."""

    if review is None:
        return MinimumModelReviewReport(
            ok=False,
            status="blocked",
            findings=("missing_template_reuse_review",),
            summary="template reuse review was not provided",
        )
    normalized = review if isinstance(review, TemplateReuseReview) else TemplateReuseReview.from_dict(review)
    findings: list[str] = list(normalized.findings)
    if not normalized.searched_layers:
        findings.append("missing_template_search_layers")
    if not normalized.used_template_ids and not normalized.no_match_reason.strip():
        findings.append("missing_template_use_or_no_match_reason")
    status = "pass" if not findings else "blocked"
    return MinimumModelReviewReport(
        ok=not findings,
        status=status,
        findings=tuple(findings),
        summary=f"used_templates={len(normalized.used_template_ids)} matches={len(normalized.match_template_ids)}",
    )


def review_minimum_model_contract(
    contract: MinimumModelContract | Mapping[str, Any] | None,
    *,
    template_reuse_review: TemplateReuseReview | Mapping[str, Any] | None = None,
) -> MinimumModelReviewReport:
    """Review the minimum valuable model fields."""

    findings: list[str] = []
    if contract is None:
        findings.append("missing_minimum_model_contract")
        normalized = MinimumModelContract()
    elif isinstance(contract, MinimumModelContract):
        normalized = contract
    else:
        normalized = MinimumModelContract.from_dict(contract)
    if not normalized.protected_error_classes:
        findings.append("missing_protected_error_class")
    if not (normalized.modeled_state or normalized.modeled_side_effects):
        findings.append("missing_state_or_side_effect")
    if not normalized.completion_evidence:
        findings.append("missing_completion_evidence")
    if not normalized.known_bad_cases:
        findings.append("missing_known_bad_case")
    reuse = review_template_reuse(template_reuse_review)
    findings.extend(reuse.findings)
    status = "pass" if not findings else "blocked"
    return MinimumModelReviewReport(
        ok=not findings,
        status=status,
        findings=tuple(_unique(findings)),
        summary=(
            f"protected_errors={len(normalized.protected_error_classes)} "
            f"known_bad_cases={len(normalized.known_bad_cases)}"
        ),
    )


def _coerce_known_bad_proofs(
    proofs: Sequence[KnownBadProof | Mapping[str, Any]] | None,
) -> tuple[KnownBadProof, ...]:
    if proofs is None:
        return ()
    normalized: list[KnownBadProof] = []
    for proof in proofs:
        if isinstance(proof, KnownBadProof):
            normalized.append(proof)
        elif isinstance(proof, Mapping):
            normalized.append(KnownBadProof.from_dict(proof))
        else:
            raise TypeError("known_bad_proofs must contain KnownBadProof or mapping items")
    return tuple(normalized)


def review_known_bad_proofs(
    contract: MinimumModelContract | Mapping[str, Any] | None,
    proofs: Sequence[KnownBadProof | Mapping[str, Any]] | None,
    *,
    risk_intent: Any = None,
) -> MinimumModelReviewReport:
    """Review executable proof that declared known-bad cases are caught."""

    normalized_contract = (
        contract
        if isinstance(contract, MinimumModelContract)
        else MinimumModelContract.from_dict(contract or {})
    )
    normalized_proofs = _coerce_known_bad_proofs(proofs)
    declared_cases = _unique(
        (
            *normalized_contract.known_bad_cases,
            *tuple(getattr(risk_intent, "known_bad_cases", ()) or ()),
        )
    )
    protected_errors = _unique(
        (
            *normalized_contract.protected_error_classes,
            *tuple(getattr(risk_intent, "protected_error_classes", ()) or ()),
        )
    )
    protected_lookup = {item.lower() for item in protected_errors}
    findings: list[str] = []

    if not declared_cases:
        findings.append("missing_known_bad_case")
    if not normalized_proofs:
        findings.append("missing_known_bad_proof")

    proofs_by_case: dict[str, list[KnownBadProof]] = {}
    for proof in normalized_proofs:
        proofs_by_case.setdefault(proof.case_id, []).append(proof)

    for case_id in declared_cases:
        if case_id not in proofs_by_case:
            findings.append(f"missing_known_bad_proof: {case_id}")

    for proof in normalized_proofs:
        if not proof.case_id:
            findings.append("missing_known_bad_case_id")
        elif declared_cases and proof.case_id not in declared_cases:
            findings.append(f"unknown_known_bad_proof_case: {proof.case_id}")
        if not proof.protected_error_class:
            findings.append("missing_known_bad_protected_error_class")
        elif protected_lookup and proof.protected_error_class.lower() not in protected_lookup:
            findings.append("known_bad_protected_error_mismatch")
        if not proof.method:
            findings.append("missing_known_bad_proof_method")
        if not (proof.evidence_id or proof.proof_artifact_id):
            findings.append("missing_known_bad_evidence")
        if not proof.expected_failure:
            findings.append("missing_expected_failure")
        if not proof.current or proof.observed_status in KNOWN_BAD_PROOF_NOT_CURRENT_STATUSES:
            findings.append("stale_known_bad_proof")
        if proof.observed_status in KNOWN_BAD_PROOF_PASS_STATUSES:
            findings.append("known_bad_case_passed")
        elif proof.observed_status not in KNOWN_BAD_PROOF_CAUGHT_STATUSES:
            findings.append("known_bad_proof_not_caught")
        elif not proof.observed_failure:
            findings.append("missing_observed_failure")

    unique_findings = _unique(findings)
    failure_findings = {"known_bad_case_passed", "known_bad_proof_not_caught"}
    if any(finding in failure_findings for finding in unique_findings):
        status = "failed"
    elif unique_findings:
        status = "blocked"
    else:
        status = "pass"
    return MinimumModelReviewReport(
        ok=status == "pass",
        status=status,
        findings=unique_findings,
        summary=(
            f"declared_known_bad_cases={len(declared_cases)} "
            f"proofs={len(normalized_proofs)}"
        ),
    )


def review_template_harvest_closure(
    review: TemplateHarvestReview | Mapping[str, Any] | None,
) -> MinimumModelReviewReport:
    """Review whether new/deepened model work closed the template harvest loop."""

    if review is None:
        return MinimumModelReviewReport(
            ok=False,
            status="blocked",
            findings=("missing_template_harvest_review",),
            summary="template harvest closure was not provided",
        )
    normalized = review if isinstance(review, TemplateHarvestReview) else TemplateHarvestReview.from_dict(review)
    findings: list[str] = list(normalized.findings)
    disposition = normalized.disposition
    if not disposition:
        findings.append("missing_template_harvest_disposition")
    elif disposition not in TEMPLATE_HARVEST_DISPOSITIONS:
        findings.append("invalid_template_harvest_disposition")
    elif disposition in TEMPLATE_HARVEST_WITH_TEMPLATE_ID:
        expected_ids = {
            "written": normalized.written_template_ids,
            "merged": normalized.merged_template_ids,
            "duplicate_linked": normalized.linked_template_ids,
        }[disposition]
        if not expected_ids:
            findings.append("missing_harvest_template_id")
    elif disposition == "not_harvestable":
        if not normalized.not_harvestable_reason:
            findings.append("missing_not_harvestable_reason")
        elif normalized.not_harvestable_reason not in NOT_HARVESTABLE_REASONS:
            findings.append("unsupported_not_harvestable_reason")
    unique_findings = _unique(findings)
    return MinimumModelReviewReport(
        ok=not unique_findings,
        status="pass" if not unique_findings else "blocked",
        findings=unique_findings,
        summary=f"harvest_disposition={disposition or '(missing)'}",
    )


def merge_risk_templates(
    templates: Sequence[RiskTemplate],
    *,
    template_id: str | None = None,
    title: str | None = None,
    false_friend_rationale: str = "",
) -> RiskTemplate:
    """Merge similar templates while preserving source ids and known-bad cases."""

    templates_tuple = tuple(templates)
    if not templates_tuple:
        raise ValueError("at least one template is required")
    protected_sets = [set(item.lower() for item in template.protected_error_classes) for template in templates_tuple]
    merge_key_sets = [set(item.lower() for item in template.merge_keys) for template in templates_tuple]
    protected_overlap = set.intersection(*protected_sets) if protected_sets else set()
    merge_key_overlap = set.intersection(*merge_key_sets) if merge_key_sets else set()
    if not protected_overlap and not merge_key_overlap and not false_friend_rationale:
        raise ValueError("templates need shared protected error classes, shared merge keys, or a false-friend rationale")
    first = templates_tuple[0]
    return RiskTemplate(
        template_id=template_id or first.template_id,
        title=title or first.title,
        summary=" / ".join(_unique(template.summary for template in templates_tuple if template.summary)),
        workflow_families=_unique(item for template in templates_tuple for item in template.workflow_families),
        protected_error_classes=_unique(item for template in templates_tuple for item in template.protected_error_classes),
        required_state=_unique(item for template in templates_tuple for item in template.required_state),
        required_side_effects=_unique(item for template in templates_tuple for item in template.required_side_effects),
        required_evidence=_unique(item for template in templates_tuple for item in template.required_evidence),
        known_bad_cases=_unique(item for template in templates_tuple for item in template.known_bad_cases),
        merge_keys=_unique(item for template in templates_tuple for item in template.merge_keys),
        source="merged",
        status="candidate" if any(template.status == "candidate" for template in templates_tuple) else "trusted",
        source_template_ids=_unique(
            item
            for template in templates_tuple
            for item in (template.source_template_ids or (template.template_id,))
        ),
        false_friend_rationales=(false_friend_rationale,) if false_friend_rationale else (),
    )


def harvest_risk_template_candidate(
    *,
    template_id: str,
    title: str,
    summary: str = "",
    workflow_families: Iterable[str] | str = (),
    protected_error_classes: Iterable[str] | str = (),
    required_state: Iterable[str] | str = (),
    required_side_effects: Iterable[str] | str = (),
    required_evidence: Iterable[str] | str = (),
    known_bad_cases: Iterable[str] | str = (),
    known_bad_proofs: Sequence[KnownBadProof | Mapping[str, Any]] | None = None,
    merge_keys: Iterable[str] | str = (),
    local_root: str | Path | None = None,
    write: bool = True,
    overwrite: bool = False,
) -> RiskTemplateHarvestReport:
    """Create and optionally write a local candidate template."""

    template = RiskTemplate(
        template_id=template_id,
        title=title,
        summary=summary,
        workflow_families=workflow_families,
        protected_error_classes=protected_error_classes,
        required_state=required_state,
        required_side_effects=required_side_effects,
        required_evidence=required_evidence,
        known_bad_cases=known_bad_cases,
        merge_keys=merge_keys,
        source="local",
        status="candidate",
    )
    missing: list[str] = []
    if not template.protected_error_classes:
        missing.append("missing_protected_error_class")
    if not (template.required_state or template.required_side_effects):
        missing.append("missing_state_or_side_effect")
    if not template.required_evidence:
        missing.append("missing_completion_evidence")
    if not template.known_bad_cases:
        missing.append("missing_known_bad_case")
    proof_report = review_known_bad_proofs(
        MinimumModelContract(
            protected_error_classes=template.protected_error_classes,
            modeled_state=template.required_state,
            modeled_side_effects=template.required_side_effects,
            completion_evidence=template.required_evidence,
            known_bad_cases=template.known_bad_cases,
        ),
        known_bad_proofs,
    )
    if proof_report.status != "pass":
        missing.extend(proof_report.findings)
    if missing:
        return RiskTemplateHarvestReport(False, "blocked", tuple(missing), template=template)
    if not write:
        return RiskTemplateHarvestReport(True, "candidate_ready", (), template=template)
    try:
        path = write_local_risk_template(template, root=local_root, overwrite=overwrite)
    except Exception as exc:
        return RiskTemplateHarvestReport(
            False,
            "blocked",
            (f"write_failed: {type(exc).__name__}: {exc}",),
            template=template,
        )
    return RiskTemplateHarvestReport(True, "written", (), template=template, path=str(path))


__all__ = [
    "KNOWN_BAD_PROOF_CAUGHT_STATUSES",
    "KNOWN_BAD_PROOF_NOT_CURRENT_STATUSES",
    "KNOWN_BAD_PROOF_PASS_STATUSES",
    "KnownBadProof",
    "MinimumModelContract",
    "MinimumModelReviewReport",
    "NOT_HARVESTABLE_REASONS",
    "RISK_TEMPLATE_SOURCES",
    "RISK_TEMPLATE_STATUSES",
    "RiskTemplate",
    "RiskTemplateHarvestReport",
    "RiskTemplateMatch",
    "RiskTemplateSearchReport",
    "TEMPLATE_LIBRARY_ENV_VAR",
    "TEMPLATE_HARVEST_DISPOSITIONS",
    "TEMPLATE_HARVEST_WITH_TEMPLATE_ID",
    "TemplateHarvestReview",
    "TemplateReuseReview",
    "builtin_risk_templates",
    "default_local_template_library_root",
    "harvest_risk_template_candidate",
    "load_local_risk_templates",
    "merge_risk_templates",
    "review_template_harvest_closure",
    "review_known_bad_proofs",
    "review_minimum_model_contract",
    "review_template_reuse",
    "search_risk_templates",
    "write_local_risk_template",
]
