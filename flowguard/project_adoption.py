"""Project-local FlowGuard adoption and version gate helpers.

The managed ``AGENTS.md`` block is a generated semantic contract.  This
module deliberately plans every adoption write before mutating the target so
that version, suite-membership, and governance-regression gates can fail
closed.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import tomllib

from .adoption import (
    AdoptionCommandResult,
    append_jsonl,
    append_markdown_log,
    make_adoption_log_entry,
)
from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable
from .schema import SCHEMA_VERSION


FLOWGUARD_REPOSITORY_URL = "https://github.com/liuyingxuvka/FlowGuard"
FLOWGUARD_AGENTS_BEGIN = "<!-- BEGIN FLOWGUARD PROJECT RULES -->"
FLOWGUARD_AGENTS_END = "<!-- END FLOWGUARD PROJECT RULES -->"
FLOWGUARD_PROJECT_MANIFEST = ".flowguard/project.toml"
FLOWGUARD_PROJECT_LOG = ".flowguard/adoption_log.jsonl"
FLOWGUARD_PROJECT_MARKDOWN_LOG = "docs/flowguard_adoption_log.md"

PROJECT_ADOPTION_ACTION_AUDIT = "audit"
PROJECT_ADOPTION_ACTION_ADOPT = "adopt"

PROJECT_ADOPTION_STATUS_PASS = "pass"
PROJECT_ADOPTION_STATUS_PASS_WITH_GAPS = "pass_with_gaps"
PROJECT_ADOPTION_STATUS_BLOCKED = "blocked"

PROJECT_ADOPTION_CLAIM_BOUNDARY = (
    "Project adoption evidence covers the generated AGENTS policy, version records, "
    "and canonical skill-suite reconciliation. It does not replace current executable "
    "model checks, tests, replay, UI click-through, release, or business-path evidence."
)

_RULE_MARKER_RE = re.compile(r"<!--\s*flowguard-rule:([a-z0-9_.-]+)\s*-->", re.IGNORECASE)
_RULE_SECTION_RE = re.compile(
    r"<!--\s*flowguard-rule:([a-z0-9_.-]+)\s*-->\s*"
    r"(.*?)"
    r"(?=<!--\s*flowguard-rule:[a-z0-9_.-]+\s*-->|"
    + re.escape(FLOWGUARD_AGENTS_END)
    + r"|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_MANAGED_BLOCK_RE = re.compile(
    re.escape(FLOWGUARD_AGENTS_BEGIN) + r".*?" + re.escape(FLOWGUARD_AGENTS_END),
    re.DOTALL,
)
_RENDERED_PACKAGE_RE = re.compile(
    r"FlowGuard check-engine version:\s*`([^`]+)`", re.IGNORECASE
)
_RENDERED_SCHEMA_RE = re.compile(
    r"FlowGuard schema version:\s*`([^`]+)`", re.IGNORECASE
)


@dataclass(frozen=True)
class ManagedAdoptionRule:
    """One stable, generated rule in the managed project prompt."""

    rule_id: str
    text_template: str

    def render(self, *, package_version: str, schema_version: str) -> str:
        return self.text_template.format(
            package_version=package_version,
            schema_version=schema_version,
            repository=FLOWGUARD_REPOSITORY_URL,
            manifest=FLOWGUARD_PROJECT_MANIFEST,
            machine_log=FLOWGUARD_PROJECT_LOG,
            markdown_log=FLOWGUARD_PROJECT_MARKDOWN_LOG,
        ).strip()


# Stable ids make rule loss observable without turning wording fragments into
# a second, private policy inventory.  The rendered text intentionally mirrors
# the complete current project rules, including the BCL and PPA additions that
# pre-date this generator refactor.
FLOWGUARD_MANAGED_RULES: tuple[ManagedAdoptionRule, ...] = (
    ManagedAdoptionRule(
        "project.scope",
        """## FlowGuard Project Rules

This project uses FlowGuard for non-trivial maintenance, feature work, bug
fixes, refactors, tests, release work, direct current replacement, and evidence-sensitive
process changes.""",
    ),
    ManagedAdoptionRule(
        "project.repository",
        """FlowGuard repository:
{repository}""",
    ),
    ManagedAdoptionRule(
        "skill_suite.agent_surface",
        """FlowGuard agent skill suite:
- Primary agent surface: `.agents/skills/`
- Default entry skill: `.agents/skills/model-first-function-flow/SKILL.md`
- Complete AI-agent setup means the agent can read `AGENTS.md` and all
  FlowGuard sibling `SKILL.md` files under `.agents/skills/`.
- The Python `flowguard` module/CLI is executable check support, not the
  AI-agent skill installation surface.""",
    ),
    ManagedAdoptionRule(
        "project.record_locations",
        """Project FlowGuard record:
- Manifest: `{manifest}`
- Machine log: `{machine_log}`
- Human log: `{markdown_log}`""",
    ),
    ManagedAdoptionRule(
        "project.rendered_versions",
        """Current adoption record:
- FlowGuard check-engine version: `{package_version}`
- FlowGuard schema version: `{schema_version}`""",
    ),
    ManagedAdoptionRule(
        "project.preflight_version_gate",
        """Before non-trivial work:
1. Verify the real FlowGuard check engine:
   `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`
2. Check the installed check-engine version:
   `python -c "import importlib.metadata as m; print(m.version('flowguard'))"`
3. Audit the project record:
   `python -m flowguard project-audit --root .`
4. Compare the installed version with `{manifest}`.
5. If the installed version is newer, run:
   `python -m flowguard project-adopt --root .`
   This directly replaces the managed project record with the one current
   FlowGuard shape. It does not read, convert, migrate, alias, or preserve an
   older FlowGuard skill/runtime shape. Then rerun only affected models/tests.
6. If the installed version is older than the project record, stop and connect
   a current FlowGuard check engine before claiming FlowGuard confidence.""",
    ),
    ManagedAdoptionRule(
        "runtime.current_authority_only",
        """FlowGuard skill and runtime guidance has one current authority only.
Former FlowGuard skill, model, check, receipt, and project-control shapes are
blocked and may appear only as exact rejection fixtures. There is no normal
compatibility reader, migration command, upgrade route, converter, alias,
renewal route, or fallback success path. Ordinary software may read historical
documents, data, or interfaces only when an explicit requirement assigns a
bounded FlowGuard owner, accepted and rejected cases, and a claim boundary.""",
    ),
    ManagedAdoptionRule(
        "lifecycle.default_replacement",
        """Default replacement means dispose the old path, old field, alias, wrapper, or
alternate success path. Delete, block, delegate, repair, replace, or
scope it out with a concrete reason; do not leave it as a second successful
route.""",
    ),
    ManagedAdoptionRule(
        "behavior.commitment_ledger",
        """Broad behavior work should use or update BehaviorCommitmentLedger before
claiming full coverage: register external behavior promises, map source
surfaces to commitments, assign exactly one primary owner model per
commitment, classify plane and actor kind, record typed relations/evidence,
and hand `path_sensitive=true`
commitments to Primary Path Authority. Do not treat every helper function,
file, field, or model as a behavior commitment.""",
    ),
    ManagedAdoptionRule(
        "behavior.plane_partitioning",
        """Keep product runtime behavior, AI-agent operations, and development lifecycle
behavior in one BehaviorCommitmentLedger structure but classify every
production commitment as exactly one of `product_runtime`, `agent_operation`,
or `development_process`. `commitment_kind` describes form, not plane.
Before non-trivial work, use the lightweight existing-model/commitment lookup
to select one same-plane primary context; keep other planes separated or
connected only by typed, reasoned relations. A related product commitment is
target context for an AI/process step, not an instruction that the step owns.
Model Miss backfeed searches the affected plane first and creates a gap row
only when no matching promise exists. This is recall guidance, not a universal
requirement to execute a model for every trivial action.""",
    ),
    ManagedAdoptionRule(
        "behavior.commitment_ledger_modes",
        """Before changing or claiming behavior coverage, classify the behavior-ledger
mode: `bootstrap_ledger`, `add_behavior`, `change_behavior`,
`remove_or_replace_behavior`, `coverage_gap_backfill`, or `model_miss_check`.
Only bootstrap and gap backfill require broad historical source discovery.
Ordinary add/change/remove work updates affected commitments, owner models,
DCAR cases, and TestMesh evidence. Model-miss checks first map the failure to
an existing same-plane commitment and owner model; keep typed related-plane
context separate, and create/backfill a commitment only when the observed
external behavior was not registered in that plane.""",
    ),
    ManagedAdoptionRule(
        "lifecycle.field_mesh",
        """Field-bearing work should use or update FieldLifecycleMesh: high-level behavior
models include behavior-bearing fields, while child/leaf field rows account all
discovered fields and record owner, readers, writers, projection, lifecycle,
and old-field disposition.""",
    ),
    ManagedAdoptionRule(
        "evidence.ui_and_payload",
        """UI runnable claims and file/work-package claims need current UI click-through
or artifact-payload evidence gates before broad done/release confidence.""",
    ),
    ManagedAdoptionRule(
        "behavior.primary_path_authority",
        """Path-sensitive behavior commitments need Primary Path Authority evidence before
broad confidence: one primary runtime authority per business intent, visible
primary failure, no automatic alternate success, ContractExhaustionMesh
coverage, TestMesh shards, and Risk Evidence Ledger gates.""",
    ),
    ManagedAdoptionRule(
        "behavior.exact_intent_reuse",
        """Treat one exact external user purpose as one stable `business_intent_id`, one
active Behavior Commitment, and one singular `primary_path_id`. UI, API, CLI,
aliases, adapters, wrappers, helpers, and compatibility surfaces for that same
purpose delegate to the selected commitment and path; they do not become
independent successful implementations.""",
    ),
    ManagedAdoptionRule(
        "ui.product_language",
        """Use the existing UI Flow Structure route to review one product-wide design
language across declared surfaces: typography hierarchy, components,
navigation, interaction, feedback, recovery, and transition semantics. Equal
semantic roles reuse the same rule or token; any exception is bounded,
presentation-only, and cannot change the business intent, commitment, path,
visibility class, or user-visible result.""",
    ),
    ManagedAdoptionRule(
        "ui.content_admission",
        """Classify UI content exactly once as `user_visible`, `user_on_demand`, or
`internal`. Ordinary UI renders only admitted user content; on-demand content
needs an explicit reveal and return path, while internal identities, audit
fields, evidence metadata, diagnostics, and routing state stay internal by
default.""",
    ),
    ManagedAdoptionRule(
        "process.development_process_flow",
        """Non-trivial rough-plan discussion, multi-skill/tool workflow setup, staged
execution, install/sync, release/archive/publish, post-change owner scans, and
final process claims enter `flowguard-development-process-flow` first as the
development-process simulator. Record `plan_detailing`, `agent_workflow`, and
`execution_freshness` modes; delegate to PlanDetailing or
AgentWorkflowRehearsal only when explicit or simulator-selected.
DevelopmentProcessFlow owns lifecycle order/freshness; AgentWorkflowRehearsal
owns AI-operation planning. Both may reference product commitments and their
evidence without copying product behavior into their own steps.""",
    ),
    ManagedAdoptionRule(
        "process.spec_work_package_reconciliation",
        """When OpenSpec, Spec Kit, or another supported specification provider is in
scope, keep provider tasks native and reconcile them bidirectionally with
FlowGuard obligations/checks through one development-process Spec Work
Package. Begin and close one immutable input session, reuse only exact terminal
receipts within an explicit boundary, and block archive when mappings,
post-snapshot evidence, provider verification, or receipt freshness is
missing. Internal work-package fields never become product UI content.""",
    ),
    ManagedAdoptionRule(
        "process.post_change_scan",
        """After non-trivial FlowGuard-managed work, let DevelopmentProcessFlow consume
post-change scan signals for changed artifacts, skipped routes, stale evidence,
open obligations, or split/reduction pressure. The scan output routes each gap
to the owning specialist, such as Model-Test Alignment, Architecture
Reduction, StructureMesh, ModelMesh, TestMesh, or AgentWorkflowRehearsal.""",
    ),
    ManagedAdoptionRule(
        "validation.native_owner_receipts",
        """Keep every native test with exactly one existing owner. Before validation,
list the affected native checks, owner, exact functional input components, and
receipt order. SkillGuard/TestMesh may request a missing owner receipt and
aggregate current receipts, but a consumer must not copy, wrap, or carry the
owner command. Only a declared functional input change invalidates that owner;
reports, receipts, logs, timestamps, task checkmarks, and install bookkeeping
are outputs and must not trigger native retesting. Run one final full gate only
after source and tool identities freeze, under one explicit owner, never through
`--resume`, a scheduled task, a background retry, or an unattended helper. If
a launcher times out or is interrupted, confirm the whole descendant process
tree is absent before accepting evidence or starting another validation.""",
    ),
    ManagedAdoptionRule(
        "claim.no_fake_adoption",
        """Do not create a fake local FlowGuard replacement. Do not claim full FlowGuard
completion from an AGENTS/manifest/log update alone; executable model checks,
tests, replay, and closure evidence still need to be current for the claim.""",
    ),
)

FLOWGUARD_REQUIRED_RULE_IDS = tuple(rule.rule_id for rule in FLOWGUARD_MANAGED_RULES)


@dataclass(frozen=True)
class ProjectAdoptionFinding:
    """One deterministic finding from project adoption work."""

    severity: str
    category: str
    message: str
    recommendation: str = ""
    file_path: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        severity = str(self.severity).lower()
        if severity not in {"info", "warning", "blocked"}:
            raise ValueError("severity must be info, warning, or blocked")
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "category", str(self.category))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "recommendation", str(self.recommendation or ""))
        object.__setattr__(self, "file_path", str(self.file_path or ""))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def code(self) -> str:
        return self.category

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "recommendation": self.recommendation,
            "file_path": self.file_path,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class _SuiteEvidence:
    ok: bool
    status: str
    inventory_hash: str = ""
    semantic_hash: str = ""
    findings: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "ok", bool(self.ok))
        object.__setattr__(self, "status", str(self.status or ("pass" if self.ok else "blocked")))
        object.__setattr__(self, "inventory_hash", str(self.inventory_hash or ""))
        object.__setattr__(self, "semantic_hash", str(self.semantic_hash or ""))
        object.__setattr__(self, "findings", tuple(dict(item) for item in self.findings))


@dataclass(frozen=True)
class ProjectAdoptionReport:
    """Structured, evidence-rich report for a project adoption command."""

    root: str
    action: str
    installed_package_version: str
    schema_version: str
    manifest_package_version: str = ""
    manifest_schema_version: str = ""
    rendered_package_version: str = ""
    rendered_schema_version: str = ""
    inventory_hash: str = ""
    suite_semantic_hash: str = ""
    suite_status: str = "unresolved"
    suite_findings: tuple[Mapping[str, Any], ...] = ()
    managed_block_semantic_hash: str = ""
    proposed_managed_block_semantic_hash: str = ""
    required_rule_ids: tuple[str, ...] = FLOWGUARD_REQUIRED_RULE_IDS
    observed_rule_ids: tuple[str, ...] = ()
    missing_rule_ids: tuple[str, ...] = ()
    semantic_rule_changes: FrozenMetadata = field(default_factory=tuple, compare=False)
    proposed_files: tuple[str, ...] = ()
    required_revalidation: tuple[str, ...] = ()
    checks: tuple[str, ...] = ()
    skipped_steps: tuple[str, ...] = ()
    claim_boundary: str = PROJECT_ADOPTION_CLAIM_BOUNDARY
    before_state: FrozenMetadata = field(default_factory=tuple, compare=False)
    after_state: FrozenMetadata = field(default_factory=tuple, compare=False)
    findings: tuple[ProjectAdoptionFinding, ...] = ()
    written_files: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "suite_findings", tuple(dict(item) for item in self.suite_findings))
        object.__setattr__(self, "required_rule_ids", tuple(str(item) for item in self.required_rule_ids))
        object.__setattr__(self, "observed_rule_ids", tuple(str(item) for item in self.observed_rule_ids))
        object.__setattr__(self, "missing_rule_ids", tuple(str(item) for item in self.missing_rule_ids))
        object.__setattr__(self, "semantic_rule_changes", freeze_metadata(self.semantic_rule_changes))
        object.__setattr__(self, "proposed_files", tuple(str(item) for item in self.proposed_files))
        object.__setattr__(self, "required_revalidation", tuple(str(item) for item in self.required_revalidation))
        object.__setattr__(self, "checks", tuple(str(item) for item in self.checks))
        object.__setattr__(self, "skipped_steps", tuple(str(item) for item in self.skipped_steps))
        object.__setattr__(self, "before_state", freeze_metadata(self.before_state))
        object.__setattr__(self, "after_state", freeze_metadata(self.after_state))

    @property
    def ok(self) -> bool:
        return not any(finding.severity == "blocked" for finding in self.findings)

    @property
    def status(self) -> str:
        if not self.ok:
            return PROJECT_ADOPTION_STATUS_BLOCKED
        if self.findings:
            return PROJECT_ADOPTION_STATUS_PASS_WITH_GAPS
        return PROJECT_ADOPTION_STATUS_PASS

    @property
    def blockers(self) -> tuple[ProjectAdoptionFinding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == "blocked")

    def to_dict(self) -> dict[str, Any]:
        versions = {
            "installed_package_version": self.installed_package_version,
            "installed_schema_version": self.schema_version,
            "manifest_package_version": self.manifest_package_version,
            "manifest_schema_version": self.manifest_schema_version,
            "rendered_package_version": self.rendered_package_version,
            "rendered_schema_version": self.rendered_schema_version,
        }
        return {
            "artifact_type": "flowguard_project_adoption_report",
            "root": self.root,
            "action": self.action,
            "mode": self.action,
            "ok": self.ok,
            "status": self.status,
            "canonical_status": self.status,
            "repository": FLOWGUARD_REPOSITORY_URL,
            "installed_package_version": self.installed_package_version,
            "schema_version": self.schema_version,
            "manifest_package_version": self.manifest_package_version,
            "manifest_schema_version": self.manifest_schema_version,
            "rendered_package_version": self.rendered_package_version,
            "rendered_schema_version": self.rendered_schema_version,
            "versions": versions,
            "inventory_hash": self.inventory_hash,
            "suite_semantic_hash": self.suite_semantic_hash,
            "suite_status": self.suite_status,
            "suite_ok": self.suite_status == PROJECT_ADOPTION_STATUS_PASS,
            "suite_findings": [dict(item) for item in self.suite_findings],
            "suite": {
                "ok": self.suite_status == PROJECT_ADOPTION_STATUS_PASS,
                "status": self.suite_status,
                "inventory_hash": self.inventory_hash,
                "semantic_hash": self.suite_semantic_hash,
                "findings": [dict(item) for item in self.suite_findings],
            },
            "managed_block_semantic_hash": self.managed_block_semantic_hash,
            "proposed_managed_block_semantic_hash": self.proposed_managed_block_semantic_hash,
            "required_rule_ids": list(self.required_rule_ids),
            "observed_rule_ids": list(self.observed_rule_ids),
            "missing_rule_ids": list(self.missing_rule_ids),
            "semantic_rule_changes": to_jsonable(dict(self.semantic_rule_changes)),
            "proposed_files": list(self.proposed_files),
            "required_revalidation": list(self.required_revalidation),
            "minimum_revalidation": list(self.required_revalidation),
            "checks": list(self.checks),
            "skipped_steps": list(self.skipped_steps),
            "claim_boundary": self.claim_boundary,
            "before": to_jsonable(dict(self.before_state)),
            "after": to_jsonable(dict(self.after_state)),
            "written_files": list(self.written_files),
            "findings": [finding.to_dict() for finding in self.findings],
            "blockers": [finding.to_dict() for finding in self.blockers],
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def format_text(self) -> str:
        lines = [
            "=== flowguard project adoption ===",
            f"action: {self.action}",
            f"mode: {self.action}",
            f"status: {self.status}",
            f"repository: {FLOWGUARD_REPOSITORY_URL}",
            f"installed_package_version: {self.installed_package_version}",
            f"manifest_package_version: {self.manifest_package_version or 'missing'}",
            f"rendered_package_version: {self.rendered_package_version or 'missing'}",
            f"schema_version: {self.schema_version}",
            f"suite_status: {self.suite_status}",
            f"inventory_hash: {self.inventory_hash or 'unavailable'}",
            f"managed_block_semantic_hash: {self.managed_block_semantic_hash or 'unavailable'}",
        ]
        if self.proposed_files:
            lines.append("proposed_files:")
            lines.extend(f"- {path}" for path in self.proposed_files)
        if self.written_files:
            lines.append("written_files:")
            lines.extend(f"- {path}" for path in self.written_files)
        if self.required_revalidation:
            lines.append("required_revalidation:")
            lines.extend(f"- {item}" for item in self.required_revalidation)
        for finding in self.findings:
            lines.extend(
                [
                    "",
                    f"{finding.severity.upper()}: {finding.category}",
                    f"message: {finding.message}",
                ]
            )
            if finding.file_path:
                lines.append(f"file: {finding.file_path}")
            if finding.recommendation:
                lines.append(f"recommendation: {finding.recommendation}")
        lines.extend(["", f"claim_boundary: {self.claim_boundary}"])
        return "\n".join(lines)


def installed_flowguard_package_version() -> str:
    """Return the installed FlowGuard check-engine package version, or empty."""

    try:
        return importlib.metadata.version("flowguard")
    except importlib.metadata.PackageNotFoundError:
        return ""


def current_project_manifest_text(
    *,
    package_version: str | None = None,
    schema_version: str = SCHEMA_VERSION,
    verified_by: str = "FlowGuard project-adopt",
) -> str:
    """Build the canonical ``.flowguard/project.toml`` text."""

    package = package_version if package_version is not None else installed_flowguard_package_version()
    verified_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return (
        "[flowguard]\n"
        f'repository = "{FLOWGUARD_REPOSITORY_URL}"\n'
        f'adopted_package_version = "{package}"\n'
        f'schema_version = "{schema_version}"\n'
        f'last_verified_at = "{verified_at}"\n'
        f'last_verified_by = "{verified_by}"\n'
        'agents_path = "AGENTS.md"\n'
        "\n"
        "[policy]\n"
        "direct_current_replacement = true\n"
        "former_flowguard_shapes_blocked = true\n"
        "ordinary_software_history_requires_explicit_contract = true\n"
        "require_adoption_log = true\n"
        "require_model_update_for_behavior_changes = true\n"
    )


def build_flowguard_agents_block(
    *,
    package_version: str | None = None,
    schema_version: str = SCHEMA_VERSION,
) -> str:
    """Build the managed AGENTS block from the stable rule inventory."""

    package = package_version if package_version is not None else installed_flowguard_package_version()
    parts = [FLOWGUARD_AGENTS_BEGIN]
    for rule in FLOWGUARD_MANAGED_RULES:
        parts.append(f"<!-- flowguard-rule:{rule.rule_id} -->")
        parts.append(rule.render(package_version=package, schema_version=schema_version))
    parts.append(FLOWGUARD_AGENTS_END)
    return "\n\n".join(parts)


def extract_managed_agents_block(text: str) -> str:
    """Return the first complete managed block, or an empty string."""

    match = _MANAGED_BLOCK_RE.search(str(text or ""))
    return match.group(0) if match is not None else ""


def normalize_managed_agents_block(text: str) -> str:
    """Normalize insignificant formatting and dynamic version values."""

    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    value = _RULE_MARKER_RE.sub("", value)
    value = _RENDERED_PACKAGE_RE.sub(
        "FlowGuard check-engine version: `{package_version}`", value
    )
    value = _RENDERED_SCHEMA_RE.sub(
        "FlowGuard schema version: `{schema_version}`", value
    )
    return re.sub(r"\s+", " ", value).strip()


def managed_block_semantic_hash(text: str) -> str:
    """Return a deterministic hash of normalized managed-block semantics."""

    normalized = normalize_managed_agents_block(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""


def managed_rule_ids_in_block(text: str) -> tuple[str, ...]:
    """Return rule ids whose marker and complete generated clause agree.

    The stable id is part of the semantic contract rather than a decorative
    comment.  Looking for clause text anywhere in the block would allow a
    missing or relabelled marker to pass and is ambiguous when one rule names
    another (for example, the BCL handoff names Primary Path Authority).
    """

    managed_block = extract_managed_agents_block(text) or str(text or "")
    if not managed_block.strip():
        return ()

    expected = {
        rule.rule_id: normalize_managed_agents_block(
            rule.render(
                package_version="{package_version}",
                schema_version="{schema_version}",
            )
        )
        for rule in FLOWGUARD_MANAGED_RULES
    }
    marker_counts: dict[str, int] = {}
    matching_counts: dict[str, int] = {}
    for match in _RULE_SECTION_RE.finditer(managed_block):
        rule_id = match.group(1).lower()
        clause = normalize_managed_agents_block(match.group(2))
        marker_counts[rule_id] = marker_counts.get(rule_id, 0) + 1
        if rule_id in expected and clause == expected[rule_id]:
            matching_counts[rule_id] = matching_counts.get(rule_id, 0) + 1

    return tuple(
        rule.rule_id
        for rule in FLOWGUARD_MANAGED_RULES
        if marker_counts.get(rule.rule_id) == 1
        and matching_counts.get(rule.rule_id) == 1
    )


def update_agents_text(existing_text: str, managed_block: str) -> str:
    """Insert or replace the managed FlowGuard AGENTS block."""

    if FLOWGUARD_AGENTS_BEGIN in existing_text and FLOWGUARD_AGENTS_END in existing_text:
        return _MANAGED_BLOCK_RE.sub(managed_block, existing_text, count=1)
    if not existing_text.strip():
        return managed_block + "\n"
    return existing_text.rstrip() + "\n\n" + managed_block + "\n"


def audit_project_adoption(root: str | Path = ".") -> ProjectAdoptionReport:
    """Read-only semantic audit of project adoption and suite state."""

    root_path = Path(root).resolve()
    package_version = installed_flowguard_package_version()
    manifest = _read_manifest(root_path / FLOWGUARD_PROJECT_MANIFEST)
    manifest_package = str(manifest.get("adopted_package_version", ""))
    manifest_schema = str(manifest.get("schema_version", ""))
    agents_text = _read_text(root_path / "AGENTS.md")
    managed_block = extract_managed_agents_block(agents_text)
    expected_block = build_flowguard_agents_block(
        package_version=package_version,
        schema_version=SCHEMA_VERSION,
    )
    suite = _load_suite_evidence(root_path)
    findings = _audit_findings(
        root_path,
        package_version,
        manifest,
        manifest_package,
        manifest_schema,
        agents_text,
        managed_block,
        expected_block,
        suite,
    )
    rendered_package, rendered_schema = _rendered_versions(managed_block)
    observed_ids = managed_rule_ids_in_block(managed_block)
    missing_ids = tuple(rule_id for rule_id in FLOWGUARD_REQUIRED_RULE_IDS if rule_id not in observed_ids)
    state = _adoption_state(
        package_version=package_version,
        manifest_package=manifest_package,
        manifest_schema=manifest_schema,
        rendered_package=rendered_package,
        rendered_schema=rendered_schema,
        semantic_hash=managed_block_semantic_hash(managed_block),
        inventory_hash=suite.inventory_hash,
    )
    return ProjectAdoptionReport(
        root=str(root_path),
        action=PROJECT_ADOPTION_ACTION_AUDIT,
        installed_package_version=package_version,
        schema_version=SCHEMA_VERSION,
        manifest_package_version=manifest_package,
        manifest_schema_version=manifest_schema,
        rendered_package_version=rendered_package,
        rendered_schema_version=rendered_schema,
        inventory_hash=suite.inventory_hash,
        suite_semantic_hash=suite.semantic_hash,
        suite_status=suite.status,
        suite_findings=suite.findings,
        managed_block_semantic_hash=managed_block_semantic_hash(managed_block),
        proposed_managed_block_semantic_hash=managed_block_semantic_hash(expected_block),
        observed_rule_ids=observed_ids,
        missing_rule_ids=missing_ids,
        semantic_rule_changes=_semantic_rule_changes(managed_block, expected_block),
        required_revalidation=_minimum_revalidation(),
        checks=("managed_block_semantic_parity", "adoption_version_parity", "skill_suite_inventory"),
        skipped_steps=("Audit is read-only; no project file or adoption log was written.",),
        before_state=state,
        after_state=state,
        findings=tuple(findings),
    )


def adopt_project(
    root: str | Path = ".",
    *,
    verified_by: str = "FlowGuard project-adopt",
) -> ProjectAdoptionReport:
    """Write target-project FlowGuard records after generator preflight."""

    return _write_project_adoption(
        root,
        action=PROJECT_ADOPTION_ACTION_ADOPT,
        verified_by=verified_by,
    )


def _write_project_adoption(
    root: str | Path,
    *,
    action: str,
    verified_by: str,
) -> ProjectAdoptionReport:
    root_path = Path(root).resolve()
    package_version = installed_flowguard_package_version()
    manifest_path = root_path / FLOWGUARD_PROJECT_MANIFEST
    manifest = _read_manifest(manifest_path)
    manifest_package = str(manifest.get("adopted_package_version", ""))
    manifest_schema = str(manifest.get("schema_version", ""))
    agents_path = root_path / "AGENTS.md"
    existing_agents = _read_text(agents_path)
    current_block = extract_managed_agents_block(existing_agents)
    proposed_block = build_flowguard_agents_block(
        package_version=package_version,
        schema_version=SCHEMA_VERSION,
    )
    updated_agents = update_agents_text(existing_agents, proposed_block)
    manifest_text = current_project_manifest_text(
        package_version=package_version,
        schema_version=SCHEMA_VERSION,
        verified_by=verified_by,
    )
    suite = _load_suite_evidence(root_path)
    audit_findings = _audit_findings(
        root_path,
        package_version,
        manifest,
        manifest_package,
        manifest_schema,
        existing_agents,
        current_block,
        proposed_block,
        suite,
    )
    rendered_package, rendered_schema = _rendered_versions(current_block)
    observed_ids = managed_rule_ids_in_block(current_block)
    missing_ids = tuple(rule_id for rule_id in FLOWGUARD_REQUIRED_RULE_IDS if rule_id not in observed_ids)
    proposed_ids = managed_rule_ids_in_block(proposed_block)
    proposed_missing_ids = tuple(
        rule_id for rule_id in FLOWGUARD_REQUIRED_RULE_IDS if rule_id not in proposed_ids
    )

    blockers = _write_preflight_blockers(
        package_version=package_version,
        manifest_package=manifest_package,
        proposed_missing_ids=proposed_missing_ids,
        root_path=root_path,
    )
    findings = _projected_current_adoption_findings(audit_findings)
    findings.extend(blockers)
    findings = _dedupe_findings(findings)

    proposed_files = _proposed_files(
        root_path=root_path,
        agents_changed=updated_agents != existing_agents,
        manifest_changed=_read_text(manifest_path) != manifest_text,
        include_logs=True,
    )
    before_state = _adoption_state(
        package_version=package_version,
        manifest_package=manifest_package,
        manifest_schema=manifest_schema,
        rendered_package=rendered_package,
        rendered_schema=rendered_schema,
        semantic_hash=managed_block_semantic_hash(current_block),
        inventory_hash=suite.inventory_hash,
    )
    after_state = _adoption_state(
        package_version=package_version,
        manifest_package=package_version,
        manifest_schema=SCHEMA_VERSION,
        rendered_package=package_version,
        rendered_schema=SCHEMA_VERSION,
        semantic_hash=managed_block_semantic_hash(proposed_block),
        inventory_hash=suite.inventory_hash,
    )
    skipped_steps = [
        "Project adoption does not replace executable model checks, tests, replay, or closure evidence."
    ]
    if any(finding.severity == "blocked" for finding in findings):
        skipped_steps.append("Writing stopped before mutation because a hard preflight gate failed.")
        return _build_report(
            root_path=root_path,
            action=action,
            package_version=package_version,
            manifest_package=manifest_package,
            manifest_schema=manifest_schema,
            rendered_package=rendered_package,
            rendered_schema=rendered_schema,
            suite=suite,
            current_block=current_block,
            proposed_block=proposed_block,
            observed_ids=observed_ids,
            missing_ids=missing_ids,
            proposed_files=proposed_files,
            skipped_steps=tuple(skipped_steps),
            before_state=before_state,
            after_state=before_state,
            findings=tuple(_dedupe_findings(findings)),
        )

    written: list[str] = []
    if updated_agents != existing_agents:
        agents_path.write_text(updated_agents, encoding="utf-8")
        written.append(str(agents_path))

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if _read_text(manifest_path) != manifest_text:
        manifest_path.write_text(manifest_text, encoding="utf-8")
        written.append(str(manifest_path))

    post_audit = audit_project_adoption(root_path)
    post_findings = list(post_audit.findings)
    if action == PROJECT_ADOPTION_ACTION_ADOPT:
        post_findings = [
            _with_severity(finding, "warning")
            if finding.category == "suite_inventory_unresolved"
            else finding
            for finding in post_findings
        ]
    post_findings.append(
        ProjectAdoptionFinding(
            "info",
            "adoption_record_written",
            "FlowGuard project AGENTS block and manifest were written or refreshed.",
            "Run the required revalidation before broad confidence claims.",
        )
    )
    post_findings = _dedupe_findings(post_findings)
    post_ok = not any(finding.severity == "blocked" for finding in post_findings)
    log_jsonl = root_path / FLOWGUARD_PROJECT_LOG
    log_markdown = root_path / FLOWGUARD_PROJECT_MARKDOWN_LOG
    checks = (
        AdoptionCommandResult(
            "managed adoption rule-set preflight",
            not proposed_missing_ids,
            summary="generated block contains every required stable rule",
        ),
        AdoptionCommandResult(
            "canonical FlowGuard skill-suite validation",
            True,
            summary=suite.status,
        ),
        AdoptionCommandResult(
            "post-write project adoption audit",
            post_ok,
            summary="semantic and version parity after write",
        ),
    )
    log_entry = make_adoption_log_entry(
        task_id=f"flowguard-project-{action}",
        project=root_path.name,
        task_summary=f"FlowGuard project {action} record update",
        trigger_reason="target project requires current semantic adoption and version records",
        status="completed" if post_ok else "blocked",
        commands=checks,
        findings=tuple(f"{item.category}: {item.message}" for item in post_findings),
        skipped_steps=tuple(skipped_steps),
        next_actions=_minimum_revalidation(),
        metadata={
            "actual_mode": action,
            "before": before_state,
            "after": after_state,
            "inventory_hash": suite.inventory_hash,
            "suite_semantic_hash": suite.semantic_hash,
            "managed_block_semantic_hash_before": managed_block_semantic_hash(current_block),
            "managed_block_semantic_hash_after": managed_block_semantic_hash(proposed_block),
            "required_rule_ids": FLOWGUARD_REQUIRED_RULE_IDS,
            "checks": tuple(command.command for command in checks),
            "claim_boundary": PROJECT_ADOPTION_CLAIM_BOUNDARY,
        },
    )
    append_jsonl(log_jsonl, log_entry)
    append_markdown_log(log_markdown, log_entry)
    written.extend((str(log_jsonl), str(log_markdown)))

    return ProjectAdoptionReport(
        root=str(root_path),
        action=action,
        installed_package_version=package_version,
        schema_version=SCHEMA_VERSION,
        manifest_package_version=package_version,
        manifest_schema_version=SCHEMA_VERSION,
        rendered_package_version=package_version,
        rendered_schema_version=SCHEMA_VERSION,
        inventory_hash=suite.inventory_hash,
        suite_semantic_hash=suite.semantic_hash,
        suite_status=suite.status,
        suite_findings=suite.findings,
        managed_block_semantic_hash=managed_block_semantic_hash(proposed_block),
        proposed_managed_block_semantic_hash=managed_block_semantic_hash(proposed_block),
        observed_rule_ids=FLOWGUARD_REQUIRED_RULE_IDS,
        missing_rule_ids=(),
        semantic_rule_changes=_semantic_rule_changes(current_block, proposed_block),
        proposed_files=proposed_files,
        required_revalidation=_minimum_revalidation(),
        checks=(
            "managed_block_semantic_parity",
            "adoption_version_parity",
            "skill_suite_inventory",
            "post_write_project_audit",
        ),
        skipped_steps=tuple(skipped_steps),
        before_state=before_state,
        after_state=after_state,
        findings=tuple(post_findings),
        written_files=tuple(written),
    )


def _build_report(
    *,
    root_path: Path,
    action: str,
    package_version: str,
    manifest_package: str,
    manifest_schema: str,
    rendered_package: str,
    rendered_schema: str,
    suite: _SuiteEvidence,
    current_block: str,
    proposed_block: str,
    observed_ids: tuple[str, ...],
    missing_ids: tuple[str, ...],
    proposed_files: tuple[str, ...],
    skipped_steps: tuple[str, ...],
    before_state: Mapping[str, Any],
    after_state: Mapping[str, Any],
    findings: tuple[ProjectAdoptionFinding, ...],
) -> ProjectAdoptionReport:
    return ProjectAdoptionReport(
        root=str(root_path),
        action=action,
        installed_package_version=package_version,
        schema_version=SCHEMA_VERSION,
        manifest_package_version=manifest_package,
        manifest_schema_version=manifest_schema,
        rendered_package_version=rendered_package,
        rendered_schema_version=rendered_schema,
        inventory_hash=suite.inventory_hash,
        suite_semantic_hash=suite.semantic_hash,
        suite_status=suite.status,
        suite_findings=suite.findings,
        managed_block_semantic_hash=managed_block_semantic_hash(current_block),
        proposed_managed_block_semantic_hash=managed_block_semantic_hash(proposed_block),
        observed_rule_ids=observed_ids,
        missing_rule_ids=missing_ids,
        semantic_rule_changes=_semantic_rule_changes(current_block, proposed_block),
        proposed_files=proposed_files,
        required_revalidation=_minimum_revalidation(),
        checks=("managed_block_semantic_parity", "adoption_version_parity", "skill_suite_inventory"),
        skipped_steps=skipped_steps,
        before_state=before_state,
        after_state=after_state,
        findings=findings,
    )


def _managed_block_shape_findings(
    agents_text: str,
    agents_path: Path,
) -> list[ProjectAdoptionFinding]:
    """Reject ambiguous ownership markers before any generated rewrite."""

    begin_count = str(agents_text or "").count(FLOWGUARD_AGENTS_BEGIN)
    end_count = str(agents_text or "").count(FLOWGUARD_AGENTS_END)
    complete_count = len(_MANAGED_BLOCK_RE.findall(str(agents_text or "")))
    if begin_count == end_count == complete_count == 0:
        return []
    if begin_count == end_count == complete_count == 1:
        return []
    return [
        ProjectAdoptionFinding(
            "blocked",
            "managed_block_cardinality_mismatch",
            "AGENTS.md does not contain exactly one unambiguous managed FlowGuard block.",
            "Repair duplicate or unmatched managed markers before running project-adopt.",
            str(agents_path),
            {
                "begin_marker_count": begin_count,
                "end_marker_count": end_count,
                "complete_block_count": complete_count,
            },
        )
    ]


def _audit_findings(
    root_path: Path,
    package_version: str,
    manifest: dict[str, Any],
    manifest_package: str,
    manifest_schema: str,
    agents_text: str,
    managed_block: str,
    expected_block: str,
    suite: _SuiteEvidence,
) -> list[ProjectAdoptionFinding]:
    findings: list[ProjectAdoptionFinding] = []
    agents_path = root_path / "AGENTS.md"
    manifest_path = root_path / FLOWGUARD_PROJECT_MANIFEST
    findings.extend(_managed_block_shape_findings(agents_text, agents_path))
    if not managed_block:
        findings.append(
            ProjectAdoptionFinding(
                "blocked",
                "missing_agents_block",
                "Target project does not have one complete managed FlowGuard AGENTS block.",
                "Run project-adopt before non-trivial FlowGuard work.",
                str(agents_path),
            )
        )
    if not manifest:
        findings.append(
            ProjectAdoptionFinding(
                "blocked",
                "missing_project_manifest",
                "Target project does not have a readable .flowguard/project.toml.",
                "Run project-adopt to establish the current version record.",
                str(manifest_path),
            )
        )
    if not package_version:
        findings.append(
            ProjectAdoptionFinding(
                "blocked",
                "flowguard_package_unavailable",
                "The real FlowGuard check-engine version could not be found.",
                f"Connect FlowGuard check execution from {FLOWGUARD_REPOSITORY_URL}.",
            )
        )
    if manifest and str(manifest.get("repository", "")) != FLOWGUARD_REPOSITORY_URL:
        findings.append(
            ProjectAdoptionFinding(
                "blocked",
                "repository_url_mismatch",
                "Project manifest does not point to the canonical FlowGuard repository.",
                f"Use {FLOWGUARD_REPOSITORY_URL}.",
                str(manifest_path),
            )
        )
    if manifest and not manifest_package:
        findings.append(
            ProjectAdoptionFinding(
                "blocked",
                "manifest_package_version_missing",
                "Project manifest does not record the adopted FlowGuard package version.",
                "Run project-adopt to replace the record with the canonical current version.",
                str(manifest_path),
            )
        )
    if manifest and not manifest_schema:
        findings.append(
            ProjectAdoptionFinding(
                "blocked",
                "manifest_schema_version_missing",
                "Project manifest does not record the adopted FlowGuard schema version.",
                "Run project-adopt to replace the record with the canonical current schema.",
                str(manifest_path),
            )
        )
    if manifest_schema and manifest_schema != SCHEMA_VERSION:
        findings.append(
            ProjectAdoptionFinding(
                "blocked",
                "schema_version_mismatch",
                "Project manifest schema version differs from the installed FlowGuard schema.",
                "Run project-adopt and rerun only affected owners before broad confidence.",
                str(manifest_path),
                {"manifest_schema_version": manifest_schema, "installed_schema_version": SCHEMA_VERSION},
            )
        )
    if manifest_package and package_version:
        comparison = compare_versions(package_version, manifest_package)
        if comparison is None:
            findings.append(
                ProjectAdoptionFinding(
                    "blocked",
                    "unknown_flowguard_version_comparison",
                    "Installed and manifest FlowGuard versions could not be compared safely.",
                    "Use comparable release versions before writing adoption records.",
                    str(manifest_path),
                    {"installed_package_version": package_version, "manifest_package_version": manifest_package},
                )
            )
        elif comparison < 0:
            findings.append(
                ProjectAdoptionFinding(
                    "blocked",
                    "installed_flowguard_older",
                    "Installed FlowGuard check engine is older than the project-recorded version.",
                    "Connect the current FlowGuard check engine before writing or claiming confidence.",
                    str(manifest_path),
                    {"installed_package_version": package_version, "manifest_package_version": manifest_package},
                )
            )
        elif comparison > 0:
            findings.append(
                ProjectAdoptionFinding(
                    "blocked",
                    "project_flowguard_current_replacement_required",
                    "Installed FlowGuard is newer than the project-recorded version.",
                    "Run project-adopt for direct current replacement, then rerun the minimum affected validation.",
                    str(manifest_path),
                    {"installed_package_version": package_version, "manifest_package_version": manifest_package},
                )
            )

    if managed_block:
        rendered_package, rendered_schema = _rendered_versions(managed_block)
        if not rendered_package:
            findings.append(
                ProjectAdoptionFinding(
                    "blocked",
                    "rendered_version_missing",
                    "Managed AGENTS block does not record a FlowGuard package version.",
                    "Regenerate the managed block with the current generator.",
                    str(agents_path),
                )
            )
        elif rendered_package != package_version or (
            manifest_package and rendered_package != manifest_package
        ):
            findings.append(
                ProjectAdoptionFinding(
                    "blocked",
                    "rendered_version_mismatch",
                    "Managed AGENTS version does not agree with installed and manifest versions.",
                    "Run project-adopt to replace the managed block with the current generated form.",
                    str(agents_path),
                    {
                        "rendered_package_version": rendered_package,
                        "installed_package_version": package_version,
                        "manifest_package_version": manifest_package,
                    },
                )
            )
        if not rendered_schema:
            findings.append(
                ProjectAdoptionFinding(
                    "blocked",
                    "rendered_schema_version_missing",
                    "Managed AGENTS block does not record a FlowGuard schema version.",
                    "Regenerate the managed block with the current generator.",
                    str(agents_path),
                )
            )
        elif rendered_schema != SCHEMA_VERSION or (
            manifest_schema and rendered_schema != manifest_schema
        ):
            findings.append(
                ProjectAdoptionFinding(
                    "blocked",
                    "rendered_schema_version_mismatch",
                    "Managed AGENTS schema version does not agree with installed and manifest schemas.",
                    "Regenerate the managed block and rerun project-audit.",
                    str(agents_path),
                    {
                        "rendered_schema_version": rendered_schema,
                        "installed_schema_version": SCHEMA_VERSION,
                        "manifest_schema_version": manifest_schema,
                    },
                )
            )

        observed_ids = managed_rule_ids_in_block(managed_block)
        missing_ids = tuple(
            rule_id for rule_id in FLOWGUARD_REQUIRED_RULE_IDS if rule_id not in observed_ids
        )
        for rule_id in missing_ids:
            findings.append(
                ProjectAdoptionFinding(
                    "blocked",
                    "missing_managed_rule",
                    f"Managed AGENTS block is missing required rule {rule_id}.",
                    "Regenerate the managed block; do not hand-edit away required governance.",
                    str(agents_path),
                    {"rule_id": rule_id},
                )
            )
        if not missing_ids and normalize_managed_agents_block(managed_block) != normalize_managed_agents_block(expected_block):
            findings.append(
                ProjectAdoptionFinding(
                    "blocked",
                    "managed_block_semantic_drift",
                    "Managed AGENTS block differs semantically from the installed generator.",
                    "Run project-adopt to replace the managed block from the current generator.",
                    str(agents_path),
                    {
                        "actual_semantic_hash": managed_block_semantic_hash(managed_block),
                        "expected_semantic_hash": managed_block_semantic_hash(expected_block),
                    },
                )
            )

    if not suite.ok:
        findings.append(
            ProjectAdoptionFinding(
                "blocked",
                "suite_inventory_unresolved",
                "Canonical FlowGuard skill-suite validation is unresolved.",
                "Resolve every canonical suite finding before claiming suite-wide confidence.",
                metadata={
                    "suite_status": suite.status,
                    "inventory_hash": suite.inventory_hash,
                    "finding_codes": tuple(str(item.get("code", "")) for item in suite.findings),
                },
            )
        )
    return _dedupe_findings(findings)


def _write_preflight_blockers(
    *,
    package_version: str,
    manifest_package: str,
    proposed_missing_ids: tuple[str, ...],
    root_path: Path,
) -> list[ProjectAdoptionFinding]:
    blockers: list[ProjectAdoptionFinding] = []
    if not package_version:
        blockers.append(
            ProjectAdoptionFinding(
                "blocked",
                "flowguard_package_unavailable",
                "Writing adoption records requires an importable installed FlowGuard engine.",
                f"Connect FlowGuard from {FLOWGUARD_REPOSITORY_URL}.",
            )
        )
    comparison = compare_versions(package_version, manifest_package) if package_version and manifest_package else 0
    if comparison is None:
        blockers.append(
            ProjectAdoptionFinding(
                "blocked",
                "unknown_flowguard_version_comparison",
                "Writing stopped because installed and manifest versions are not safely comparable.",
                "Use comparable release versions before retrying.",
                str(root_path / FLOWGUARD_PROJECT_MANIFEST),
            )
        )
    elif comparison < 0:
        blockers.append(
            ProjectAdoptionFinding(
                "blocked",
                "installed_flowguard_older",
                "Writing stopped because the installed engine is older than the project record.",
                "Connect a current FlowGuard engine before retrying.",
                str(root_path / FLOWGUARD_PROJECT_MANIFEST),
            )
        )
    if proposed_missing_ids:
        blockers.append(
            ProjectAdoptionFinding(
                "blocked",
                "governance_regression",
                "Proposed managed block loses required governance rules.",
                "Repair the generator before any project adoption write.",
                str(root_path / "AGENTS.md"),
                {"missing_rule_ids": proposed_missing_ids},
            )
        )
    return _dedupe_findings(blockers)


def _load_suite_evidence(root_path: Path) -> _SuiteEvidence:
    """Load the canonical suite validator lazily to avoid import cycles."""

    try:
        from .skill_suite import validate_skill_suite
    except (ImportError, ModuleNotFoundError) as exc:
        return _SuiteEvidence(
            False,
            "blocked",
            findings=(
                {
                    "code": "suite_validator_unavailable",
                    "message": str(exc),
                    "member_id": "",
                    "file_path": "",
                },
            ),
        )
    try:
        report = validate_skill_suite(root_path)
    except Exception as exc:  # validator failures must remain visible, not crash writes
        return _SuiteEvidence(
            False,
            "blocked",
            findings=(
                {
                    "code": "suite_validation_error",
                    "message": f"{type(exc).__name__}: {exc}",
                    "member_id": "",
                    "file_path": "",
                },
            ),
        )
    findings: list[Mapping[str, Any]] = []
    for finding in getattr(report, "findings", ()):
        payload = finding.to_dict() if hasattr(finding, "to_dict") else dict(finding)
        findings.append(payload)
    return _SuiteEvidence(
        bool(getattr(report, "ok", False)),
        str(getattr(report, "status", "blocked")),
        str(getattr(report, "inventory_hash", "")),
        str(getattr(report, "semantic_hash", "")),
        tuple(findings),
    )


def _projected_current_adoption_findings(
    findings: list[ProjectAdoptionFinding],
) -> list[ProjectAdoptionFinding]:
    repairable = {
        "missing_agents_block",
        "missing_project_manifest",
        "repository_url_mismatch",
        "schema_version_mismatch",
        "project_flowguard_current_replacement_required",
        "rendered_version_missing",
        "rendered_version_mismatch",
        "rendered_schema_version_missing",
        "rendered_schema_version_mismatch",
        "missing_managed_rule",
        "managed_block_semantic_drift",
        "manifest_package_version_missing",
        "manifest_schema_version_missing",
    }
    projected: list[ProjectAdoptionFinding] = []
    for finding in findings:
        if finding.category in repairable:
            projected.append(_with_severity(finding, "warning"))
        elif finding.category == "suite_inventory_unresolved":
            projected.append(_with_severity(finding, "warning"))
        else:
            projected.append(finding)
    return projected


def _with_severity(finding: ProjectAdoptionFinding, severity: str) -> ProjectAdoptionFinding:
    return ProjectAdoptionFinding(
        severity,
        finding.category,
        finding.message,
        finding.recommendation,
        finding.file_path,
        finding.metadata,
    )


def _dedupe_findings(findings: list[ProjectAdoptionFinding]) -> list[ProjectAdoptionFinding]:
    result: list[ProjectAdoptionFinding] = []
    seen: set[tuple[str, str, str]] = set()
    for finding in findings:
        key = (finding.severity, finding.category, finding.message)
        if key not in seen:
            seen.add(key)
            result.append(finding)
    return result


def _semantic_rule_changes(before: str, after: str) -> dict[str, Any]:
    before_ids = set(managed_rule_ids_in_block(before))
    after_ids = set(managed_rule_ids_in_block(after))
    return {
        "added_rule_ids": sorted(after_ids - before_ids),
        "removed_rule_ids": sorted(before_ids - after_ids),
        "missing_before": [item for item in FLOWGUARD_REQUIRED_RULE_IDS if item not in before_ids],
        "missing_after": [item for item in FLOWGUARD_REQUIRED_RULE_IDS if item not in after_ids],
        "content_changed": normalize_managed_agents_block(before) != normalize_managed_agents_block(after),
        "before_semantic_hash": managed_block_semantic_hash(before),
        "after_semantic_hash": managed_block_semantic_hash(after),
    }


def _rendered_versions(managed_block: str) -> tuple[str, str]:
    package_match = _RENDERED_PACKAGE_RE.search(managed_block)
    schema_match = _RENDERED_SCHEMA_RE.search(managed_block)
    return (
        package_match.group(1).strip() if package_match else "",
        schema_match.group(1).strip() if schema_match else "",
    )


def _adoption_state(
    *,
    package_version: str,
    manifest_package: str,
    manifest_schema: str,
    rendered_package: str,
    rendered_schema: str,
    semantic_hash: str,
    inventory_hash: str,
) -> dict[str, str]:
    return {
        "installed_package_version": package_version,
        "installed_schema_version": SCHEMA_VERSION,
        "manifest_package_version": manifest_package,
        "manifest_schema_version": manifest_schema,
        "rendered_package_version": rendered_package,
        "rendered_schema_version": rendered_schema,
        "managed_block_semantic_hash": semantic_hash,
        "inventory_hash": inventory_hash,
    }


def _minimum_revalidation() -> tuple[str, ...]:
    return (
        "python -m flowguard project-audit --root . --json",
        "Rerun affected FlowGuard model checks and focused tests before broad confidence.",
    )


def _proposed_files(
    *,
    root_path: Path,
    agents_changed: bool,
    manifest_changed: bool,
    include_logs: bool,
) -> tuple[str, ...]:
    paths: list[str] = []
    if agents_changed:
        paths.append(str(root_path / "AGENTS.md"))
    if manifest_changed:
        paths.append(str(root_path / FLOWGUARD_PROJECT_MANIFEST))
    if include_logs:
        paths.extend(
            (
                str(root_path / FLOWGUARD_PROJECT_LOG),
                str(root_path / FLOWGUARD_PROJECT_MARKDOWN_LOG),
            )
        )
    return tuple(dict.fromkeys(paths))


def _read_manifest(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    if not text:
        return {}
    try:
        payload = tomllib.loads(text)
        flowguard_section = payload.get("flowguard", {})
        return dict(flowguard_section) if isinstance(flowguard_section, dict) else {}
    except (tomllib.TOMLDecodeError, TypeError):
        return {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def compare_versions(left: str, right: str) -> int | None:
    """Compare simple release versions. Return -1, 0, 1, or None."""

    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    if left_parts is None or right_parts is None:
        return None
    length = max(len(left_parts), len(right_parts))
    padded_left = left_parts + (0,) * (length - len(left_parts))
    padded_right = right_parts + (0,) * (length - len(right_parts))
    if padded_left < padded_right:
        return -1
    if padded_left > padded_right:
        return 1
    return 0


def _version_parts(value: str) -> tuple[int, ...] | None:
    cleaned = str(value or "").strip().lstrip("vV")
    if not cleaned:
        return None
    pieces = re.split(r"[.\-+]", cleaned)
    numbers: list[int] = []
    for piece in pieces:
        if piece == "":
            continue
        if not piece.isdigit():
            return None
        numbers.append(int(piece))
    return tuple(numbers) if numbers else None


__all__ = [
    "FLOWGUARD_AGENTS_BEGIN",
    "FLOWGUARD_AGENTS_END",
    "FLOWGUARD_MANAGED_RULES",
    "FLOWGUARD_PROJECT_LOG",
    "FLOWGUARD_PROJECT_MANIFEST",
    "FLOWGUARD_PROJECT_MARKDOWN_LOG",
    "FLOWGUARD_REPOSITORY_URL",
    "FLOWGUARD_REQUIRED_RULE_IDS",
    "PROJECT_ADOPTION_ACTION_ADOPT",
    "PROJECT_ADOPTION_ACTION_AUDIT",
    "PROJECT_ADOPTION_CLAIM_BOUNDARY",
    "PROJECT_ADOPTION_STATUS_BLOCKED",
    "PROJECT_ADOPTION_STATUS_PASS",
    "PROJECT_ADOPTION_STATUS_PASS_WITH_GAPS",
    "ManagedAdoptionRule",
    "ProjectAdoptionFinding",
    "ProjectAdoptionReport",
    "adopt_project",
    "audit_project_adoption",
    "build_flowguard_agents_block",
    "compare_versions",
    "current_project_manifest_text",
    "extract_managed_agents_block",
    "installed_flowguard_package_version",
    "managed_block_semantic_hash",
    "managed_rule_ids_in_block",
    "normalize_managed_agents_block",
    "update_agents_text",
]
