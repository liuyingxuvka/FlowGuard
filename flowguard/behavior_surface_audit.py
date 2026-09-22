"""Fail-closed audit of the declarable public behavior surface.

The public API registry and command parser are useful *declaration signals*,
but they are not a semantic behavior denominator.  This module records those
signals and the missing native owners without manufacturing behavior rows from
names, tests, or model artifacts.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


PUBLIC_BEHAVIOR_SURFACE_GAP_SCHEMA = "flowguard.public_behavior_surface_gap.v1"
PUBLIC_BEHAVIOR_CLAIM_BOUNDARY = (
    "Complete declarable FlowGuard public behavior surface; every row must be "
    "independently authored with source, intent, success, error, recovery, "
    "owner, and disposition."
)
PUBLIC_BEHAVIOR_SURFACE_CLASSES = (
    "python_public_import",
    "cli_command",
    "template",
    "file_format_or_config",
    "ui_action",
    "installation_upgrade",
    "provider_platform",
    "fault_recovery",
    "release_identity",
)

# This is deliberately a different vocabulary from the historical
# ``BehaviorInventoryItem`` dispositions.  The historical inventory answers
# "what external behavior did the discovery owner find?".  This reverse
# audit answers "what did the implementation owner do with every observed
# source surface?".  Keeping the two vocabularies separate prevents a model
# or BCL row from silently becoming an implementation observation.
IMPLEMENTATION_SURFACE_AUDIT_SCHEMA = "flowguard.implementation_surface_audit.v1"
# Terminal output is intentionally a bounded projection.  The full discovery
# and audit JSON files remain the sole machine authorities; this schema is only
# a read-only display/transport projection and must never be used as audit
# input.
IMPLEMENTATION_SURFACE_AUDIT_COMPACT_SCHEMA = (
    "flowguard.implementation_surface_audit_compact.v1"
)
IMPLEMENTATION_SURFACE_CURRENTNESS_PROFILES = ("light", "full")
IMPLEMENTATION_SURFACE_MAP_SCHEMA = "flowguard.implementation_surface_map.v1"
# A source tree larger than the per-observation row bound is represented as a
# set of independently fingerprinted shards.  The merged observation keeps the
# same implementation-surface schema, while these two schemas make the
# partition and merge contract explicit to callers and receipt consumers.
IMPLEMENTATION_SURFACE_SHARD_SCHEMA = "flowguard.implementation_surface_shard.v1"
IMPLEMENTATION_SURFACE_SHARD_PLAN_SCHEMA = "flowguard.implementation_surface_shard_plan.v1"
# A candidate report is a deliberately weaker, source-only handoff than the
# reverse semantic map.  It is useful for review ordering, but it must never
# be consumed as an intent/model/owner/test/receipt binding.
IMPLEMENTATION_SURFACE_CANDIDATE_REPORT_SCHEMA = (
    "flowguard.implementation_surface_candidate_report.v1"
)
# A reverse map for a modeled target is not current merely because its source
# discovery fingerprint is current.  It must also join the exact observed
# model head, accepted revision, and the owner evidence that was current when
# the map was authored.  The owner-evidence list is the union of the
# delta-local accepted-revision references and the independent persistent
# reverse-surface owner authority.  The latter is required for routes that are
# unchanged by the latest model revision; it is not a compatibility reader or
# a second model authority.
IMPLEMENTATION_SURFACE_CURRENT_AUTHORITY_JOIN_SCHEMA = (
    "flowguard.implementation_surface_current_authority_join.v1"
)
# A source fingerprint and a model-head fingerprint do not prove that a
# reverse row points at a *current intent*.  The current behavior ledger is
# the native owner of that intent/obligation vocabulary.  Keep its projection
# as a separate exact join so a reverse map cannot invent an obligation id or
# silently bind an old intent catalogue.
IMPLEMENTATION_SURFACE_CURRENT_BEHAVIOR_LEDGER_JOIN_SCHEMA = (
    "flowguard.implementation_surface_current_behavior_ledger_join.v1"
)
IMPLEMENTATION_SURFACE_DISPOSITION_GOVERNED = "governed"
IMPLEMENTATION_SURFACE_DISPOSITION_INTERNAL_PROVEN = "internal_proven"
IMPLEMENTATION_SURFACE_DISPOSITION_RETIRED_PROVEN = "retired_proven"
IMPLEMENTATION_SURFACE_DISPOSITION_NOT_APPLICABLE_PROVEN = "not_applicable_proven"
IMPLEMENTATION_SURFACE_DISPOSITION_BLOCKED_GAP = "blocked_gap"
IMPLEMENTATION_SURFACE_DISPOSITIONS = (
    IMPLEMENTATION_SURFACE_DISPOSITION_GOVERNED,
    IMPLEMENTATION_SURFACE_DISPOSITION_INTERNAL_PROVEN,
    IMPLEMENTATION_SURFACE_DISPOSITION_RETIRED_PROVEN,
    IMPLEMENTATION_SURFACE_DISPOSITION_NOT_APPLICABLE_PROVEN,
    IMPLEMENTATION_SURFACE_DISPOSITION_BLOCKED_GAP,
)

# ``surface_kind`` remains the fine-grained source observation vocabulary used
# by the existing shard protocol.  ``surface_class`` is the stable semantic
# denominator used by the reverse map: it prevents a new parser detail (for
# example ``cli_entrypoint`` versus ``cli_command``) from silently creating a
# new coverage class.  The classes are intentionally finite and match the
# audit boundary requested by the independent implementation owner.
IMPLEMENTATION_SURFACE_CLASSES = (
    "code",
    "api",
    "cli",
    "ui_like",
    "config",
    "effect",
    "fault",
    "recovery",
    "install",
)

IMPLEMENTATION_SURFACE_KINDS = (
    "module",
    "function",
    "class",
    "export",
    "api",
    "cli_command",
    "cli_entrypoint",
    "template",
    "config",
    "effect",
    "error",
    "recovery",
    "placeholder",
    "ui_like_action",
    "dynamic",
    "plugin",
    "unreachable_or_unbound",
    "install",
)
# Component-level authoring compression is intentionally narrower than the
# component review report.  Dynamic/plugin, placeholder, and
# unreachable/unbound observations stay individually visible so their current
# owner and disposition cannot be hidden by a broad component row.  They may
# still be governed together by the same current obligation when the author
# explicitly proves that closure.
IMPLEMENTATION_SURFACE_COMPONENT_GROUP_MEMBER_KINDS = (
    "module",
    "function",
    "class",
)

IMPLEMENTATION_SURFACE_CANDIDATE_CLASSES = (
    "public_api",
    "public_cli",
    "ui_like",
    "template",
    "configuration",
    "installation",
    "effect",
    "fault",
    "recovery",
    "dynamic_boundary",
    "plugin_boundary",
    "placeholder",
    "unbound_or_unreachable",
    "implementation_code",
    "unclassified",
)

_SURFACE_EXCLUDED_PARTS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".flowguard",
        ".pytest_cache",
        ".skillguard",
        ".agents",
        ".codex",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "venv",
        ".venv",
        "work",
        "worktrees",
        "site-packages",
        "tmp",
        "openspec",
        "tests",
    }
)
_SURFACE_CONFIG_NAMES = frozenset(
    {
        "pyproject.toml",
        "setup.cfg",
        "tox.ini",
        "pytest.ini",
        "mypy.ini",
        ".env.example",
    }
)
_SURFACE_CONFIG_SUFFIXES = frozenset({".toml", ".ini", ".cfg", ".yaml", ".yml"})
_EFFECT_CALL_NAMES = frozenset(
    {
        "write_text",
        "write_bytes",
        "unlink",
        "remove",
        "rmdir",
        "mkdir",
        "rename",
        "replace",
        "copy",
        "copy2",
        "move",
        "rmtree",
        "run",
        "run_sync",
        "popen",
        "system",
        "chmod",
        "touch",
    }
)
_RECOVERY_CALL_RE = re.compile(
    r"(?:retry|resume|rollback|recover|cleanup|restore|repair|reconnect|close|fallback)",
    re.IGNORECASE,
)
_UI_CALL_RE = re.compile(
    r"(?:button|click|on_click|onclick|menu|control|submit|navigate|select|action|launch)",
    re.IGNORECASE,
)
_DYNAMIC_CALL_RE = re.compile(
    r"(?:import_module|__import__|importlib|module_from_spec|exec|eval|globals|locals|"
    r"getattr|setattr|__getattr__|__getattribute__|resolve_symbol|"
    r"load_module|load_object)",
    re.IGNORECASE,
)
_PLUGIN_CALL_RE = re.compile(
    r"(?:plugin|entry_points?|load_entry_point|register_plugin|discover_plugins?|"
    r"hookimpl|pluggy)",
    re.IGNORECASE,
)
_INSTALL_CALL_RE = re.compile(
    r"(?:^|[._-])(?:uninstall|install|upgrade|bootstrap|setup|sync_install|"
    r"install_skill|ensure_installed)(?:$|[._-])",
    re.IGNORECASE,
)
_PLACEHOLDER_RE = re.compile(
    r"\b(?:TODO|FIXME|XXX|HACK|placeholder|not[ -]?implemented)\b|NotImplementedError",
    re.IGNORECASE,
)

# Deterministic safety bounds for source discovery.  Exceeding a bound emits
# a blocker and never degrades to a partial green inventory.
_SURFACE_MAX_FILES = 512
_SURFACE_MAX_SOURCE_BYTES = 64 * 1024 * 1024
_SURFACE_MAX_ROWS = 5_000
_CURRENT_IDENTITY_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CURRENT_CALL_CONTRACT_ID_RE = re.compile(r"^contract:[a-z0-9_]+:[0-9a-f]{64}$")
_CURRENT_EXTERNAL_CONTRACT_BOUNDARY_KINDS = frozenset(
    {
        "dynamic_expression",
        "dynamic_receiver",
        "dynamic_callback",
        "external_unbound_call",
    }
)
_CURRENT_EXTERNAL_CONTRACT_TARGET_KIND = "external_contract"
_CURRENT_EXTERNAL_CONTRACT_TARGET_STATUS = "current_resolved"
_CURRENT_EXTERNAL_CONTRACT_TARGET_PROOF = "external_contract_registry"

# The reverse map has one current wire vocabulary.  Older drafts used
# singular receipt/test fields and plural owner aliases; accepting those
# fields as fallbacks lets a stale or ambiguous map look complete.  Keep the
# names visible as explicit blockers instead of silently interpreting them.
_IMPLEMENTATION_SURFACE_LEGACY_FIELDS = frozenset(
    {
        "receipt_ref",
        "receipts",
        "tests",
        "owners",
        "owner_ids",
        "primary_owner_ids",
        "primary_owners",
        "model_owner_ids",
        "primary_model_owner_ids",
        "retirement_reason",
        "internal_reason",
    }
)


class PublicBehaviorSurfaceAuditError(ValueError):
    """Raised when an audit input cannot be represented safely."""


def _fingerprint_payload(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _source_identity_content_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    """Project source identity to content identity used by discovery fingerprints.

    Size/mtime are observation hints only.  They deliberately do not alter the
    content identity or become a second authority.
    """

    return {
        "source_path": str(value.get("source_path", "")).replace("\\", "/"),
        "source_fingerprint": str(value.get("source_fingerprint", "")),
    }


def _current_authority_join_payload(
    state: Any,
    *,
    root: Path,
) -> dict[str, Any]:
    """Project the native current authority into a reverse-map join.

    The reverse audit may consume this projection, but it never chooses the
    model, rewrites a receipt, or promotes a candidate.  The source of truth
    remains ``load_current_model_authority_state``.  Owner evidence is copied
    only as identity tuples so a surface map cannot silently bind to a stale
    model revision or an unrelated owner receipt.
    """

    head = getattr(state, "head", None)
    snapshot = getattr(state, "snapshot", None)
    revision = getattr(state, "accepted_revision", None)
    if head is None or snapshot is None or revision is None:
        raise PublicBehaviorSurfaceAuditError(
            "current authority must expose head, observed snapshot, and accepted revision"
        )

    model_owner_ids: list[str] = []
    for item in getattr(snapshot, "model_instances", ()):
        logical_model_id = str(getattr(item, "logical_model_id", "")).strip()
        if not logical_model_id:
            raise PublicBehaviorSurfaceAuditError(
                "current observed snapshot contains a model instance without logical_model_id"
            )
        model_owner_ids.append(logical_model_id)
    if len(model_owner_ids) != len(set(model_owner_ids)):
        raise PublicBehaviorSurfaceAuditError(
            "current observed snapshot contains duplicate logical model owners"
        )

    owner_receipt_identities: list[dict[str, str]] = []
    for raw in getattr(revision, "completed_evidence_refs", ()):
        value = raw.to_dict() if hasattr(raw, "to_dict") else raw
        if not isinstance(value, Mapping):
            raise PublicBehaviorSurfaceAuditError(
                "current accepted revision contains a malformed completed evidence reference"
            )
        row = {
            "owner_route": str(value.get("owner_route", "")).strip(),
            "receipt_id": str(value.get("receipt_id", "")).strip(),
            "receipt_fingerprint": str(value.get("receipt_fingerprint", "")).strip(),
            "subject_fingerprint": str(value.get("subject_fingerprint", "")).strip(),
            "candidate_snapshot_fingerprint": str(
                value.get("candidate_snapshot_fingerprint", "")
            ).strip(),
        }
        if not row["owner_route"] or not row["receipt_id"]:
            raise PublicBehaviorSurfaceAuditError(
                "current completed evidence reference lacks owner_route or receipt_id"
            )
        for field_name in (
            "receipt_fingerprint",
            "subject_fingerprint",
            "candidate_snapshot_fingerprint",
        ):
            if not _CURRENT_IDENTITY_FINGERPRINT_RE.fullmatch(row[field_name]):
                raise PublicBehaviorSurfaceAuditError(
                    f"current completed evidence reference has invalid {field_name}"
                )
        owner_receipt_identities.append(row)
    owner_receipt_identities.sort(
        key=lambda item: (
            item["owner_route"],
            item["receipt_id"],
            item["receipt_fingerprint"],
        )
    )
    if len(
        {
            (item["owner_route"], item["receipt_id"])
            for item in owner_receipt_identities
        }
    ) != len(owner_receipt_identities):
        raise PublicBehaviorSurfaceAuditError(
            "current accepted revision contains duplicate owner receipt ids for one owner"
        )

    body = {
        "schema_version": IMPLEMENTATION_SURFACE_CURRENT_AUTHORITY_JOIN_SCHEMA,
        "head_fingerprint": str(getattr(head, "fingerprint", "")).strip(),
        "snapshot_fingerprint": str(getattr(head, "snapshot_fingerprint", "")).strip(),
        "revision_set_fingerprint": str(
            getattr(head, "accepted_revision_set_fingerprint", "")
        ).strip(),
        "activation_receipt_fingerprint": str(
            getattr(head, "activation_receipt_fingerprint", "")
        ).strip(),
        "model_owner_ids": sorted(model_owner_ids),
        "owner_receipt_identities": owner_receipt_identities,
    }
    for field_name in (
        "head_fingerprint",
        "snapshot_fingerprint",
        "revision_set_fingerprint",
        "activation_receipt_fingerprint",
    ):
        if not _CURRENT_IDENTITY_FINGERPRINT_RE.fullmatch(body[field_name]):
            raise PublicBehaviorSurfaceAuditError(
                f"current authority has invalid {field_name}"
            )
    try:
        from .reverse_surface_owner_authority import (
            load_current_reverse_surface_owner_authority,
        )

        reverse_authority = load_current_reverse_surface_owner_authority(
            root,
            authority_identity={
                "head_fingerprint": body["head_fingerprint"],
                "snapshot_fingerprint": body["snapshot_fingerprint"],
                "revision_set_fingerprint": body["revision_set_fingerprint"],
                "activation_receipt_fingerprint": body[
                    "activation_receipt_fingerprint"
                ],
            },
        )
    except Exception as exc:
        raise PublicBehaviorSurfaceAuditError(
            "current persistent reverse-surface owner authority is not current: "
            f"{exc}"
        ) from exc
    # A persistent reverse map has one canonical current receipt per owner
    # route.  The accepted revision's native evidence is delta-local and is
    # authoritative for revision acceptance, but it is not the persistent
    # reverse-map denominator.  Replacing matching routes (rather than
    # appending a second identity) keeps the join exact and fail-closed.
    reverse_rows = list(reverse_authority["owner_receipt_identities"])
    reverse_routes = {str(row["owner_route"]).strip() for row in reverse_rows}
    body["owner_receipt_identities"] = [
        row
        for row in body["owner_receipt_identities"]
        if row["owner_route"] not in reverse_routes
    ] + reverse_rows
    body["owner_receipt_identities"].sort(
        key=lambda item: (
            item["owner_route"],
            item["receipt_id"],
            item["receipt_fingerprint"],
        )
    )
    return {
        **body,
        "join_fingerprint": _surface_hash(body),
    }


def _load_current_authority_join(root: Path) -> dict[str, Any] | None:
    """Load the native current authority only when the target declares one.

    A repository with no FlowGuard project manifest is allowed to use the
    small source-only fixtures in this module.  Once a target declares a
    FlowGuard project, inability to load its current authority is a visible
    blocker; there is deliberately no legacy or fallback loader here.
    """

    root = Path(root).resolve()
    manifest_path = root / ".flowguard" / "project.toml"
    if not manifest_path.is_file():
        return None
    try:
        from .model_authority_store import load_current_model_authority_state

        state = load_current_model_authority_state(root)
        return _current_authority_join_payload(state, root=root)
    except Exception as exc:  # current authority errors are audit findings
        return {
            "schema_version": IMPLEMENTATION_SURFACE_CURRENT_AUTHORITY_JOIN_SCHEMA,
            "status": "blocked",
            "load_error": str(exc),
        }


def _ledger_model_owner_id(value: Any) -> str:
    """Normalize a ledger owner path to the logical current model id.

    The behavior ledger stores the owner as a repository-relative model path,
    while the native observed model snapshot stores ``logical_model_id``.
    This projection is deliberately structural; it never matches by fuzzy
    name or source-path similarity.
    """

    text = str(value or "").strip().replace("\\", "/")
    if not text:
        return ""
    parts = PurePosixPath(text).parts
    try:
        owner_index = parts.index("owners")
    except ValueError:
        return text
    if owner_index + 1 >= len(parts):
        return text
    return str(parts[owner_index + 1]).strip()


def _load_current_behavior_ledger_join(root: Path) -> dict[str, Any] | None:
    """Load the one current behavior-ledger identity for a modeled target.

    The reverse audit uses this projection only for identity and vocabulary
    joins.  It does not turn ledger declarations into implementation rows.
    A declared FlowGuard target with a missing or malformed current ledger is
    blocked; there is no historical reader or alternate ledger path.
    """

    root = Path(root).resolve()
    if not (root / ".flowguard" / "project.toml").is_file():
        return None
    # A narrow source-only/model-identity fixture may declare only the
    # ``project.toml`` loader seam and no behavior authority at all.  Preserve
    # that explicit boundary as not-applicable.  Once the target declares the
    # canonical behavior inventory directory, a missing ledger is a hard
    # currentness failure below; it is never replaced by a historical file.
    behavior_inventory_dir = root / ".flowguard" / "behavior" / "inventory"
    if not behavior_inventory_dir.exists():
        return None
    ledger_path = root / ".flowguard" / "behavior" / "inventory" / "ledger.json"
    try:
        if not ledger_path.is_file():
            raise PublicBehaviorSurfaceAuditError(
                "current behavior ledger is missing at "
                ".flowguard/behavior/inventory/ledger.json"
            )
        value = json.loads(ledger_path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise PublicBehaviorSurfaceAuditError(
                "current behavior ledger must be a JSON object"
            )
        ledger_id = str(value.get("ledger_id", "")).strip()
        current_revision = str(value.get("current_revision", "")).strip()
        if not ledger_id or not current_revision:
            raise PublicBehaviorSurfaceAuditError(
                "current behavior ledger needs ledger_id and current_revision"
            )
        commitments = value.get("commitments")
        if not isinstance(commitments, list) or not commitments:
            raise PublicBehaviorSurfaceAuditError(
                "current behavior ledger needs a non-empty commitments array"
            )
        commitment_bindings: list[dict[str, Any]] = []
        commitment_ids: list[str] = []
        intent_ids: list[str] = []
        model_obligation_ids: list[str] = []
        seen_commitments: set[str] = set()
        seen_intents: set[str] = set()
        seen_obligations: set[str] = set()
        for index, raw in enumerate(commitments):
            if not isinstance(raw, Mapping):
                raise PublicBehaviorSurfaceAuditError(
                    f"current behavior ledger commitment {index} is not an object"
                )
            commitment_id = str(raw.get("commitment_id", "")).strip()
            intent_id = str(raw.get("business_intent_id", "")).strip()
            owner_model_id = _ledger_model_owner_id(
                raw.get("primary_owner_model_id")
            )
            if not commitment_id or not intent_id or not owner_model_id:
                raise PublicBehaviorSurfaceAuditError(
                    f"current behavior ledger commitment {index} lacks canonical identity"
                )
            if commitment_id in seen_commitments:
                raise PublicBehaviorSurfaceAuditError(
                    f"current behavior ledger has duplicate commitment_id {commitment_id!r}"
                )
            if intent_id in seen_intents:
                raise PublicBehaviorSurfaceAuditError(
                    f"current behavior ledger has duplicate business_intent_id {intent_id!r}"
                )
            evidence = raw.get("evidence")
            if not isinstance(evidence, Mapping):
                raise PublicBehaviorSurfaceAuditError(
                    f"current behavior ledger commitment {commitment_id!r} lacks evidence"
                )
            if evidence.get("current") is not True or evidence.get(
                "evidence_state"
            ) != "current_pass":
                raise PublicBehaviorSurfaceAuditError(
                    f"current behavior ledger commitment {commitment_id!r} does not have current_pass evidence"
                )
            obligation_values = evidence.get("model_obligation_ids")
            if not isinstance(obligation_values, (list, tuple)) or not obligation_values:
                raise PublicBehaviorSurfaceAuditError(
                    f"current behavior ledger commitment {commitment_id!r} lacks model_obligation_ids"
                )
            obligations: list[str] = []
            for obligation in obligation_values:
                obligation_id = str(obligation).strip()
                if not obligation_id:
                    raise PublicBehaviorSurfaceAuditError(
                        f"current behavior ledger commitment {commitment_id!r} has an empty model obligation id"
                    )
                if obligation_id in seen_obligations:
                    raise PublicBehaviorSurfaceAuditError(
                        f"current behavior ledger has duplicate model obligation id {obligation_id!r}"
                    )
                seen_obligations.add(obligation_id)
                obligations.append(obligation_id)
            seen_commitments.add(commitment_id)
            seen_intents.add(intent_id)
            commitment_ids.append(commitment_id)
            intent_ids.append(intent_id)
            model_obligation_ids.extend(obligations)
            commitment_bindings.append(
                {
                    "commitment_id": commitment_id,
                    "intent_id": intent_id,
                    "model_owner_id": owner_model_id,
                    "model_obligation_ids": sorted(obligations),
                }
            )
        body = {
            "schema_version": IMPLEMENTATION_SURFACE_CURRENT_BEHAVIOR_LEDGER_JOIN_SCHEMA,
            "ledger_path": ".flowguard/behavior/inventory/ledger.json",
            "ledger_id": ledger_id,
            "current_revision": current_revision,
            "ledger_fingerprint": _sha256_file(ledger_path),
            "commitment_ids": sorted(commitment_ids),
            "intent_ids": sorted(intent_ids),
            "model_obligation_ids": sorted(model_obligation_ids),
            "commitment_bindings": sorted(
                commitment_bindings,
                key=lambda row: str(row["commitment_id"]),
            ),
        }
        return {
            **body,
            "status": "current",
            "join_fingerprint": _surface_hash(body),
        }
    except (OSError, UnicodeError, json.JSONDecodeError, PublicBehaviorSurfaceAuditError) as exc:
        return {
            "schema_version": IMPLEMENTATION_SURFACE_CURRENT_BEHAVIOR_LEDGER_JOIN_SCHEMA,
            "status": "blocked",
            "load_error": str(exc),
        }


def _validate_current_behavior_ledger_join_projection(
    value: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Validate canonical shape and self-fingerprint of a ledger projection."""

    findings: list[dict[str, Any]] = []
    if value.get("schema_version") != IMPLEMENTATION_SURFACE_CURRENT_BEHAVIOR_LEDGER_JOIN_SCHEMA:
        findings.append(
            {
                "code": "implementation_surface_current_behavior_ledger_join_schema_invalid",
                "severity": "blocker",
                "message": "current behavior-ledger join schema is not current",
            }
        )
    for field in (
        "ledger_path",
        "ledger_id",
        "current_revision",
        "ledger_fingerprint",
        "commitment_ids",
        "intent_ids",
        "model_obligation_ids",
        "commitment_bindings",
        "join_fingerprint",
    ):
        if field not in value:
            findings.append(
                {
                    "code": "implementation_surface_current_behavior_ledger_field_missing",
                    "severity": "blocker",
                    "field": field,
                    "message": "current behavior-ledger join is missing a required identity field",
                }
            )
    for field in ("ledger_fingerprint", "join_fingerprint"):
        if field in value and not _CURRENT_IDENTITY_FINGERPRINT_RE.fullmatch(
            str(value.get(field, ""))
        ):
            findings.append(
                {
                    "code": "implementation_surface_current_behavior_ledger_fingerprint_invalid",
                    "severity": "blocker",
                    "field": field,
                    "message": "current behavior-ledger identity is not canonical sha256",
                }
            )
    try:
        body = {
            key: value[key]
            for key in (
                "schema_version",
                "ledger_path",
                "ledger_id",
                "current_revision",
                "ledger_fingerprint",
                "commitment_ids",
                "intent_ids",
                "model_obligation_ids",
                "commitment_bindings",
            )
        }
    except KeyError:
        return findings
    if value.get("join_fingerprint") != _surface_hash(body):
        findings.append(
            {
                "code": "implementation_surface_current_behavior_ledger_join_fingerprint_mismatch",
                "severity": "blocker",
                "message": "current behavior-ledger join fingerprint does not match its identity body",
            }
        )
    return findings


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _source_identity(root: Path, relative_path: str, role: str) -> dict[str, Any]:
    path = (root / relative_path).resolve()
    row: dict[str, Any] = {
        "source_path": relative_path.replace("\\", "/"),
        "role": role,
    }
    try:
        path.relative_to(root.resolve())
    except ValueError:
        row.update({"status": "blocked", "reason": "source escapes project root"})
        return row
    if not path.is_file():
        row.update({"status": "blocked", "reason": "declared source file is missing"})
        return row
    row.update({"status": "current_input", "source_fingerprint": _sha256_file(path)})
    return row


def _flatten_declared_names(value: Any) -> list[str]:
    """Flatten explicit registry values without treating them as behaviors."""

    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        names: list[str] = []
        for child in value.values():
            names.extend(_flatten_declared_names(child))
        return names
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        names = []
        for child in value:
            names.extend(_flatten_declared_names(child))
        return names
    return []


def _name_summary(names: Sequence[str]) -> dict[str, Any]:
    ordered = [str(name) for name in names]
    unique = sorted(set(ordered))
    return {
        "declared_count": len(ordered),
        "unique_count": len(unique),
        "sample_names": unique[:12],
    }


def _api_declaration_summary() -> dict[str, Any]:
    # Imported lazily so this audit is not another __init__ authority or a
    # second public API registry.  The values are reported as declarations
    # only; no value is converted into a BehaviorInventoryItem.
    import flowguard

    api_surface = getattr(flowguard, "API_SURFACE", None)
    if not isinstance(api_surface, Mapping):
        raise PublicBehaviorSurfaceAuditError("flowguard.API_SURFACE is not a mapping")
    groups: dict[str, Any] = {}
    all_names: list[str] = []
    for group_id in sorted(api_surface):
        names = _flatten_declared_names(api_surface[group_id])
        groups[str(group_id)] = _name_summary(names)
        all_names.extend(names)
    public_all = getattr(flowguard, "__all__", ())
    return {
        "registry": "flowguard.API_SURFACE",
        "groups": groups,
        "declared_name_count": len(all_names),
        "unique_name_count": len(set(all_names)),
        "public_all_name_count": len(tuple(public_all)),
        "public_all_sample_names": sorted(set(str(name) for name in public_all))[:12],
        "semantic_behavior_rows_generated": 0,
    }


def _literal_cli_declarations(path: Path) -> dict[str, Any]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        return {"status": "blocked", "reason": f"cannot parse CLI source: {exc}"}

    parser_names: list[str] = []
    parser_calls = 0
    template_names: list[str] = []
    template_calls = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Attribute) and function.attr == "add_parser":
            parser_calls += 1
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(
                node.args[0].value, str
            ):
                parser_names.append(node.args[0].value)
        if isinstance(function, ast.Name) and function.id == "FileTemplateCommand":
            template_calls += 1
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(
                node.args[0].value, str
            ):
                template_names.append(node.args[0].value)
    return {
        "status": "current_input",
        "literal_parser_declarations": _name_summary(parser_names),
        "all_parser_call_count": parser_calls,
        "dynamic_parser_call_count": parser_calls - len(parser_names),
        "literal_template_declarations": _name_summary(template_names),
        "all_template_command_call_count": template_calls,
        "semantic_behavior_rows_generated": 0,
    }


def _console_script_declarations(path: Path) -> dict[str, Any]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        scripts = data.get("project", {}).get("scripts", {})
        if not isinstance(scripts, Mapping):
            raise TypeError("[project.scripts] must be a table")
        names = sorted(str(name) for name in scripts)
        return {
            "status": "current_input",
            "scripts": names,
            "declared_count": len(names),
            "semantic_behavior_rows_generated": 0,
        }
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, TypeError, AttributeError) as exc:
        return {"status": "blocked", "reason": f"cannot read project scripts: {exc}"}


def _manifest_context(manifest_evidence: Mapping[str, Any]) -> dict[str, Any]:
    inventory = manifest_evidence.get("inventory")
    if not isinstance(inventory, Mapping):
        inventory = {}
    expected = inventory.get("expected_behavior_ids")
    items = inventory.get("items")
    expected_ids = [str(value) for value in expected] if isinstance(expected, list) else []
    materialized_ids = (
        [str(item.get("behavior_id")) for item in items if isinstance(item, Mapping)]
        if isinstance(items, list)
        else []
    )
    return {
        "status": str(manifest_evidence.get("status", "blocked")),
        "inventory_id": inventory.get("inventory_id"),
        "claim_boundary": manifest_evidence.get("claim_boundary")
        or inventory.get("claim_boundary"),
        "expected_behavior_ids": expected_ids,
        "materialized_behavior_ids": materialized_ids,
        "materialized_behavior_count": len(materialized_ids),
        "discovery_fingerprint": inventory.get("discovery_fingerprint"),
        "coverage_scope": dict(
            (inventory.get("metadata") or {}).get("coverage_scope") or {}
        ),
        "items": [item for item in items if isinstance(item, Mapping)]
        if isinstance(items, list)
        else [],
    }


def _finding(code: str, message: str, *, surface_class: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"code": code, "severity": "blocker", "message": message}
    if surface_class is not None:
        row["surface_class"] = surface_class
    return row


def build_public_behavior_surface_gap_report(
    *,
    root: Path,
    manifest_evidence: Mapping[str, Any],
    manifest_path: Path | None = None,
    authority_status: str = "not_provided",
    authority_reason: str = "Attach a current selected-model read result before a broad current claim.",
) -> dict[str, Any]:
    """Build a blocked report without expanding the independent denominator."""

    bounded_root = root.resolve()
    main_path = bounded_root / "flowguard" / "__main__.py"
    pyproject_path = bounded_root / "pyproject.toml"
    cli_declarations = _literal_cli_declarations(main_path)
    declarations = {
        "python_public_import": _api_declaration_summary(),
        "cli_command": cli_declarations,
        "template": cli_declarations.get(
            "literal_template_declarations",
            {"declared_count": 0, "unique_count": 0, "sample_names": []},
        ),
        "console_script": _console_script_declarations(pyproject_path),
    }
    source_identities = [
        _source_identity(
            bounded_root,
            "flowguard/__init__.py",
            "explicit Python API registry and __all__ declaration",
        ),
        _source_identity(
            bounded_root,
            "flowguard/__main__.py",
            "explicit CLI parser and template command declarations",
        ),
        _source_identity(
            bounded_root,
            "pyproject.toml",
            "explicit console-script declaration",
        ),
    ]
    manifest = _manifest_context(manifest_evidence)
    findings: list[dict[str, Any]] = []
    coverage_scope = manifest.get("coverage_scope") or {}
    complete_scope = coverage_scope.get("status") == "complete_current"
    materialized_rows = list(manifest.get("items") or []) if complete_scope else []
    declared_scope_classes = coverage_scope.get("surface_classes")
    if not isinstance(declared_scope_classes, list):
        declared_scope_classes = []
    covered_classes = {
        str((item.get("metadata") or {}).get("surface_class"))
        for item in materialized_rows
        if isinstance(item, Mapping)
        and str((item.get("metadata") or {}).get("surface_class") or "").strip()
    }
    unresolved_surface_classes = sorted(
        set(PUBLIC_BEHAVIOR_SURFACE_CLASSES) - covered_classes
    )
    declared_scope_set = {str(value) for value in declared_scope_classes}
    unresolved_surface_classes = sorted(
        set(unresolved_surface_classes)
        | (set(PUBLIC_BEHAVIOR_SURFACE_CLASSES) - declared_scope_set)
    )
    if manifest["status"] != "passed":
        findings.append(
            _finding(
                "behavior_discovery_manifest_invalid",
                "The scoped behavior manifest did not produce a terminal pass.",
            )
        )
    if not complete_scope:
        findings.append(
            _finding(
                "behavior_discovery_scope_not_complete",
                "The current manifest does not declare a complete current public behavior denominator.",
            )
        )
        findings.append(
            _finding(
                "behavior_discovery_public_declarations_not_semantic_rows",
                "API_SURFACE, __all__, parser names, and console-script names lack independently authored intent, success, error, recovery, owner, and disposition fields; no behavior rows were generated from them.",
                surface_class="python_public_import",
            )
        )
        if (
            declarations["cli_command"].get("literal_parser_declarations", {}).get("declared_count", 0)
            or declarations["console_script"].get("declared_count", 0)
        ):
            findings.append(
                _finding(
                    "behavior_discovery_cli_surface_not_manifested",
                    "Explicit CLI entrypoint/parser declarations are outside the current manifest and require a native semantic inventory owner.",
                    surface_class="cli_command",
                )
            )
    elif (
        not declared_scope_classes
        or len(declared_scope_classes) != len(declared_scope_set)
        or declared_scope_set != set(PUBLIC_BEHAVIOR_SURFACE_CLASSES)
    ):
        findings.append(
            _finding(
                "behavior_discovery_complete_scope_classes_missing",
                "A complete current manifest must explicitly enumerate each finite public surface class exactly once.",
            )
        )
    for surface_class in unresolved_surface_classes:
        findings.append(
            _finding(
                f"behavior_discovery_{surface_class}_not_manifested",
                "The complete current manifest has no independently authored semantic row for this public surface class.",
                surface_class=surface_class,
            )
        )
    if complete_scope:
        for item in materialized_rows:
            item_id = str(item.get("behavior_id") or "")
            if str(item.get("intent_disposition") or "") == "unresolved":
                findings.append(
                    _finding(
                        "behavior_discovery_intent_unresolved",
                        "A complete current public behavior manifest cannot contain an unresolved intent disposition.",
                        surface_class=str((item.get("metadata") or {}).get("surface_class") or ""),
                    )
                )
            if str(item.get("disposition") or "") == "blocked_gap":
                findings.append(
                    _finding(
                        "behavior_discovery_blocked_gap_present",
                        "A complete current public behavior manifest cannot contain a blocked gap.",
                        surface_class=str((item.get("metadata") or {}).get("surface_class") or ""),
                    )
                )
    if authority_status != "passed":
        findings.append(
            _finding(
                "behavior_discovery_current_authority_not_green",
                authority_reason,
            )
        )

    declaration_payload = {
        "source_identities": source_identities,
        "declarations": declarations,
    }
    next_actions: list[dict[str, Any]]
    if complete_scope:
        next_actions = [
            {
                "owner": "native-public-behavior-discovery-owner",
                "action": "Keep the current explicit manifest and its source identities frozen; any source or intent change requires a new current manifest revision and affected revalidation.",
            },
            {
                "owner": "current-model-authority-owner",
                "action": "Keep the current model-authority result bound to this report; a non-passed authority result blocks the broad public-surface claim without changing the authored denominator.",
            },
        ]
    else:
        next_actions = [
            {
                "owner": "native-public-behavior-discovery-owner",
                "action": "Freeze the complete declarable surface from explicit production declarations and manually author one row per external behavior.",
                "required_fields": [
                    "behavior_id",
                    "source_ref",
                    "source_fingerprint",
                    "public_surface",
                    "intent",
                    "success",
                    "errors",
                    "recovery",
                    "owner",
                    "disposition",
                ],
            },
            {
                "owner": "current-model-authority-owner",
                "action": "Repair and freeze one current model-authority head, then run one explicit selected-model read and bind its identity to the inventory review.",
            },
            {
                "owner": "behavior-commitment-ledger-owner",
                "action": "Keep require_complete_behavior_inventory=false until exact expected/materialized conservation passes for the full boundary and every blocked gap is resolved.",
            },
        ]
    base: dict[str, Any] = {
        "schema_version": PUBLIC_BEHAVIOR_SURFACE_GAP_SCHEMA,
        "status": "blocked",
        "claim_boundary": PUBLIC_BEHAVIOR_CLAIM_BOUNDARY,
        "manifest": {
            "path": _relative_path(bounded_root, manifest_path) if manifest_path else None,
            **manifest,
        },
        "authority": {
            "status": authority_status,
            "reason": authority_reason,
        },
        "declaration_summary": declaration_payload,
        "unresolved_surface_classes": unresolved_surface_classes,
        "materialized_behavior_rows": materialized_rows,
        "generated_behavior_ids": [],
        "denominator_expansion": "explicit_manifest" if complete_scope else "not_attempted",
        "complete_public_surface_claim_licensed": False,
        "findings": findings,
        "next_actions": next_actions,
    }
    base["public_surface_declaration_fingerprint"] = _fingerprint_payload(declaration_payload)
    base["status"] = "passed" if not findings else "blocked"
    base["complete_public_surface_claim_licensed"] = base["status"] == "passed"
    base["evidence_fingerprint"] = _fingerprint_payload(base)
    return base


def _surface_text(value: Any, *, context: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        qualifier = "a string" if allow_empty else "a non-empty string"
        raise PublicBehaviorSurfaceAuditError(f"{context} must be {qualifier}")
    return value


def _surface_strings(value: Any, *, context: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise PublicBehaviorSurfaceAuditError(f"{context} must be an array")
    result = tuple(_surface_text(item, context=f"{context}[]") for item in value)
    if len(result) != len(set(result)):
        raise PublicBehaviorSurfaceAuditError(f"{context} contains duplicate values")
    return result


def _surface_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _validate_current_authority_join_projection(
    value: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Validate the native current-authority projection before joining it.

    The loader normally constructs this projection from the native authority
    store.  Keep the audit boundary defensive anyway: a malformed or
    hand-authored projection must not become a current join merely because a
    reverse map copied the same malformed values.  In particular, owner
    receipt identity is keyed by ``(owner_route, receipt_id)``; changing only
    its fingerprint is not a second current receipt.
    """

    findings: list[dict[str, Any]] = []
    required_fields = (
        "schema_version",
        "head_fingerprint",
        "snapshot_fingerprint",
        "revision_set_fingerprint",
        "activation_receipt_fingerprint",
        "model_owner_ids",
        "owner_receipt_identities",
        "join_fingerprint",
    )
    missing = [field for field in required_fields if field not in value]
    if missing:
        for field in missing:
            findings.append(
                {
                    "code": "implementation_surface_current_authority_field_missing",
                    "severity": "blocker",
                    "field": field,
                    "message": "native current authority join is missing a required identity field",
                }
            )
        return findings

    if value.get("schema_version") != IMPLEMENTATION_SURFACE_CURRENT_AUTHORITY_JOIN_SCHEMA:
        findings.append(
            {
                "code": "implementation_surface_current_authority_join_schema_invalid",
                "severity": "blocker",
                "message": "native current authority join schema is not current",
            }
        )
    for field in (
        "head_fingerprint",
        "snapshot_fingerprint",
        "revision_set_fingerprint",
        "activation_receipt_fingerprint",
    ):
        if not isinstance(value.get(field), str) or not _CURRENT_IDENTITY_FINGERPRINT_RE.fullmatch(
            value.get(field, "")
        ):
            findings.append(
                {
                    "code": "implementation_surface_current_authority_identity_invalid",
                    "severity": "blocker",
                    "field": field,
                    "message": "native current authority identity is not canonical sha256",
                }
            )

    model_owner_ids = value.get("model_owner_ids")
    if not isinstance(model_owner_ids, list) or not model_owner_ids:
        findings.append(
            {
                "code": "implementation_surface_current_authority_model_owner_ids_invalid",
                "severity": "blocker",
                "message": "native current authority model_owner_ids must be a non-empty array",
            }
        )
    elif any(not isinstance(item, str) or not item.strip() for item in model_owner_ids):
        findings.append(
            {
                "code": "implementation_surface_current_authority_model_owner_ids_invalid",
                "severity": "blocker",
                "message": "native current authority model_owner_ids must contain non-empty strings",
            }
        )
    elif len(model_owner_ids) != len(set(model_owner_ids)):
        findings.append(
            {
                "code": "implementation_surface_current_authority_model_owner_duplicate",
                "severity": "blocker",
                "message": "native current authority contains duplicate model owners",
            }
        )

    owner_receipt_identities = value.get("owner_receipt_identities")
    identity_keys: set[tuple[str, str]] = set()
    if not isinstance(owner_receipt_identities, list):
        findings.append(
            {
                "code": "implementation_surface_current_authority_owner_receipts_invalid",
                "severity": "blocker",
                "message": "native current authority owner_receipt_identities must be an array",
            }
        )
        owner_receipt_identities = []
    for index, identity in enumerate(owner_receipt_identities):
        if not isinstance(identity, Mapping):
            findings.append(
                {
                    "code": "implementation_surface_current_authority_owner_receipt_invalid",
                    "severity": "blocker",
                    "row_index": index,
                    "message": "native current authority owner receipt identity must be an object",
                }
            )
            continue
        owner_route = identity.get("owner_route")
        receipt_id = identity.get("receipt_id")
        if not isinstance(owner_route, str) or not owner_route.strip() or not isinstance(
            receipt_id, str
        ) or not receipt_id.strip():
            findings.append(
                {
                    "code": "implementation_surface_current_authority_owner_receipt_invalid",
                    "severity": "blocker",
                    "row_index": index,
                    "message": "native current authority owner receipt needs owner_route and receipt_id",
                }
            )
            continue
        key = (owner_route, receipt_id)
        if key in identity_keys:
            findings.append(
                {
                    "code": "implementation_surface_current_authority_owner_receipt_duplicate",
                    "severity": "blocker",
                    "row_index": index,
                    "message": "native current authority contains duplicate owner receipt ids for one owner",
                }
            )
        identity_keys.add(key)
        for field in (
            "receipt_fingerprint",
            "subject_fingerprint",
            "candidate_snapshot_fingerprint",
        ):
            if not isinstance(identity.get(field), str) or not _CURRENT_IDENTITY_FINGERPRINT_RE.fullmatch(
                identity.get(field, "")
            ):
                findings.append(
                    {
                        "code": "implementation_surface_current_authority_owner_receipt_invalid",
                        "severity": "blocker",
                        "row_index": index,
                        "field": field,
                        "message": "native current authority owner receipt identity is not canonical",
                    }
                )

    body = {
        field: value.get(field)
        for field in required_fields
        if field != "join_fingerprint"
    }
    join_fingerprint = value.get("join_fingerprint")
    if not isinstance(join_fingerprint, str) or not _CURRENT_IDENTITY_FINGERPRINT_RE.fullmatch(
        join_fingerprint
    ):
        findings.append(
            {
                "code": "implementation_surface_current_authority_join_fingerprint_invalid",
                "severity": "blocker",
                "message": "native current authority join_fingerprint is not canonical sha256",
            }
        )
    elif join_fingerprint != _surface_hash(body):
        findings.append(
            {
                "code": "implementation_surface_current_authority_join_fingerprint_mismatch",
                "severity": "blocker",
                "message": "native current authority join_fingerprint does not match its identity body",
            }
        )
    return findings


def _surface_span(node: ast.AST, *, fallback_line: int = 1) -> dict[str, int]:
    line_start = int(getattr(node, "lineno", fallback_line) or fallback_line)
    line_end = int(getattr(node, "end_lineno", line_start) or line_start)
    col_start = int(getattr(node, "col_offset", 0) or 0)
    col_end = int(getattr(node, "end_col_offset", col_start) or col_start)
    return {
        "line_start": line_start,
        "line_end": max(line_start, line_end),
        "column_start": max(0, col_start),
        "column_end": max(0, col_end),
    }


def _surface_relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _surface_call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _surface_call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return "<dynamic>"


def _surface_module_name(relative_path: str) -> str:
    """Return the source-only dotted module name for one Python path."""

    path = PurePosixPath(str(relative_path).replace("\\", "/"))
    if path.suffix.casefold() != ".py":
        return ""
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _surface_import_bindings(relative_path: str, tree: ast.AST) -> dict[str, tuple[str, ...]]:
    """Collect deterministic import aliases without importing target code.

    The result is only a lexical hint for the source-only call graph.  It
    never turns an external import into a local surface: a target is usable
    only when the merged source inventory contains the exact imported symbol.
    """

    module_name = _surface_module_name(relative_path)
    module_parts = module_name.split(".") if module_name else []
    path = PurePosixPath(str(relative_path).replace("\\", "/"))
    package_parts = (
        module_parts
        if path.name == "__init__.py"
        else module_parts[:-1]
    )
    bindings: dict[str, list[str]] = {}

    def add_binding(bound_name: str, target: str) -> None:
        if not bound_name or not target:
            return
        values = bindings.setdefault(bound_name, [])
        if target not in values:
            values.append(target)

    class _ModuleImportVisitor(ast.NodeVisitor):
        # Imports nested in a function or class have a narrower lexical scope;
        # keeping them out of this file-wide map prevents a different function
        # from receiving a false imported binding.
        def visit_FunctionDef(self, current: ast.FunctionDef) -> None:
            return None

        def visit_AsyncFunctionDef(self, current: ast.AsyncFunctionDef) -> None:
            return None

        def visit_ClassDef(self, current: ast.ClassDef) -> None:
            return None

        def visit_Import(self, current: ast.Import) -> None:
            for alias in current.names:
                target = str(alias.name).strip()
                if not target:
                    continue
                if alias.asname:
                    add_binding(str(alias.asname).strip(), target)
                else:
                    # ``import package.module`` binds the root package name
                    # in Python, while the complete dotted path remains a
                    # valid lexical import prefix.  Keep both exact prefixes
                    # so ``package.module.member`` can be resolved without
                    # appending the module path twice.
                    root_name = target.split(".", 1)[0]
                    add_binding(root_name, root_name)
                    add_binding(target, target)

        def visit_ImportFrom(self, current: ast.ImportFrom) -> None:
            nonlocal package_parts
            node = current
            if node.level:
                base_parts = package_parts[: max(0, len(package_parts) - (node.level - 1))]
                imported_module = ".".join(
                    [*base_parts, *([node.module] if node.module else [])]
                )
            else:
                imported_module = str(node.module or "").strip()
            imported_module = imported_module.strip(".")
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound_name = str(alias.asname or alias.name).strip()
                if not bound_name:
                    continue
                target = ".".join(
                    item for item in (imported_module, str(alias.name).strip()) if item
                )
                add_binding(bound_name, target)

    visitor = _ModuleImportVisitor()
    visitor.visit(tree)
    return {name: tuple(targets) for name, targets in bindings.items()}


def _surface_import_target_matches(candidate_symbol: str, target: str) -> bool:
    """Match an imported target only when its source identity is exact."""

    candidate = str(candidate_symbol)
    normalized_target = str(target)
    if candidate == normalized_target:
        return True
    # A suffix match would let an unrelated module which happens to expose the
    # same dotted tail masquerade as the imported owner.
    return False


def _surface_literal_strings(node: ast.AST) -> tuple[str, ...]:
    """Read only literal names from declarations; never import the package."""

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return (node.value,)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values: list[str] = []
        for child in node.elts:
            values.extend(_surface_literal_strings(child))
        return tuple(values)
    if isinstance(node, ast.Dict):
        values: list[str] = []
        for child in node.values:
            if child is not None:
                values.extend(_surface_literal_strings(child))
        return tuple(values)
    return ()


def _surface_is_config_file(relative_path: str) -> bool:
    path = Path(relative_path)
    name = path.name.casefold()
    if name in {item.casefold() for item in _SURFACE_CONFIG_NAMES}:
        return True
    if path.suffix.casefold() not in _SURFACE_CONFIG_SUFFIXES:
        return False
    return any(token in name for token in ("config", "setting", "option", "tox", "pytest", "mypy"))


def _surface_python_files(root: Path) -> tuple[Path, ...]:
    result: list[Path] = []
    root_resolved = root.resolve()
    # A FlowGuard checkout contains authoring skills, KB material, build
    # workspaces, and other Python trees beside the product package.  The
    # target source boundary is intentionally limited to production roots;
    # otherwise a supposedly local audit can recurse into an unbounded tool
    # tree and never produce a receipt.
    allowed_roots: tuple[Path, ...]
    if (root_resolved / "flowguard").is_dir():
        allowed_roots = tuple(
            path
            for path in (
                root_resolved / "flowguard",
                root_resolved / "scripts",
                root_resolved / "examples",
            )
            if path.is_dir()
        )
        allowed_root_files = tuple(root_resolved.glob("*.py"))
    else:
        allowed_roots = (root_resolved,)
        allowed_root_files = ()

    def visit(base: Path) -> None:
        for current, directories, files in os.walk(base):
            current_path = Path(current)
            directories[:] = sorted(
                directory
                for directory in directories
                if directory not in _SURFACE_EXCLUDED_PARTS
            )
            for name in sorted(files):
                if not name.endswith(".py"):
                    continue
                path = current_path / name
                try:
                    relative = path.resolve().relative_to(root_resolved)
                except ValueError:
                    continue
                if any(part in _SURFACE_EXCLUDED_PARTS for part in relative.parts):
                    continue
                result.append(path)

    for base in allowed_roots:
        visit(base)
    for path in allowed_root_files:
        if path.is_file() and path not in result:
            result.append(path)
    return tuple(sorted(result, key=lambda item: item.as_posix()))


def _surface_config_files(root: Path) -> tuple[Path, ...]:
    result: list[Path] = []
    root_resolved = root.resolve()
    allowed_roots = (
        (root_resolved / "flowguard", root_resolved / "scripts", root_resolved / "examples")
        if (root_resolved / "flowguard").is_dir()
        else (root_resolved,)
    )
    candidates = [root_resolved / name for name in _SURFACE_CONFIG_NAMES]
    for base in allowed_roots:
        if not base.is_dir():
            continue
        for current, directories, files in os.walk(base):
            directories[:] = sorted(
                directory
                for directory in directories
                if directory not in _SURFACE_EXCLUDED_PARTS
            )
            for name in sorted(files):
                path = Path(current) / name
                try:
                    relative = path.resolve().relative_to(root_resolved).as_posix()
                except ValueError:
                    continue
                if _surface_is_config_file(relative):
                    result.append(path)
    for path in candidates:
        if path.is_file() and path not in result:
            result.append(path)
    return tuple(sorted(result, key=lambda item: item.as_posix()))


def _surface_candidate_files(root: Path) -> tuple[Path, ...]:
    """Return the complete bounded source boundary in deterministic order.

    Python and configuration discovery intentionally remain separate because
    they use different parsers.  A shard, however, owns a source path exactly
    once, so this helper deduplicates the two views before partitioning.
    """

    paths = {
        path.resolve()
        for path in (*_surface_python_files(root), *_surface_config_files(root))
        if path.is_file()
    }
    return tuple(sorted(paths, key=lambda item: _surface_relative(root, item)))


def _resolve_surface_source_selection(
    root: Path,
    source_paths: Sequence[str | Path] | None,
    *,
    candidate_paths: Sequence[Path] | None = None,
) -> tuple[tuple[Path, ...], list[dict[str, Any]]]:
    """Resolve an optional explicit shard boundary without silent expansion."""

    candidates = tuple(candidate_paths) if candidate_paths is not None else _surface_candidate_files(root)
    by_relative = {
        _surface_relative(root, path): path
        for path in candidates
    }
    if source_paths is None:
        return candidates, []

    findings: list[dict[str, Any]] = []
    selected: list[Path] = []
    seen: set[str] = set()
    for raw_path in source_paths:
        raw_text = str(raw_path)
        candidate = Path(raw_text)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (root / candidate).resolve()
        relative = _surface_relative(root, resolved)
        if relative in seen:
            findings.append(
                {
                    "code": "surface_shard_duplicate_source_path",
                    "severity": "blocker",
                    "source_path": relative,
                    "message": "a shard source path was supplied more than once",
                }
            )
            continue
        seen.add(relative)
        if relative not in by_relative or by_relative[relative] != resolved:
            findings.append(
                {
                    "code": "surface_shard_source_path_not_in_boundary",
                    "severity": "blocker",
                    "source_path": relative,
                    "message": "explicit shard source path is not part of the current production boundary",
                }
            )
            continue
        selected.append(resolved)
    return tuple(sorted(selected, key=lambda item: _surface_relative(root, item))), findings


def _surface_relative_paths(root: Path, paths: Sequence[Path]) -> list[str]:
    return sorted({_surface_relative(root, path) for path in paths})


def _surface_anchor(relative_path: str, kind: str, symbol: str, span: Mapping[str, int]) -> str:
    return "|".join(
        (
            relative_path,
            kind,
            symbol,
            str(span.get("line_start", 0)),
            str(span.get("column_start", 0)),
            str(span.get("line_end", 0)),
            str(span.get("column_end", 0)),
        )
    )


def _surface_id(relative_path: str, kind: str, symbol: str, span: Mapping[str, int]) -> str:
    # The semantic anchor intentionally excludes line numbers.  A comment or
    # import inserted above a function must not create a new logical surface;
    # the separately recorded source_span and source_fingerprint will make the
    # changed observation stale.  Repeated call sites use the deterministic
    # collision suffix in _surface_emit.
    anchor = "|".join((relative_path, kind, symbol))
    digest = hashlib.sha256(anchor.encode("utf-8")).hexdigest()
    return f"surface:{kind}:{digest[:32]}"


def _surface_source_ref(relative_path: str, symbol: str, span: Mapping[str, int]) -> str:
    return (
        f"{relative_path}#{symbol}"
        f"@L{span['line_start']}:C{span['column_start']}-"
        f"L{span['line_end']}:C{span['column_end']}"
    )


def _surface_class_for_kind(kind: str) -> str:
    """Collapse fine-grained observations into the fixed audit denominator."""

    normalized = str(kind).strip()
    if normalized in {"module", "function", "class", "template", "placeholder", "dynamic", "plugin", "unreachable_or_unbound"}:
        return "code"
    if normalized in {"export", "api"}:
        return "api"
    if normalized in {"cli_command", "cli_entrypoint"}:
        return "cli"
    if normalized == "ui_like_action":
        return "ui_like"
    if normalized == "config":
        return "config"
    if normalized == "effect":
        return "effect"
    if normalized in {"error", "fault"}:
        return "fault"
    if normalized == "recovery":
        return "recovery"
    if normalized == "install":
        return "install"
    # Keep an unexpected source observation visible to the mapping validator;
    # it must not silently become a code row in a future parser extension.
    return ""


def _surface_review_group(relative_path: str, kind: str, symbol: str) -> tuple[str, str]:
    """Return the review unit for one source observation.

    The reverse denominator is intentionally not a source-line checklist.
    Externally observable actions/contracts are reviewed as individual
    surfaces.  Private implementation observations share a deterministic
    component group so one internal proof can cover the component after its
    public boundaries have been closed.  This is a grouping hint only; it
    never discharges an unmapped observation or licenses a broad claim.
    """

    surface_class = _surface_class_for_kind(kind)
    external_classes = {"api", "cli", "ui_like", "config", "effect", "fault", "recovery", "install"}
    # A registered template is an externally reachable artifact even though
    # its normalized class is ``code`` for the finite denominator.  Keep it
    # individually reviewable; otherwise a component grouping could hide a
    # missing template command behind an internal module proof.  Dynamic,
    # plugin, placeholder, and unbound observations are also individual
    # boundaries.  They have a typed disposition rule in the semantic audit
    # (currently ``not_applicable_proven`` or ``blocked_gap``), so grouping
    # them with ordinary functions would force the whole file into the same
    # disposition and either hide real implementation behavior or make a
    # valid dynamic proof impossible.  Splitting these observations is a
    # current review-boundary repair, not a fallback or a semantic guess.
    if surface_class in external_classes or kind in {
        "template",
        "dynamic",
        "plugin",
        "placeholder",
        "unreachable_or_unbound",
    }:
        group_key = f"surface|{relative_path}|{kind}|{symbol}"
        granularity = "surface"
        prefix = "group:surface"
    else:
        group_key = f"component|{relative_path}"
        granularity = "component"
        prefix = "group:component"
    digest = hashlib.sha256(group_key.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:32]}", granularity


def _surface_emit(
    rows: dict[str, dict[str, Any]],
    *,
    root: Path,
    path: Path,
    source_fingerprint: str,
    kind: str,
    symbol: str,
    node: ast.AST | None,
    source_text: str,
    observed: Mapping[str, Any] | None = None,
    span: Mapping[str, int] | None = None,
) -> str:
    # Keep the observation itself hard-bounded.  Callers also record a
    # blocker when they hit the boundary, but no later config/template/error
    # pass may grow a supposedly bounded result past the cap.
    if len(rows) >= _SURFACE_MAX_ROWS:
        return ""
    relative_path = _surface_relative(root, path)
    actual_span = dict(span or _surface_span(node or ast.Pass()))
    source_segment = ""
    if node is not None and kind in {"module", "function", "class"}:
        source_segment = ast.get_source_segment(source_text, node) or ""
    if not source_segment and actual_span["line_start"] > 0:
        lines = source_text.splitlines()
        source_segment = lines[actual_span["line_start"] - 1] if lines else ""
    source_segment = " ".join(source_segment.split())[:800]
    surface_id = _surface_id(relative_path, kind, symbol, actual_span)
    review_group_id, review_granularity = _surface_review_group(relative_path, kind, symbol)
    row: dict[str, Any] = {
        "surface_id": surface_id,
        "surface_kind": kind,
        "surface_class": _surface_class_for_kind(kind),
        "review_group_id": review_group_id,
        "review_granularity": review_granularity,
        "symbol": symbol,
        "source_path": relative_path,
        "source_ref": _surface_source_ref(relative_path, symbol, actual_span),
        "source_span": actual_span,
        "source_fingerprint": source_fingerprint,
        "observed": dict(observed or {}),
    }
    row["surface_fingerprint"] = _surface_hash(row)
    # An identical AST span should never silently overwrite an observation.
    # If a parser emits the same key twice, retain a deterministic collision
    # suffix and make the collision visible to the caller through its ID.
    if surface_id in rows and rows[surface_id] != row:
        collision_span = dict(actual_span)
        collision_span["column_end"] += 1
        surface_id = _surface_id(relative_path, kind, f"{symbol}:collision", collision_span)
        row["surface_id"] = surface_id
        row["source_ref"] = _surface_source_ref(relative_path, symbol, collision_span)
        # The first fingerprint belongs to the pre-collision row.  Remove it
        # before hashing the rewritten identity; otherwise a repeated
        # dynamic/plugin observation carries the old hash into its own hash
        # input and merge-time verification reports a false stale fingerprint.
        row.pop("surface_fingerprint", None)
        row["surface_fingerprint"] = _surface_hash(row)
    rows[surface_id] = row
    return surface_id


def _surface_node_specs(tree: ast.AST, *, module_symbol: str) -> tuple[tuple[str, str, ast.AST], ...]:
    specs: list[tuple[str, str, ast.AST]] = [("module", module_symbol, tree)]

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(child, ast.ClassDef) else "function"
                symbol = f"{prefix}.{child.name}" if prefix else child.name
                specs.append((kind, symbol, child))
                visit(child, symbol)
            elif not isinstance(child, (ast.Lambda,)):
                visit(child, prefix)

    visit(tree, module_symbol)
    return tuple(specs)


def _surface_scope_contexts(
    tree: ast.AST,
    *,
    relative_path: str,
    module_symbol: str,
) -> dict[int, dict[str, Any]]:
    """Build private lexical context for each implementation surface.

    ``_surface_node_specs`` deliberately exposes only the public observation
    tuple.  Call-graph resolution needs a little more information than that
    tuple carries: imports inside a function must not leak to its siblings,
    parameters and local assignments must shadow module names, and methods
    need to be distinguished from module-level functions.  Keep this context
    private so it cannot become model authority or alter the surface schema.
    """

    contexts: dict[int, dict[str, Any]] = {}

    def _kind(node: ast.AST) -> str:
        if isinstance(node, ast.ClassDef):
            return "class"
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return "function"
        return "module"

    def _argument_names(node: ast.AST) -> set[str]:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return set()
        arguments = node.args
        names = {
            str(argument.arg)
            for argument in (
                *getattr(arguments, "posonlyargs", ()),
                *getattr(arguments, "args", ()),
                *getattr(arguments, "kwonlyargs", ()),
            )
        }
        if arguments.vararg is not None:
            names.add(str(arguments.vararg.arg))
        if arguments.kwarg is not None:
            names.add(str(arguments.kwarg.arg))
        return names

    def _merge_imports(
        target: dict[str, list[str]],
        values: Mapping[str, Sequence[str]],
    ) -> None:
        for name, targets in values.items():
            bucket = target.setdefault(str(name), [])
            for target_name in targets:
                text = str(target_name)
                if text and text not in bucket:
                    bucket.append(text)

    def _single_import_bindings(node: ast.Import | ast.ImportFrom) -> dict[str, tuple[str, ...]]:
        # Reusing the source-level import parser keeps relative-package
        # arithmetic identical for module and function-local imports.
        synthetic = ast.Module(body=[node], type_ignores=[])
        return _surface_import_bindings(relative_path, synthetic)

    def walk_scope(
        node: ast.AST,
        symbol: str,
        parent_node: ast.AST | None,
        class_symbol: str,
    ) -> None:
        scope_kind = _kind(node)
        context: dict[str, Any] = {
            "node": node,
            "scope_kind": scope_kind,
            "symbol": symbol,
            "parent_node_id": id(parent_node) if parent_node is not None else None,
            "parent_symbol": (
                str(contexts[id(parent_node)].get("symbol", ""))
                if parent_node is not None and id(parent_node) in contexts
                else ""
            ),
            "is_class_member": isinstance(parent_node, ast.ClassDef),
            "class_symbol": symbol if scope_kind == "class" else class_symbol,
            "local_import_bindings": {},
            "bound_names": set(_argument_names(node)),
            "local_definition_symbols": {},
            "surface_id": _surface_id(
                relative_path,
                scope_kind,
                symbol,
                _surface_span(node),
            ),
        }
        contexts[id(node)] = context

        def visit_owned(current: ast.AST) -> None:
            for child in ast.iter_child_nodes(current):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    child_kind = "class" if isinstance(child, ast.ClassDef) else "function"
                    child_symbol = f"{symbol}.{child.name}" if symbol else str(child.name)
                    context["bound_names"].add(str(child.name))
                    context["local_definition_symbols"].setdefault(
                        str(child.name),
                        [],
                    ).append(child_symbol)
                    child_class_symbol = (
                        child_symbol
                        if child_kind == "class"
                        else str(context.get("class_symbol", ""))
                    )
                    walk_scope(child, child_symbol, node, child_class_symbol)
                    continue
                if isinstance(child, ast.Lambda):
                    # Lambda is not an emitted implementation surface and its
                    # local bindings must not leak into the enclosing facts.
                    continue
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    _merge_imports(
                        context["local_import_bindings"],
                        _single_import_bindings(child),
                    )
                    context["bound_names"].update(
                        str(name)
                        for name in _single_import_bindings(child)
                    )
                    continue
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                    context["bound_names"].add(str(child.id))
                elif isinstance(child, ast.ExceptHandler) and child.name:
                    context["bound_names"].add(str(child.name))
                visit_owned(child)

        visit_owned(node)

    walk_scope(tree, module_symbol, None, "")

    # Resolve imports along the lexical chain.  Class scope is intentionally
    # not a closure for methods; a method may use module imports and function
    # closures, but not an unqualified class-body import.
    for context in contexts.values():
        chain: list[dict[str, Any]] = []
        current: dict[str, Any] | None = context
        while current is not None:
            chain.append(current)
            parent_id = current.get("parent_node_id")
            current = contexts.get(parent_id) if isinstance(parent_id, int) else None
        chain.reverse()
        effective: dict[str, list[str]] = {}
        shadowed: set[str] = set()
        for ancestor in chain:
            ancestor_kind = str(ancestor.get("scope_kind", ""))
            if ancestor_kind == "class" and ancestor is not context and str(context.get("scope_kind")) == "function":
                continue
            local_imports = {
                str(name): [str(value) for value in values]
                for name, values in ancestor.get("local_import_bindings", {}).items()
                if isinstance(values, Sequence) and not isinstance(values, (str, bytes))
            }
            if ancestor_kind == "function":
                local_defs = {
                    str(name)
                    for name in ancestor.get("local_definition_symbols", {})
                }
                for name in set(ancestor.get("bound_names", ())) - set(local_imports):
                    if name in local_defs:
                        effective.pop(name, None)
                    else:
                        effective.pop(name, None)
                        shadowed.add(name)
            effective.update(local_imports)
        context["effective_import_bindings"] = {
            name: tuple(values) for name, values in sorted(effective.items())
        }
        context["shadowed_names"] = tuple(sorted(shadowed))

    return contexts


def _surface_function_facts(node: ast.AST) -> dict[str, Any]:
    calls: set[str] = set()
    effects: set[str] = set()
    errors: set[str] = set()
    recoveries: set[str] = set()
    dynamic_actions: set[str] = set()
    plugin_actions: set[str] = set()
    dynamic_calls: set[str] = set()
    returns_value = False

    # ``ast.walk`` over a module, class, or enclosing function also traverses
    # every nested definition.  That made a module surface appear to call all
    # of its child methods and inflated the global call graph with unrelated
    # duplicate names.  Visit the owned body only; nested definitions remain
    # separate implementation surfaces and are analyzed by their own rows.
    root = node

    class _OwnedFactsVisitor(ast.NodeVisitor):
        def _visit_owned_definition(self, current: ast.AST) -> None:
            if current is root:
                self.generic_visit(current)

        visit_FunctionDef = _visit_owned_definition
        visit_AsyncFunctionDef = _visit_owned_definition
        visit_ClassDef = _visit_owned_definition

        def visit_Call(self, current: ast.Call) -> None:
            name = _surface_call_name(current.func)
            leaf = name.rsplit(".", 1)[-1]
            calls.add(name)
            if leaf.casefold() in {item.casefold() for item in _EFFECT_CALL_NAMES}:
                effects.add(name)
            if _RECOVERY_CALL_RE.search(leaf):
                recoveries.add(name)
            if _UI_CALL_RE.search(leaf) and leaf.casefold() not in {"open", "close"}:
                dynamic_actions.add(name)
            if _PLUGIN_CALL_RE.search(name):
                plugin_actions.add(name)
            elif _DYNAMIC_CALL_RE.search(name):
                dynamic_calls.add(name)
            if leaf.casefold() in {"error", "exit", "abort", "fail"}:
                errors.add(name)
            self.generic_visit(current)

        def visit_Raise(self, current: ast.Raise) -> None:
            if current.exc is not None:
                error_node = current.exc.func if isinstance(current.exc, ast.Call) else current.exc
                errors.add(_surface_call_name(error_node))
            else:
                errors.add("reraised_exception")
            self.generic_visit(current)

        def visit_ExceptHandler(self, current: ast.ExceptHandler) -> None:
            errors.add(_surface_call_name(current.type) if current.type is not None else "Exception")
            self.generic_visit(current)

        def visit_Return(self, current: ast.Return) -> None:
            nonlocal returns_value
            if current.value is not None:
                returns_value = True
            self.generic_visit(current)

    visitor = _OwnedFactsVisitor()
    visitor.visit(root)
    return {
        "calls": sorted(calls),
        "effects": sorted(effects),
        "errors": sorted(errors),
        "recoveries": sorted(recoveries),
        "ui_actions": sorted(dynamic_actions),
        "plugin_actions": sorted(plugin_actions),
        "dynamic_calls": sorted(dynamic_calls),
        "returns_value": returns_value,
    }


def _surface_resolve_call_candidates(
    call_name: str,
    caller_symbol: str,
    candidates_by_leaf: Mapping[str, Sequence[Mapping[str, Any]]],
    caller_source_path: str | None = None,
    import_bindings: Mapping[str, str | Sequence[str]] | None = None,
    *,
    caller_context: Mapping[str, Any] | None = None,
    candidate_contexts: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[Mapping[str, Any]]:
    """Resolve source-only calls with lexical and exact-import boundaries.

    This resolver intentionally does not import modules or guess a target from
    a matching suffix.  The caller turns the exact candidate set into a source
    target, a finite dispatch set, or a deterministic external boundary.
    """

    normalized = str(call_name).strip()
    if normalized.startswith("<dynamic>"):
        return []

    context = caller_context if isinstance(caller_context, Mapping) else {}
    effective_imports: Mapping[str, str | Sequence[str]] = (
        context.get("effective_import_bindings", {})
        if isinstance(context.get("effective_import_bindings", {}), Mapping)
        else import_bindings or {}
    )
    if not effective_imports and isinstance(import_bindings, Mapping):
        effective_imports = import_bindings
    shadowed_names = {
        str(name) for name in context.get("shadowed_names", ())
    }
    caller_class_symbol = str(context.get("class_symbol", ""))

    def values(raw: Any) -> tuple[str, ...]:
        if isinstance(raw, str):
            return (raw,)
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            return tuple(str(item) for item in raw if str(item))
        return ()

    def candidate_context(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
        direct = candidate.get("scope_context")
        if isinstance(direct, Mapping):
            return direct
        surface_id = str(candidate.get("surface_id", ""))
        if isinstance(candidate_contexts, Mapping):
            selected = candidate_contexts.get(surface_id)
            if isinstance(selected, Mapping):
                return selected
        return {}

    def is_method(candidate: Mapping[str, Any]) -> bool:
        candidate_scope = candidate_context(candidate)
        return bool(candidate_scope.get("is_class_member"))

    def is_scope_ancestor(parent_symbol: str, child_symbol: str) -> bool:
        parent = str(parent_symbol).strip()
        child = str(child_symbol).strip()
        return bool(parent) and (child == parent or child.startswith(f"{parent}."))

    def is_unqualified_visible(candidate: Mapping[str, Any]) -> bool:
        # A bare name in a module/function body does not dispatch to an
        # arbitrary class method.  Methods are only eligible through an
        # explicit receiver such as ``self.method``.
        if is_method(candidate):
            return False
        candidate_scope = candidate_context(candidate)
        parent_symbol = str(candidate_scope.get("parent_symbol", ""))
        if not parent_symbol:
            return True
        # Nested definitions are visible from their defining scope and its
        # descendants (closure lookup); unrelated nested scopes are not.
        return is_scope_ancestor(parent_symbol, str(caller_symbol))

    def deduplicate(items: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        by_id: dict[str, Mapping[str, Any]] = {}
        for item in items:
            by_id[str(item.get("surface_id", ""))] = item
        return [by_id[key] for key in sorted(by_id)]

    leaf = normalized.rsplit(".", 1)[-1]
    candidates = list(candidates_by_leaf.get(leaf, ()))

    # A local parameter/assignment shadows a module-level candidate.  The
    # caller records this as a dynamic-boundary edge rather than silently
    # treating the global function as the callback implementation.
    if "." not in normalized and normalized in shadowed_names:
        return []

    # ``self.method`` is the one receiver form which can be proven from the
    # lexical surface itself.  It binds to the current class owner only.
    if normalized.startswith("self.") and caller_class_symbol:
        method_name = normalized.rsplit(".", 1)[-1]
        expected_symbol = f"{caller_class_symbol}.{method_name}"
        return deduplicate(
            candidate
            for candidate in candidates_by_leaf.get(method_name, ())
            if str(candidate.get("symbol", "")) == expected_symbol
        )

    if "." not in normalized:
        raw_imported_targets = effective_imports.get(normalized, ())
        imported_targets = values(raw_imported_targets)
        if imported_targets:
            imported_candidates = [
                candidate
                for imported_target in imported_targets
                for candidate in candidates_by_leaf.get(
                    str(imported_target).rsplit(".", 1)[-1], ()
                )
                if _surface_import_target_matches(
                    str(candidate.get("symbol", "")),
                    str(imported_target),
                )
            ]
            return deduplicate(imported_candidates)

        same_source: list[Mapping[str, Any]] = []
        if isinstance(caller_source_path, str) and caller_source_path.strip():
            caller_path = caller_source_path.replace("\\", "/")
            same_source = [
                candidate
                for candidate in candidates
                if str(candidate.get("source_path", "")).replace("\\", "/")
                == caller_path
                and is_unqualified_visible(candidate)
            ]
        if same_source:
            # Direct lexical recursion wins over a same-leaf class method or
            # another unrelated same-source candidate.
            exact_self = [
                candidate
                for candidate in same_source
                if str(candidate.get("symbol", "")) == str(caller_symbol)
            ]
            if exact_self:
                return deduplicate(exact_self)
            return deduplicate(same_source)
        # Keep genuine cross-file ambiguity visible, but never resolve a
        # single unimported candidate as if an import had been declared.
        return deduplicate(candidates) if len(candidates) > 1 else []

    # Resolve qualified calls only through the longest exact imported prefix.
    # This handles both ``import pkg.helpers`` and ``from pkg import helpers``
    # without allowing a suffix-only match.
    prefix_keys = [
        str(prefix)
        for prefix in effective_imports
        if normalized == str(prefix)
        or normalized.startswith(f"{prefix}.")
    ]
    if prefix_keys:
        longest_length = max(len(prefix.split(".")) for prefix in prefix_keys)
        imported_candidates: list[Mapping[str, Any]] = []
        for prefix in sorted(
            (item for item in prefix_keys if len(item.split(".")) == longest_length),
        ):
            remainder = normalized[len(prefix):].lstrip(".")
            for imported_prefix in values(effective_imports.get(prefix, ())):
                imported_target = ".".join(
                    item for item in (imported_prefix, remainder) if item
                )
                imported_candidates.extend(
                    candidate
                    for candidate in candidates_by_leaf.get(
                        imported_target.rsplit(".", 1)[-1], ()
                    )
                    if _surface_import_target_matches(
                        str(candidate.get("symbol", "")),
                        imported_target,
                    )
                )
        return deduplicate(imported_candidates)

    # A qualified name without an explicit import is external/dynamic.  If
    # several source surfaces happen to share the exact spelling, return the
    # complete exact candidate set for a deterministic dispatch edge; a single
    # accidental suffix match is never a source resolution.
    qualified = [
        candidate
        for candidate in candidates
        if str(candidate.get("symbol", "")) == normalized
    ]
    return deduplicate(qualified) if len(qualified) > 1 else []


def _surface_call_requires_dynamic_boundary(
    call_name: str,
    caller_context: Mapping[str, Any] | None,
) -> bool:
    """Return whether a call is a shadowed receiver/callback boundary."""

    if not isinstance(caller_context, Mapping):
        return False
    normalized = str(call_name).strip()
    if normalized.startswith("<dynamic>"):
        return True
    if normalized.startswith("self.") and str(caller_context.get("class_symbol", "")):
        return False
    first_segment = normalized.split(".", 1)[0]
    shadowed = {
        str(name) for name in caller_context.get("shadowed_names", ())
    }
    return bool(first_segment and first_segment in shadowed)


def _surface_call_external_target_id(
    caller_surface_id: str,
    call_name: str,
    boundary_kind: str,
) -> str:
    """Return a stable identity for one explicitly resolved external contract.

    The contract is not a guessed source function and is not an unresolved
    observation.  It is the exact current call expression in the caller's
    lexical surface, classified by its external contract kind.  The identity
    is deterministic so semantic owners can bind the contract to a current
    oracle without a compatibility reader or a suffix-based target guess.
    """

    payload = "|".join(
        (
            str(caller_surface_id).strip(),
            str(call_name).strip(),
            str(boundary_kind).strip(),
        )
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"contract:{boundary_kind}:{digest}"


def _surface_external_contract_target_fields(contract_id: str) -> dict[str, str]:
    """Return the mandatory current identity for an external call target.

    ``resolved_external_contract`` is a resolved target class, not a typed
    observation or an unresolved placeholder.  Keep that distinction explicit
    on both the edge and its registry row so a producer cannot claim closure by
    carrying only a free-form ``external_contract_id``.  The registry join is
    the producer-local proof: the id, caller, expression, and boundary kind are
    conserved in one exact current row.
    """

    normalized_id = str(contract_id).strip()
    return {
        "target_kind": _CURRENT_EXTERNAL_CONTRACT_TARGET_KIND,
        "target_identity": normalized_id,
        "target_status": _CURRENT_EXTERNAL_CONTRACT_TARGET_STATUS,
        "target_proof": _CURRENT_EXTERNAL_CONTRACT_TARGET_PROOF,
    }


def _surface_external_contracts(
    call_graph: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Materialize the exact current contract identities used by call edges.

    A contract row is a source observation of an external/dynamic target, not
    a guessed implementation.  Keeping it in the discovery artifact makes
    the target set auditable and lets the semantic owner bind every contract
    without treating the edge as an unresolved typed observation.
    """

    contracts: dict[str, dict[str, Any]] = {}
    for edge in call_graph:
        if str(edge.get("resolution", "")).strip() != "resolved_external_contract":
            continue
        contract_id = str(edge.get("external_contract_id", "")).strip()
        if not contract_id:
            continue
        row = {
            "contract_id": contract_id,
            **_surface_external_contract_target_fields(contract_id),
            "boundary_kind": str(edge.get("boundary_kind", "")).strip(),
            "callee_name": str(edge.get("callee_name", "")).strip(),
            "caller_surface_id": str(edge.get("caller_surface_id", "")).strip(),
        }
        prior = contracts.get(contract_id)
        if prior is not None and any(prior.get(key) != row.get(key) for key in row):
            # The id includes caller and call spelling, so a collision is a
            # deterministic source-integrity blocker rather than a choice.
            raise PublicBehaviorSurfaceAuditError(
                f"external contract id collision: {contract_id}"
            )
        source_ref = str(edge.get("caller_source_ref", "")).strip()
        if prior is None:
            row["caller_source_refs"] = [source_ref] if source_ref else []
            contracts[contract_id] = row
        elif source_ref and source_ref not in prior["caller_source_refs"]:
            prior["caller_source_refs"] = sorted(
                [*prior["caller_source_refs"], source_ref]
            )
    return [contracts[key] for key in sorted(contracts)]


def _surface_resolve_call_edge(
    call_name: str,
    caller_surface_id: str,
    caller_symbol: str,
    candidates_by_leaf: Mapping[str, Sequence[Mapping[str, Any]]],
    caller_source_path: str | None = None,
    import_bindings: Mapping[str, str | Sequence[str]] | None = None,
    *,
    caller_context: Mapping[str, Any] | None = None,
    candidate_contexts: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Close one call site to a source, dispatch set, or named boundary.

    ``resolved_static_dispatch`` is an exact finite set of source candidates.
    A dynamic receiver/callback and a call with no current source candidate
    get a stable *external contract* identity.  Both forms are current
    resolved targets, not uncertainty observations; the graph therefore has
    no ``ambiguous``/``unknown``/boundary-only call state.
    """

    candidates = _surface_resolve_call_candidates(
        call_name,
        caller_symbol,
        candidates_by_leaf,
        caller_source_path,
        import_bindings,
        caller_context=caller_context,
        candidate_contexts=candidate_contexts,
    )
    dynamic_boundary = _surface_call_requires_dynamic_boundary(
        str(call_name), caller_context
    )
    if dynamic_boundary:
        normalized_call_name = str(call_name).strip()
        if normalized_call_name.startswith("<dynamic>"):
            boundary_kind = "dynamic_expression"
        else:
            boundary_kind = (
                "dynamic_receiver"
                if "." in normalized_call_name
                else "dynamic_callback"
            )
        external_contract_id = _surface_call_external_target_id(
            caller_surface_id, call_name, boundary_kind
        )
        return {
            "resolved_surface_ids": [],
            "resolution": "resolved_external_contract",
            "boundary_kind": boundary_kind,
            "external_contract_id": external_contract_id,
            **_surface_external_contract_target_fields(external_contract_id),
        }
    candidate_ids = sorted(
        {
            str(candidate.get("surface_id", "")).strip()
            for candidate in candidates
            if str(candidate.get("surface_id", "")).strip()
        }
    )
    if len(candidate_ids) == 1:
        return {
            "resolved_surface_ids": candidate_ids,
            "resolution": "resolved",
        }
    if len(candidate_ids) > 1:
        return {
            "resolved_surface_ids": candidate_ids,
            "resolution": "resolved_static_dispatch",
            "dispatch_kind": "source_candidate_set",
        }
    boundary_kind = "external_unbound_call"
    external_contract_id = _surface_call_external_target_id(
        caller_surface_id, call_name, boundary_kind
    )
    return {
        "resolved_surface_ids": [],
        "resolution": "resolved_external_contract",
        "boundary_kind": boundary_kind,
        "external_contract_id": external_contract_id,
        **_surface_external_contract_target_fields(external_contract_id),
    }


def _surface_empty_or_placeholder_nodes(node: ast.AST, source_text: str) -> tuple[tuple[str, ast.AST], ...]:
    rows: list[tuple[str, ast.AST]] = []
    for child in ast.walk(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = list(getattr(child, "body", ()))
            meaningful = [
                item
                for item in body
                if not (
                    isinstance(item, ast.Expr)
                    and isinstance(getattr(item, "value", None), ast.Constant)
                    and isinstance(item.value.value, str)
                )
            ]
            if len(meaningful) == 1 and isinstance(meaningful[0], (ast.Pass, ast.Expr)):
                value = getattr(meaningful[0], "value", None)
                if isinstance(meaningful[0], ast.Pass) or isinstance(value, ast.Constant) and value.value is Ellipsis:
                    rows.append(("empty_or_placeholder", meaningful[0]))
        if isinstance(child, ast.Raise) and isinstance(child.exc, ast.Call):
            name = _surface_call_name(child.exc.func)
            if name.rsplit(".", 1)[-1] == "NotImplementedError":
                rows.append(("not_implemented_error", child))
        if isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant) and child.value.value is Ellipsis:
            rows.append(("ellipsis_placeholder", child))
    for index, line in enumerate(source_text.splitlines(), start=1):
        if _PLACEHOLDER_RE.search(line):
            rows.append(("placeholder_marker", ast.Pass(lineno=index, col_offset=0, end_lineno=index, end_col_offset=len(line))))
    return tuple(rows)


def discover_implementation_behavior_surfaces(
    root: str | Path,
    *,
    source_paths: Sequence[str | Path] | None = None,
    shard_id: str | None = None,
    _candidate_paths: Sequence[Path] | None = None,
) -> dict[str, Any]:
    """Discover production implementation surfaces from source only.

    This function is intentionally observation-only.  It does not import the
    target package and never reads model files or tests to manufacture rows.
    A mapping from these observations to intent/model/test is a separate,
    author-owned input reviewed by :func:`audit_implementation_behavior_surface`.
    """

    bounded_root = Path(root).resolve()
    if not bounded_root.is_dir():
        raise PublicBehaviorSurfaceAuditError(f"implementation surface root is not a directory: {bounded_root}")
    rows: dict[str, dict[str, Any]] = {}
    source_identities: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    source_texts: dict[Path, str] = {}
    source_fingerprints: dict[Path, str] = {}
    source_import_bindings: dict[str, dict[str, tuple[str, ...]]] = {}
    graph_records: list[dict[str, Any]] = []
    externally_bound_names: set[str] = set()
    selected_paths, selection_findings = _resolve_surface_source_selection(
        bounded_root,
        source_paths,
        candidate_paths=_candidate_paths,
    )
    findings.extend(selection_findings)
    if shard_id is not None and (not isinstance(shard_id, str) or not shard_id.strip()):
        findings.append(
            {
                "code": "surface_shard_id_invalid",
                "severity": "blocker",
                "message": "shard_id must be a non-empty string when supplied",
            }
        )
    shard_label = shard_id.strip() if isinstance(shard_id, str) and shard_id.strip() else "full"
    if len(selected_paths) > _SURFACE_MAX_FILES:
        findings.append({
            "code": "surface_discovery_file_budget_exceeded",
            "severity": "blocker",
            "message": f"production source discovery found {len(selected_paths)} source files; the bounded maximum is {_SURFACE_MAX_FILES}",
        })
        selected_paths = selected_paths[:_SURFACE_MAX_FILES]
    source_bytes_total = sum(path.stat().st_size for path in selected_paths if path.is_file())
    if source_bytes_total > _SURFACE_MAX_SOURCE_BYTES:
        findings.append({
            "code": "surface_discovery_source_budget_exceeded",
            "severity": "blocker",
            "message": f"production source discovery spans {source_bytes_total} bytes; the bounded maximum is {_SURFACE_MAX_SOURCE_BYTES}",
        })
    python_paths = tuple(path for path in selected_paths if path.suffix.casefold() == ".py")
    config_paths = tuple(path for path in selected_paths if path not in python_paths)
    for path in python_paths:
        if len(rows) >= _SURFACE_MAX_ROWS:
            findings.append({
                "code": "surface_discovery_row_budget_exceeded",
                "severity": "blocker",
                "message": f"production source discovery exceeded the bounded maximum of {_SURFACE_MAX_ROWS} surfaces",
            })
            break
        relative_path = _surface_relative(bounded_root, path)
        try:
            source_bytes = path.read_bytes()
            source_text = source_bytes.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            findings.append({"code": "surface_source_read_failure", "severity": "blocker", "source_path": relative_path, "message": str(exc)})
            continue
        source_fingerprint = _sha256_file(path)
        source_stat = path.stat()
        source_identities.append(
            {
                "source_path": relative_path,
                "source_fingerprint": source_fingerprint,
                "source_size": int(source_stat.st_size),
                "source_mtime_ns": int(source_stat.st_mtime_ns),
            }
        )
        source_texts[path] = source_text
        source_fingerprints[path] = source_fingerprint
        try:
            tree = ast.parse(source_text, filename=relative_path)
        except SyntaxError as exc:
            findings.append({"code": "surface_source_parse_failure", "severity": "blocker", "source_path": relative_path, "message": str(exc)})
            continue
        source_import_bindings[relative_path] = _surface_import_bindings(
            relative_path,
            tree,
        )
        module_symbol = relative_path[:-3].replace("/", ".") if relative_path.endswith(".py") else relative_path
        scope_contexts = _surface_scope_contexts(
            tree,
            relative_path=relative_path,
            module_symbol=module_symbol,
        )
        specs = _surface_node_specs(tree, module_symbol=module_symbol)
        for kind, symbol, node in specs:
            # Module facts would walk the complete file once more while every
            # child function/class already receives its own scoped facts.  The
            # reverse denominator needs the module surface identity, not a
            # duplicated aggregate of all descendants.
            facts = {} if kind == "module" else _surface_function_facts(node)
            emitted_surface_id = _surface_emit(
                rows,
                root=bounded_root,
                path=path,
                source_fingerprint=source_fingerprint,
                kind=kind,
                symbol=symbol,
                node=node,
                source_text=source_text,
                observed=facts,
            )
            if kind in {"module", "function", "class"}:
                graph_records.append(
                    {
                        "surface_id": emitted_surface_id,
                        "surface_kind": kind,
                        "symbol": symbol,
                        "source_path": relative_path,
                        "source_ref": _surface_source_ref(
                            relative_path,
                            symbol,
                            _surface_span(node),
                        ),
                        "node": node,
                        "scope_context": scope_contexts.get(id(node), {}),
                    }
                )
        for node in ast.walk(tree):
            if len(rows) >= _SURFACE_MAX_ROWS:
                findings.append({
                    "code": "surface_discovery_row_budget_exceeded",
                    "severity": "blocker",
                    "source_path": relative_path,
                    "message": f"production source discovery exceeded the bounded maximum of {_SURFACE_MAX_ROWS} surfaces",
                })
                break
            if isinstance(node, ast.Assign):
                targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
                if "__all__" in targets:
                    for name in _surface_literal_strings(node.value):
                        externally_bound_names.add(name.rsplit(".", 1)[-1])
                        _surface_emit(rows, root=bounded_root, path=path, source_fingerprint=source_fingerprint, kind="export", symbol=f"__all__.{name}", node=node.value, source_text=source_text, observed={"export_name": name})
                if "API_SURFACE" in targets:
                    for name in _surface_literal_strings(node.value):
                        externally_bound_names.add(name.rsplit(".", 1)[-1])
                        _surface_emit(rows, root=bounded_root, path=path, source_fingerprint=source_fingerprint, kind="api", symbol=f"API_SURFACE.{name}", node=node.value, source_text=source_text, observed={"api_name": name})
                if any(name.casefold().endswith(("_config", "_settings", "_options", "_defaults")) or name.casefold() in {"config", "settings", "options", "defaults"} for name in targets):
                    _surface_emit(rows, root=bounded_root, path=path, source_fingerprint=source_fingerprint, kind="config", symbol=targets[0] if targets else "config", node=node, source_text=source_text, observed={"config_names": targets})
            if isinstance(node, ast.Call):
                call_name = _surface_call_name(node.func)
                leaf = call_name.rsplit(".", 1)[-1]
                if isinstance(node.func, ast.Attribute) and node.func.attr == "add_parser" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    _surface_emit(rows, root=bounded_root, path=path, source_fingerprint=source_fingerprint, kind="cli_command", symbol=f"{call_name}:{node.args[0].value}", node=node, source_text=source_text, observed={"command": node.args[0].value})
                    if _INSTALL_CALL_RE.search(str(node.args[0].value)):
                        _surface_emit(
                            rows,
                            root=bounded_root,
                            path=path,
                            source_fingerprint=source_fingerprint,
                            kind="install",
                            symbol=f"{call_name}:{node.args[0].value}",
                            node=node,
                            source_text=source_text,
                            observed={
                                "operation": node.args[0].value,
                                "boundary": "cli_install_or_upgrade",
                            },
                        )
                if leaf.casefold() in {"filetemplatecommand", "templatecommand", "register_template", "add_template"}:
                    template_name = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str) else call_name
                    _surface_emit(rows, root=bounded_root, path=path, source_fingerprint=source_fingerprint, kind="template", symbol=f"{call_name}:{template_name}", node=node, source_text=source_text, observed={"template": template_name})
                if leaf.casefold() in {item.casefold() for item in _EFFECT_CALL_NAMES}:
                    _surface_emit(rows, root=bounded_root, path=path, source_fingerprint=source_fingerprint, kind="effect", symbol=call_name, node=node, source_text=source_text, observed={"effect": call_name})
                if _INSTALL_CALL_RE.search(call_name):
                    _surface_emit(
                        rows,
                        root=bounded_root,
                        path=path,
                        source_fingerprint=source_fingerprint,
                        kind="install",
                        symbol=call_name,
                        node=node,
                        source_text=source_text,
                        observed={"operation": call_name, "boundary": "installation_or_upgrade"},
                    )
                if _RECOVERY_CALL_RE.search(leaf):
                    _surface_emit(rows, root=bounded_root, path=path, source_fingerprint=source_fingerprint, kind="recovery", symbol=call_name, node=node, source_text=source_text, observed={"recovery": call_name})
                if _UI_CALL_RE.search(leaf) and leaf.casefold() not in {"open", "close"}:
                    _surface_emit(rows, root=bounded_root, path=path, source_fingerprint=source_fingerprint, kind="ui_like_action", symbol=call_name, node=node, source_text=source_text, observed={"action": call_name})
                if _PLUGIN_CALL_RE.search(call_name):
                    _surface_emit(rows, root=bounded_root, path=path, source_fingerprint=source_fingerprint, kind="plugin", symbol=call_name, node=node, source_text=source_text, observed={"plugin": call_name})
                elif _DYNAMIC_CALL_RE.search(call_name):
                    _surface_emit(rows, root=bounded_root, path=path, source_fingerprint=source_fingerprint, kind="dynamic", symbol=call_name, node=node, source_text=source_text, observed={"dynamic": call_name})
                if leaf.casefold() in {"error", "exit", "abort", "fail"}:
                    _surface_emit(rows, root=bounded_root, path=path, source_fingerprint=source_fingerprint, kind="error", symbol=call_name, node=node, source_text=source_text, observed={"error": call_name})
            if isinstance(node, ast.Raise):
                error_node = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
                error_symbol = _surface_call_name(error_node) if error_node is not None else "reraised_exception"
                _surface_emit(rows, root=bounded_root, path=path, source_fingerprint=source_fingerprint, kind="error", symbol=error_symbol, node=node, source_text=source_text, observed={"error": error_symbol})
            if isinstance(node, ast.ExceptHandler):
                error_symbol = _surface_call_name(node.type) if node.type is not None else "Exception"
                _surface_emit(rows, root=bounded_root, path=path, source_fingerprint=source_fingerprint, kind="error", symbol=f"handler:{error_symbol}", node=node, source_text=source_text, observed={"handler": error_symbol})
        for placeholder_kind, node in _surface_empty_or_placeholder_nodes(tree, source_text):
            _surface_emit(rows, root=bounded_root, path=path, source_fingerprint=source_fingerprint, kind="placeholder", symbol=placeholder_kind, node=node, source_text=source_text, observed={"placeholder": placeholder_kind})
        if len(rows) > _SURFACE_MAX_ROWS:
            findings.append({
                "code": "surface_discovery_row_budget_exceeded",
                "severity": "blocker",
                "source_path": relative_path,
                "message": f"production source discovery exceeded the bounded maximum of {_SURFACE_MAX_ROWS} surfaces",
            })
            break

    for path in config_paths:
        if len(rows) >= _SURFACE_MAX_ROWS:
            break
        relative_path = _surface_relative(bounded_root, path)
        source_fingerprint = _sha256_file(path)
        source_stat = path.stat()
        source_identities.append(
            {
                "source_path": relative_path,
                "source_fingerprint": source_fingerprint,
                "source_size": int(source_stat.st_size),
                "source_mtime_ns": int(source_stat.st_mtime_ns),
            }
        )
        source_text = path.read_text(encoding="utf-8", errors="replace")
        source_texts[path] = source_text
        source_fingerprints[path] = source_fingerprint
        span = {"line_start": 1, "line_end": max(1, len(source_text.splitlines())), "column_start": 0, "column_end": 0}
        _surface_emit(rows, root=bounded_root, path=path, source_fingerprint=source_fingerprint, kind="config", symbol=relative_path, node=None, source_text=source_text, observed={"config_file": relative_path}, span=span)
        if path.name.casefold() == "pyproject.toml":
            try:
                payload = tomllib.loads(source_text)
            except tomllib.TOMLDecodeError as exc:
                findings.append({"code": "surface_config_parse_failure", "severity": "blocker", "source_path": relative_path, "message": str(exc)})
            else:
                # A package manifest is itself an installation boundary even
                # when the repository does not contain a Python function named
                # ``install``.  Keep this observation source-only and bind it
                # to the exact manifest span; the semantic map must still
                # supply the installer owner, tests, and terminal receipt.
                if isinstance(payload.get("build-system"), Mapping) or isinstance(payload.get("project"), Mapping):
                    _surface_emit(
                        rows,
                        root=bounded_root,
                        path=path,
                        source_fingerprint=source_fingerprint,
                        kind="install",
                        symbol="pyproject.installation_boundary",
                        node=None,
                        source_text=source_text,
                        observed={"config_file": relative_path, "boundary": "package_installation"},
                        span=span,
                    )
                scripts = payload.get("project", {}).get("scripts", {}) if isinstance(payload.get("project"), Mapping) else {}
                if isinstance(scripts, Mapping):
                    lines = source_text.splitlines()
                    for name in sorted(str(key) for key in scripts):
                        if len(rows) >= _SURFACE_MAX_ROWS:
                            break
                        target = scripts.get(name)
                        if isinstance(target, str) and ":" in target:
                            externally_bound_names.add(
                                target.rsplit(":", 1)[-1].split(".", 1)[-1]
                            )
                        line_no = next((index for index, line in enumerate(lines, start=1) if re.match(rf"^\s*{re.escape(name)}\s*=", line)), 1)
                        script_span = {"line_start": line_no, "line_end": line_no, "column_start": 0, "column_end": len(lines[line_no - 1]) if lines else 0}
                        _surface_emit(
                            rows,
                            root=bounded_root,
                            path=path,
                            source_fingerprint=source_fingerprint,
                            kind="cli_entrypoint",
                            symbol=f"project.scripts.{name}",
                            node=None,
                            source_text=source_text,
                            observed={
                                "entrypoint": name,
                                "target": target if isinstance(target, str) else "",
                            },
                            span=script_span,
                        )
                        if _INSTALL_CALL_RE.search(name) or (
                            isinstance(target, str) and _INSTALL_CALL_RE.search(target)
                        ):
                            _surface_emit(
                                rows,
                                root=bounded_root,
                                path=path,
                                source_fingerprint=source_fingerprint,
                                kind="install",
                                symbol=f"project.scripts.{name}",
                                node=None,
                                source_text=source_text,
                                observed={
                                    "entrypoint": name,
                                    "target": target if isinstance(target, str) else "",
                                    "boundary": "console_install_or_upgrade",
                                },
                                span=script_span,
                            )

    # Build a source-only local call graph. Every call site closes to one
    # current source target, an exact finite dispatch set, or a deterministic
    # external-contract target. A function with no source incoming edge and no
    # explicit export/API/console binding receives a separate
    # unreachable_or_unbound observation so the semantic map must close it as
    # governed, internally proven, or retired with current proof.
    graph_by_leaf: dict[str, list[dict[str, Any]]] = {}
    for record in graph_records:
        leaf = str(record["symbol"]).rsplit(".", 1)[-1]
        graph_by_leaf.setdefault(leaf, []).append(record)
    incoming: dict[str, set[str]] = {
        str(record["surface_id"]): set() for record in graph_records
    }
    call_graph: list[dict[str, Any]] = []
    for record in graph_records:
        facts = _surface_function_facts(record["node"])
        for call_name in facts["calls"]:
            edge_resolution = _surface_resolve_call_edge(
                str(call_name),
                str(record["surface_id"]),
                str(record["symbol"]),
                graph_by_leaf,
                str(record["source_path"]),
                source_import_bindings.get(str(record["source_path"]), {}),
                caller_context=(
                    record.get("scope_context")
                    if isinstance(record.get("scope_context"), Mapping)
                    else None
                ),
            )
            resolved_ids = list(edge_resolution["resolved_surface_ids"])
            for resolved_id in resolved_ids:
                incoming[resolved_id].add(str(record["surface_id"]))
            call_graph.append(
                {
                    "caller_surface_id": str(record["surface_id"]),
                    "caller_source_ref": record["source_ref"],
                    "callee_name": call_name,
                    **edge_resolution,
                }
            )

    unbound_surface_ids: list[str] = []
    for record in graph_records:
        if record["surface_kind"] != "function":
            continue
        symbol_leaf = str(record["symbol"]).rsplit(".", 1)[-1]
        if symbol_leaf.startswith("_") or symbol_leaf in externally_bound_names:
            continue
        original_surface_id = str(record["surface_id"])
        if incoming.get(original_surface_id):
            continue
        unbound_id = _surface_emit(
            rows,
            root=bounded_root,
            path=bounded_root / str(record["source_path"]),
            source_fingerprint=source_fingerprints.get(
                bounded_root / str(record["source_path"]),
                "",
            ),
            kind="unreachable_or_unbound",
            symbol=str(record["symbol"]),
            node=record["node"],
            source_text=source_texts.get(
                bounded_root / str(record["source_path"]),
                "",
            ),
            observed={
                "original_surface_id": original_surface_id,
                "reachability": "unknown_external_or_unbound",
                "incoming_local_call_count": 0,
                "call_graph": "source_only",
            },
        )
        if unbound_id:
            unbound_surface_ids.append(unbound_id)

    if not source_identities:
        findings.append({
            "code": "surface_discovery_no_production_sources",
            "severity": "blocker",
            "message": "bounded production source discovery found no eligible implementation or configuration source",
        })
    if len(rows) >= _SURFACE_MAX_ROWS and not any(
        item.get("code") == "surface_discovery_row_budget_exceeded" for item in findings
    ):
        findings.append({
            "code": "surface_discovery_row_budget_exceeded",
            "severity": "blocker",
            "message": f"production source discovery reached the bounded maximum of {_SURFACE_MAX_ROWS} surfaces",
        })
    # Multiple nested AST passes can observe the same budget boundary.  Keep
    # one deterministic blocker so the receipt is stable and easy to consume.
    budget_findings = [
        item for item in findings if item.get("code") == "surface_discovery_row_budget_exceeded"
    ]
    if budget_findings:
        first_budget_finding = sorted(
            budget_findings,
            key=lambda item: (item.get("source_path", ""), item.get("message", "")),
        )[0]
        findings = [
            item for item in findings if item.get("code") != "surface_discovery_row_budget_exceeded"
        ]
        findings.append(first_budget_finding)
    ordered_rows = tuple(sorted(rows.values(), key=lambda row: row["surface_id"]))
    discovery_payload = {
        "schema_version": IMPLEMENTATION_SURFACE_AUDIT_SCHEMA,
        "shard_id": shard_label,
        "source_paths": _surface_relative_paths(bounded_root, selected_paths),
        "source_identities": [
            _source_identity_content_projection(row)
            for row in sorted(source_identities, key=lambda row: row["source_path"])
        ],
        "surfaces": ordered_rows,
        "call_graph": sorted(
            call_graph,
            key=lambda row: (
                row["caller_surface_id"],
                row["callee_name"],
                row["resolution"],
            ),
        ),
        "external_contracts": _surface_external_contracts(call_graph),
        "unbound_surface_ids": sorted(set(unbound_surface_ids)),
    }
    return {
        "schema_version": IMPLEMENTATION_SURFACE_AUDIT_SCHEMA,
        "shard_id": shard_label,
        "source_paths": _surface_relative_paths(bounded_root, selected_paths),
        "status": "blocked" if any(item.get("severity") == "blocker" for item in findings) else "passed",
        "claim_boundary": "Static production implementation surfaces only; no intent, model, test execution, or runtime behavior is inferred.",
        "source_identities": sorted(
            source_identities, key=lambda row: row["source_path"]
        ),
        "surfaces": list(ordered_rows),
        "surface_count": len(ordered_rows),
        "call_graph": discovery_payload["call_graph"],
        "external_contracts": discovery_payload["external_contracts"],
        "unbound_surface_ids": discovery_payload["unbound_surface_ids"],
        "findings": sorted(findings, key=lambda item: (item.get("source_path", ""), item.get("code", ""), item.get("message", ""))),
        "discovery_fingerprint": _surface_hash(discovery_payload),
    }


def _surface_source_row_upper_bound(
    root: Path,
    path: Path,
) -> tuple[int, str, list[dict[str, Any]]]:
    """Count a conservative per-file row upper bound without importing code."""

    relative = _surface_relative(root, path)
    findings: list[dict[str, Any]] = []
    try:
        source_bytes = path.read_bytes()
        source_text = source_bytes.decode("utf-8")
        source_fingerprint = _sha256_file(path)
    except (OSError, UnicodeError) as exc:
        return (
            0,
            "",
            [
                {
                    "code": "surface_source_read_failure",
                    "severity": "blocker",
                    "source_path": relative,
                    "message": str(exc),
                }
            ],
        )
    if path.suffix.casefold() != ".py":
        row_count = 1
        if path.name.casefold() == "pyproject.toml":
            try:
                payload = tomllib.loads(source_text)
            except tomllib.TOMLDecodeError as exc:
                findings.append(
                    {
                        "code": "surface_config_parse_failure",
                        "severity": "blocker",
                        "source_path": relative,
                        "message": str(exc),
                    }
                )
            else:
                if isinstance(payload.get("build-system"), Mapping) or isinstance(payload.get("project"), Mapping):
                    row_count += 1
                scripts = (
                    payload.get("project", {}).get("scripts", {})
                    if isinstance(payload.get("project"), Mapping)
                    else {}
                )
                if isinstance(scripts, Mapping):
                    row_count += len(scripts)
                    row_count += sum(
                        1
                        for name, target in scripts.items()
                        if _INSTALL_CALL_RE.search(str(name))
                        or (isinstance(target, str) and _INSTALL_CALL_RE.search(target))
                    )
        return row_count, source_fingerprint, findings

    try:
        tree = ast.parse(source_text, filename=relative)
    except SyntaxError as exc:
        findings.append(
            {
                "code": "surface_source_parse_failure",
                "severity": "blocker",
                "source_path": relative,
                "message": str(exc),
            }
        )
        return 0, source_fingerprint, findings

    row_count = len(_surface_node_specs(tree, module_symbol=relative[:-3].replace("/", ".")))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if "__all__" in targets:
                row_count += len(_surface_literal_strings(node.value))
            if "API_SURFACE" in targets:
                row_count += len(_surface_literal_strings(node.value))
            if any(
                name.casefold().endswith(("_config", "_settings", "_options", "_defaults"))
                or name.casefold() in {"config", "settings", "options", "defaults"}
                for name in targets
            ):
                row_count += 1
        if isinstance(node, ast.Call):
            call_name = _surface_call_name(node.func)
            leaf = call_name.rsplit(".", 1)[-1]
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_parser"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                row_count += 1
                if _INSTALL_CALL_RE.search(str(node.args[0].value)):
                    row_count += 1
            if leaf.casefold() in {
                "filetemplatecommand",
                "templatecommand",
                "register_template",
                "add_template",
            }:
                row_count += 1
            if leaf.casefold() in {item.casefold() for item in _EFFECT_CALL_NAMES}:
                row_count += 1
            if _INSTALL_CALL_RE.search(call_name):
                row_count += 1
            if _RECOVERY_CALL_RE.search(leaf):
                row_count += 1
            if _UI_CALL_RE.search(leaf) and leaf.casefold() not in {"open", "close"}:
                row_count += 1
            if _PLUGIN_CALL_RE.search(call_name):
                row_count += 1
            elif _DYNAMIC_CALL_RE.search(call_name):
                row_count += 1
            if leaf.casefold() in {"error", "exit", "abort", "fail"}:
                row_count += 1
        if isinstance(node, ast.Raise):
            row_count += 1
        if isinstance(node, ast.ExceptHandler):
            row_count += 1
    row_count += len(_surface_empty_or_placeholder_nodes(tree, source_text))
    # A later whole-boundary call-graph pass may add one observation for every
    # function that has no resolved local incoming edge.  Count every function
    # as a conservative upper bound so a shard can never overflow after that
    # pass merely because reachability was under-estimated.
    row_count += sum(1 for kind, _symbol, _node in _surface_node_specs(
        tree,
        module_symbol=relative[:-3].replace("/", "."),
    ) if kind == "function")
    return row_count, source_fingerprint, findings


def plan_implementation_surface_shards(
    root: str | Path,
    *,
    max_rows: int = _SURFACE_MAX_ROWS,
) -> dict[str, Any]:
    """Plan a complete source partition whose every child stays row-bounded.

    The planner probes one source file at a time, then greedily packs those
    observed row counts into deterministic shards.  It never fabricates an
    estimate from file size or model/test names.  A source file that cannot fit
    within the hard per-shard bound remains an explicit blocker; callers must
    refine the native parser boundary instead of silently truncating it.
    """

    bounded_root = Path(root).resolve()
    if not bounded_root.is_dir():
        raise PublicBehaviorSurfaceAuditError(
            f"implementation surface root is not a directory: {bounded_root}"
        )
    if not isinstance(max_rows, int) or max_rows < 1 or max_rows > _SURFACE_MAX_ROWS:
        raise PublicBehaviorSurfaceAuditError(
            f"max_rows must be between 1 and {_SURFACE_MAX_ROWS}"
        )
    candidates = _surface_candidate_files(bounded_root)
    findings: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for path in candidates:
        relative = _surface_relative(bounded_root, path)
        row_count, source_fingerprint, probe_findings = _surface_source_row_upper_bound(
            bounded_root,
            path,
        )
        for finding in probe_findings:
            findings.append(
                {
                    **finding,
                    "source_path": finding.get("source_path", relative),
                    "code": f"surface_shard_probe_{finding.get('code', 'invalid')}",
                }
            )
        source_bytes = path.stat().st_size if path.is_file() else 0
        if row_count > max_rows:
            findings.append(
                {
                    "code": "surface_shard_source_row_budget_exceeded",
                    "severity": "blocker",
                    "source_path": relative,
                    "message": (
                        f"one source file produces {row_count} surfaces, greater "
                        f"than the per-shard maximum of {max_rows}"
                    ),
                }
            )
        if source_bytes > _SURFACE_MAX_SOURCE_BYTES:
            findings.append(
                {
                    "code": "surface_shard_source_byte_budget_exceeded",
                    "severity": "blocker",
                    "source_path": relative,
                    "message": (
                        f"one source file is {source_bytes} bytes, greater than "
                        f"the per-shard byte maximum of {_SURFACE_MAX_SOURCE_BYTES}"
                    ),
                }
            )
        entries.append(
            {
                "source_path": relative,
                "source_fingerprint": source_fingerprint,
                "surface_count": row_count,
                "source_bytes": source_bytes,
            }
        )

    shards: list[dict[str, Any]] = []
    current_paths: list[str] = []
    current_count = 0
    current_bytes = 0

    def flush() -> None:
        nonlocal current_paths, current_count, current_bytes
        if not current_paths:
            return
        shard_index = len(shards)
        shards.append(
            {
                "shard_id": f"implementation-surface-{shard_index:04d}",
                "source_paths": list(current_paths),
                "estimated_surface_count": current_count,
                "source_file_count": len(current_paths),
                "source_bytes": current_bytes,
            }
        )
        current_paths = []
        current_count = 0
        current_bytes = 0

    for entry in entries:
        count = int(entry["surface_count"])
        source_bytes = int(entry["source_bytes"])
        if count > max_rows or source_bytes > _SURFACE_MAX_SOURCE_BYTES:
            continue
        would_overflow = (
            current_paths
            and (
                current_count + count > max_rows
                or len(current_paths) + 1 > _SURFACE_MAX_FILES
                or current_bytes + source_bytes > _SURFACE_MAX_SOURCE_BYTES
            )
        )
        if would_overflow:
            flush()
        current_paths.append(str(entry["source_path"]))
        current_count += count
        current_bytes += source_bytes
    flush()

    assigned_paths = {
        source_path
        for shard in shards
        for source_path in shard["source_paths"]
    }
    unassigned_paths = sorted(
        set(_surface_relative_paths(bounded_root, candidates)) - assigned_paths
    )
    if unassigned_paths:
        findings.append(
            {
                "code": "surface_shard_source_unassigned",
                "severity": "blocker",
                "message": "one or more current production sources could not be assigned to a shard",
                "source_paths": unassigned_paths,
            }
        )
    if not candidates:
        findings.append(
            {
                "code": "surface_shard_no_production_sources",
                "severity": "blocker",
                "message": "the current production boundary contains no source files",
            }
        )

    payload = {
        "schema_version": IMPLEMENTATION_SURFACE_SHARD_PLAN_SCHEMA,
        "claim_boundary": (
            "Complete production implementation-surface partition plan; "
            "semantic intent/model/test closure is not inferred."
        ),
        "max_rows": max_rows,
        "source_paths": _surface_relative_paths(bounded_root, candidates),
        "source_count": len(candidates),
        "entries": sorted(entries, key=lambda row: row["source_path"]),
        "shards": shards,
        "unassigned_source_paths": unassigned_paths,
        "findings": sorted(
            findings,
            key=lambda row: (
                row.get("source_path", ""),
                row.get("code", ""),
                row.get("message", ""),
            ),
        ),
    }
    return {
        **payload,
        "status": "blocked"
        if any(row.get("severity") == "blocker" for row in findings)
        else "planned",
        "plan_fingerprint": _surface_hash(payload),
    }


def discover_implementation_surface_shard(
    root: str | Path,
    plan: Mapping[str, Any],
    shard_id: str,
) -> dict[str, Any]:
    """Execute exactly one shard from a frozen plan and bind its identity."""

    if plan.get("schema_version") != IMPLEMENTATION_SURFACE_SHARD_PLAN_SCHEMA:
        raise PublicBehaviorSurfaceAuditError("shard plan schema is not current")
    shard = next(
        (
            row
            for row in plan.get("shards", ())
            if isinstance(row, Mapping) and row.get("shard_id") == shard_id
        ),
        None,
    )
    if shard is None:
        raise PublicBehaviorSurfaceAuditError(
            f"shard id is not present in the supplied plan: {shard_id}"
        )
    result = discover_implementation_behavior_surfaces(
        root,
        source_paths=tuple(shard.get("source_paths", ())),
        shard_id=shard_id,
    )
    result["shard_plan_fingerprint"] = plan.get("plan_fingerprint", "")
    result["shard_expected_surface_count"] = shard.get("estimated_surface_count")
    try:
        max_rows = int(plan.get("max_rows", _SURFACE_MAX_ROWS))
    except (TypeError, ValueError):
        max_rows = _SURFACE_MAX_ROWS
    if result.get("surface_count", 0) > max_rows:
        result.setdefault("findings", []).append(
            {
                "code": "surface_shard_row_budget_exceeded",
                "severity": "blocker",
                "shard_id": shard_id,
                "message": "executed shard exceeded the frozen plan row bound",
            }
        )
        result["status"] = "blocked"
    return result


def merge_implementation_surface_shards(
    root: str | Path,
    plan: Mapping[str, Any],
    shards: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Verify and merge a complete current shard set.

    This is intentionally a verifier, not a repairer: missing, duplicate,
    stale, foreign, over-budget, or overlapping shards remain visible blockers.
    Source hashes and row source fingerprints are recomputed from disk before
    the merged observation is accepted.
    """

    bounded_root = Path(root).resolve()
    findings: list[dict[str, Any]] = []
    plan_findings = plan.get("findings", ())
    if isinstance(plan_findings, list):
        findings.extend(
            row for row in plan_findings if isinstance(row, Mapping)
        )
    if plan.get("status") != "planned":
        findings.append(
            {
                "code": "surface_shard_plan_not_current",
                "severity": "blocker",
                "message": "the supplied shard plan is not a terminal planned artifact",
            }
        )
    if plan.get("schema_version") != IMPLEMENTATION_SURFACE_SHARD_PLAN_SCHEMA:
        findings.append(
            {
                "code": "surface_shard_plan_invalid",
                "severity": "blocker",
                "message": "shard plan schema is not current",
            }
        )
    try:
        max_rows = int(plan.get("max_rows", _SURFACE_MAX_ROWS))
    except (TypeError, ValueError):
        max_rows = _SURFACE_MAX_ROWS
        findings.append(
            {
                "code": "surface_shard_plan_invalid",
                "severity": "blocker",
                "message": "shard plan max_rows is not an integer",
            }
        )
    if max_rows < 1 or max_rows > _SURFACE_MAX_ROWS:
        findings.append(
            {
                "code": "surface_shard_plan_invalid",
                "severity": "blocker",
                "message": f"shard plan max_rows must be between 1 and {_SURFACE_MAX_ROWS}",
            }
        )
    expected_shards = plan.get("shards")
    if not isinstance(expected_shards, list):
        expected_shards = []
        findings.append(
            {
                "code": "surface_shard_plan_shards_missing",
                "severity": "blocker",
                "message": "shard plan must contain a shards array",
            }
        )
    expected_by_id: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(expected_shards):
        if not isinstance(row, Mapping) or not str(row.get("shard_id", "")).strip():
            findings.append(
                {
                    "code": "surface_shard_plan_row_invalid",
                    "severity": "blocker",
                    "message": f"planned shard row {index} has no valid shard_id",
                }
            )
            continue
        shard_id = str(row["shard_id"])
        if shard_id in expected_by_id:
            findings.append(
                {
                    "code": "surface_shard_plan_duplicate_id",
                    "severity": "blocker",
                    "shard_id": shard_id,
                    "message": "shard plan contains duplicate shard ids",
                }
            )
            continue
        expected_by_id[shard_id] = row
    actual_by_id: dict[str, Mapping[str, Any]] = {}
    for index, shard in enumerate(shards):
        if not isinstance(shard, Mapping):
            findings.append(
                {
                    "code": "surface_shard_invalid",
                    "severity": "blocker",
                    "message": f"shard {index} is not an object",
                }
            )
            continue
        shard_id = str(shard.get("shard_id", "")).strip()
        if not shard_id:
            findings.append(
                {
                    "code": "surface_shard_id_missing",
                    "severity": "blocker",
                    "message": f"shard {index} has no shard_id",
                }
            )
            continue
        if shard_id in actual_by_id:
            findings.append(
                {
                    "code": "surface_shard_duplicate_id",
                    "severity": "blocker",
                    "shard_id": shard_id,
                    "message": "the supplied shard set contains duplicate shard ids",
                }
            )
            continue
        actual_by_id[shard_id] = shard

    for shard_id in sorted(set(expected_by_id) - set(actual_by_id)):
        findings.append(
            {
                "code": "surface_shard_missing",
                "severity": "blocker",
                "shard_id": shard_id,
                "message": "the planned shard was not supplied",
            }
        )
    for shard_id in sorted(set(actual_by_id) - set(expected_by_id)):
        findings.append(
            {
                "code": "surface_shard_unexpected",
                "severity": "blocker",
                "shard_id": shard_id,
                "message": "the supplied shard is not part of the current plan",
            }
        )

    expected_paths = {
        str(path)
        for path in plan.get("source_paths", ())
        if isinstance(path, str)
    }
    current_paths = set(_surface_relative_paths(bounded_root, _surface_candidate_files(bounded_root)))
    if expected_paths != current_paths:
        findings.append(
            {
                "code": "surface_shard_plan_stale",
                "severity": "blocker",
                "message": "current production source paths differ from the shard plan",
                "planned_only": sorted(expected_paths - current_paths),
                "current_only": sorted(current_paths - expected_paths),
            }
        )

    source_owner: dict[str, str] = {}
    merged_rows: dict[str, Mapping[str, Any]] = {}
    source_identities: dict[str, dict[str, Any]] = {}
    merged_import_bindings: dict[str, dict[str, tuple[str, ...]]] = {}
    merged_scope_contexts: dict[str, Mapping[str, Any]] = {}
    # Keep the child call-graph observations as the authoritative list of
    # observed call sites.  Surface rows intentionally do not duplicate
    # module-body facts, so reconstructing calls from ``row["observed"]``
    # here would silently drop top-level/module edges during merge.
    observed_call_graph: list[dict[str, Any]] = []
    merged_unbound_surface_ids: set[str] = set()
    merged_unbound_rows_by_original: dict[str, Mapping[str, Any]] = {}
    for shard_id in sorted(actual_by_id):
        shard = actual_by_id[shard_id]
        expected = expected_by_id.get(shard_id)
        if shard.get("shard_plan_fingerprint") != plan.get("plan_fingerprint"):
            findings.append(
                {
                    "code": "surface_shard_plan_fingerprint_mismatch",
                    "severity": "blocker",
                    "shard_id": shard_id,
                    "message": "shard was not produced from the frozen shard plan",
                }
            )
        declared_paths = {
            str(path)
            for path in shard.get("source_paths", ())
            if isinstance(path, str)
        }
        if expected is not None:
            expected_paths_for_shard = {
                str(path)
                for path in expected.get("source_paths", ())
                if isinstance(path, str)
            }
            if declared_paths != expected_paths_for_shard:
                findings.append(
                    {
                        "code": "surface_shard_source_partition_mismatch",
                        "severity": "blocker",
                        "shard_id": shard_id,
                        "message": "shard source paths differ from the frozen plan",
                    }
                )
        for source_path in sorted(declared_paths):
            if source_path in source_owner:
                findings.append(
                    {
                        "code": "surface_shard_source_overlap",
                        "severity": "blocker",
                        "source_path": source_path,
                        "shard_id": shard_id,
                        "message": f"source path is already owned by shard {source_owner[source_path]}",
                    }
                )
            else:
                source_owner[source_path] = shard_id
            source_file = (bounded_root / source_path).resolve()
            try:
                source_file.relative_to(bounded_root)
                current_fingerprint = _sha256_file(source_file)
            except (OSError, ValueError):
                current_fingerprint = ""
            if not current_fingerprint:
                findings.append(
                    {
                        "code": "surface_shard_source_missing",
                        "severity": "blocker",
                        "source_path": source_path,
                        "shard_id": shard_id,
                        "message": "shard source path is missing or escapes the root",
                    }
                )
                continue
            source_identities[source_path] = {
                "source_path": source_path,
                "source_fingerprint": current_fingerprint,
            }
            if source_file.suffix.casefold() == ".py":
                try:
                    source_tree = ast.parse(
                        source_file.read_text(encoding="utf-8"),
                        filename=source_path,
                    )
                except (OSError, UnicodeError, SyntaxError) as exc:
                    findings.append(
                        {
                            "code": "surface_shard_import_parse_failure",
                            "severity": "blocker",
                            "source_path": source_path,
                            "shard_id": shard_id,
                            "message": str(exc),
                        }
                    )
                else:
                    merged_import_bindings[source_path] = _surface_import_bindings(
                        source_path,
                        source_tree,
                    )
                    module_symbol = (
                        source_path[:-3].replace("/", ".")
                        if source_path.endswith(".py")
                        else source_path
                    )
                    for context in _surface_scope_contexts(
                        source_tree,
                        relative_path=source_path,
                        module_symbol=module_symbol,
                    ).values():
                        surface_id = str(context.get("surface_id", ""))
                        if surface_id:
                            merged_scope_contexts[surface_id] = context
        declared_identities = shard.get("source_identities", ())
        if not isinstance(declared_identities, list):
            findings.append(
                {
                    "code": "surface_shard_source_identities_missing",
                    "severity": "blocker",
                    "shard_id": shard_id,
                    "message": "shard must carry source identities for every declared path",
                }
            )
        else:
            identity_by_path = {
                str(row.get("source_path", "")): row
                for row in declared_identities
                if isinstance(row, Mapping)
            }
            if set(identity_by_path) != declared_paths:
                findings.append(
                    {
                        "code": "surface_shard_source_identity_conservation_failed",
                        "severity": "blocker",
                        "shard_id": shard_id,
                        "message": "shard source identities do not conserve its source paths",
                    }
                )
            for source_path, identity in identity_by_path.items():
                current_identity = source_identities.get(source_path, {})
                if identity.get("source_fingerprint") != current_identity.get(
                    "source_fingerprint"
                ):
                    findings.append(
                        {
                            "code": "surface_shard_source_identity_stale",
                            "severity": "blocker",
                            "source_path": source_path,
                            "shard_id": shard_id,
                            "message": "shard source identity does not match the current file",
                        }
                    )
        shard_rows = shard.get("surfaces", ())
        if not isinstance(shard_rows, list):
            findings.append(
                {
                    "code": "surface_shard_surfaces_missing",
                    "severity": "blocker",
                    "shard_id": shard_id,
                    "message": "shard surfaces must be an array",
                }
            )
            shard_rows = []
        if len(shard_rows) > max_rows:
            findings.append(
                {
                    "code": "surface_shard_row_budget_exceeded",
                    "severity": "blocker",
                    "shard_id": shard_id,
                    "message": f"shard contains more than {max_rows} surfaces",
                }
            )
        for row in shard_rows:
            if not isinstance(row, Mapping):
                findings.append(
                    {
                        "code": "surface_shard_row_invalid",
                        "severity": "blocker",
                        "shard_id": shard_id,
                        "message": "shard surface row is not an object",
                    }
                )
                continue
            surface_id = str(row.get("surface_id", "")).strip()
            source_path = str(row.get("source_path", "")).replace("\\", "/")
            if not surface_id:
                findings.append(
                    {
                        "code": "surface_shard_surface_id_missing",
                        "severity": "blocker",
                        "shard_id": shard_id,
                        "message": "shard surface row has no surface_id",
                    }
                )
                continue
            if source_path not in declared_paths:
                findings.append(
                    {
                        "code": "surface_shard_row_foreign_source",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "shard_id": shard_id,
                        "message": "surface row belongs to a source outside its shard",
                    }
                )
            current_fingerprint = source_identities.get(source_path, {}).get(
                "source_fingerprint"
            )
            if current_fingerprint and row.get("source_fingerprint") != current_fingerprint:
                findings.append(
                    {
                        "code": "surface_shard_row_source_stale",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "shard_id": shard_id,
                        "message": "surface row source fingerprint is not current",
                    }
                )
            row_without_fingerprint = {
                key: value
                for key, value in row.items()
                if key != "surface_fingerprint"
            }
            if row.get("surface_fingerprint") != _surface_hash(
                row_without_fingerprint
            ):
                findings.append(
                    {
                        "code": "surface_shard_surface_fingerprint_stale",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "shard_id": shard_id,
                        "message": "surface row fingerprint does not match its canonical content",
                    }
                )
            if surface_id in merged_rows:
                findings.append(
                    {
                        "code": "surface_shard_surface_duplicate",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "message": "surface id appears in more than one shard",
                    }
                )
            else:
                merged_rows[surface_id] = row
            if row.get("surface_kind") == "unreachable_or_unbound":
                observed = row.get("observed", {})
                original_surface_id = (
                    str(observed.get("original_surface_id", "")).strip()
                    if isinstance(observed, Mapping)
                    else ""
                )
                if original_surface_id:
                    prior_unbound = merged_unbound_rows_by_original.get(
                        original_surface_id
                    )
                    if prior_unbound is not None and dict(prior_unbound) != dict(row):
                        findings.append(
                            {
                                "code": "surface_shard_unbound_observation_duplicate",
                                "severity": "blocker",
                                "surface_id": surface_id,
                                "message": "multiple current unbound rows claim the same original surface",
                            }
                        )
                    else:
                        merged_unbound_rows_by_original[original_surface_id] = row

        shard_findings = shard.get("findings", ())
        if isinstance(shard_findings, list):
            findings.extend(
                row
                for row in shard_findings
                if isinstance(row, Mapping)
            )
        shard_call_graph = shard.get("call_graph", ())
        if not isinstance(shard_call_graph, list):
            findings.append(
                {
                    "code": "surface_shard_call_graph_missing",
                    "severity": "blocker",
                    "shard_id": shard_id,
                    "message": "each shard must carry its source-only call graph observation",
                }
            )
        else:
            shard_edges = [
                row for row in shard_call_graph if isinstance(row, Mapping)
            ]
            observed_call_graph.extend(shard_edges)
            declared_contracts = shard.get("external_contracts")
            expected_contracts = _surface_external_contracts(shard_edges)
            if declared_contracts != expected_contracts:
                findings.append(
                    {
                        "code": "surface_shard_external_contract_conservation_failed",
                        "severity": "blocker",
                        "shard_id": shard_id,
                        "message": (
                            "shard external-contract rows must exactly conserve "
                            "its resolved external-contract call edges"
                        ),
                    }
                )
        shard_unbound = shard.get("unbound_surface_ids", ())
        if isinstance(shard_unbound, list):
            merged_unbound_surface_ids.update(
                str(surface_id) for surface_id in shard_unbound
            )

    if set(source_owner) != expected_paths:
        findings.append(
            {
                "code": "surface_shard_source_conservation_failed",
                "severity": "blocker",
                "message": "the supplied shards do not conserve the complete planned source boundary",
                "missing": sorted(expected_paths - set(source_owner)),
                "unexpected": sorted(set(source_owner) - expected_paths),
            }
        )

    # Recompute reachability over the complete merged function inventory.
    # Local shard graphs are retained only as child observations: resolving a
    # call inside one shard cannot prove or disprove a target defined in a
    # different shard.
    base_rows = {
        surface_id: row
        for surface_id, row in merged_rows.items()
        if row.get("surface_kind") != "unreachable_or_unbound"
    }
    graph_rows = [
        row
        for row in base_rows.values()
        if row.get("surface_kind") in {"module", "function", "class"}
    ]
    function_rows = [
        row for row in graph_rows if row.get("surface_kind") == "function"
    ]
    graph_by_leaf: dict[str, list[Mapping[str, Any]]] = {}
    for row in graph_rows:
        leaf = str(row.get("symbol", "")).rsplit(".", 1)[-1]
        graph_by_leaf.setdefault(leaf, []).append(row)
    external_names = {
        str(row.get("observed", {}).get("export_name", "")).rsplit(".", 1)[-1]
        for row in base_rows.values()
        if row.get("surface_kind") in {"export", "api"}
        and str(row.get("observed", {}).get("export_name", "")).strip()
    }
    external_names.update(
        str(row.get("observed", {}).get("api_name", "")).rsplit(".", 1)[-1]
        for row in base_rows.values()
        if row.get("surface_kind") == "api"
        and str(row.get("observed", {}).get("api_name", "")).strip()
    )
    for row in base_rows.values():
        if row.get("surface_kind") != "cli_entrypoint":
            continue
        target = row.get("observed", {}).get("target", "")
        if isinstance(target, str) and ":" in target:
            external_names.add(target.rsplit(":", 1)[-1].rsplit(".", 1)[-1])
    call_observations_by_caller: dict[str, list[Mapping[str, Any]]] = {}
    for edge in observed_call_graph:
        caller_surface_id = str(edge.get("caller_surface_id", "")).strip()
        callee_name = str(edge.get("callee_name", "")).strip()
        if caller_surface_id and callee_name:
            call_observations_by_caller.setdefault(caller_surface_id, []).append(edge)

    global_incoming: dict[str, set[str]] = {
        str(row.get("surface_id")): set() for row in graph_rows
    }
    global_call_graph: list[dict[str, Any]] = []
    for row in graph_rows:
        # Use the child observation for every graph owner, including module
        # and class bodies.  The previous implementation read only the
        # surface-row ``observed.calls`` field, which is intentionally empty
        # for module rows and caused full-vs-merged call-graph loss.
        call_observations = call_observations_by_caller.get(
            str(row.get("surface_id", "")), ()
        )
        for observed_call in call_observations:
            call_name = str(observed_call.get("callee_name", "")).strip()
            if not call_name:
                continue
            edge_resolution = _surface_resolve_call_edge(
                str(call_name),
                str(row.get("surface_id", "")),
                str(row.get("symbol", "")),
                graph_by_leaf,
                str(row.get("source_path", "")),
                merged_import_bindings.get(str(row.get("source_path", "")), {}),
                caller_context=merged_scope_contexts.get(
                    str(row.get("surface_id", ""))
                ),
                candidate_contexts=merged_scope_contexts,
            )
            resolved_ids = list(edge_resolution["resolved_surface_ids"])
            for resolved_id in resolved_ids:
                global_incoming.setdefault(resolved_id, set()).add(
                    str(row.get("surface_id"))
                )
            global_call_graph.append(
                {
                    "caller_surface_id": str(row.get("surface_id")),
                    "caller_source_ref": observed_call.get(
                        "caller_source_ref", row.get("source_ref", "")
                    ),
                    "callee_name": call_name,
                    **edge_resolution,
                }
            )

    merged_rows = dict(base_rows)
    merged_unbound_surface_ids = set()
    for row in function_rows:
        surface_id = str(row.get("surface_id"))
        symbol_leaf = str(row.get("symbol", "")).rsplit(".", 1)[-1]
        if symbol_leaf.startswith("_") or symbol_leaf in external_names:
            continue
        if global_incoming.get(surface_id):
            continue
        unbound_row = merged_unbound_rows_by_original.get(surface_id)
        if unbound_row is None:
            findings.append(
                {
                    "code": "surface_shard_unbound_observation_missing",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": "a globally unbound function has no child unbound observation to conserve",
                }
            )
            continue
        unbound_id = str(unbound_row.get("surface_id", "")).strip()
        if not unbound_id:
            findings.append(
                {
                    "code": "surface_shard_unbound_observation_invalid",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": "child unbound observation has no current surface id",
                }
            )
            continue
        unbound_row = dict(unbound_row)
        merged_rows[unbound_id] = unbound_row
        merged_unbound_surface_ids.add(unbound_id)

    ordered_rows = tuple(
        sorted(merged_rows.values(), key=lambda row: str(row.get("surface_id", "")))
    )
    ordered_sources = tuple(
        sorted(source_identities.values(), key=lambda row: row["source_path"])
    )
    merged_surface_ids = set(merged_rows)
    for edge in global_call_graph:
        caller_surface_id = str(edge.get("caller_surface_id", ""))
        if caller_surface_id not in merged_surface_ids:
            findings.append(
                {
                    "code": "surface_shard_call_graph_orphan_caller",
                    "severity": "blocker",
                    "surface_id": caller_surface_id,
                    "message": "call graph caller is not present in the merged surface inventory",
                }
            )
        for callee_surface_id in edge.get("resolved_surface_ids", ()):
            if str(callee_surface_id) not in merged_surface_ids:
                findings.append(
                    {
                        "code": "surface_shard_call_graph_orphan_callee",
                        "severity": "blocker",
                        "surface_id": str(callee_surface_id),
                        "message": "call graph callee is not present in the merged surface inventory",
                    }
                )
    merged_call_graph = sorted(
        global_call_graph,
        key=lambda row: (
            str(row.get("caller_surface_id", "")),
            str(row.get("callee_name", "")),
            str(row.get("resolution", "")),
        ),
    )
    merged_payload = {
        "schema_version": IMPLEMENTATION_SURFACE_AUDIT_SCHEMA,
        "shard_id": "merged",
        "source_paths": sorted(expected_paths),
        "shard_plan_fingerprint": plan.get("plan_fingerprint", ""),
        "shard_ids": sorted(expected_by_id),
        "source_identities": [
            _source_identity_content_projection(row) for row in ordered_sources
        ],
        "surfaces": ordered_rows,
        "call_graph": merged_call_graph,
        "external_contracts": _surface_external_contracts(merged_call_graph),
        "unbound_surface_ids": sorted(merged_unbound_surface_ids),
    }
    # A merged observation is complete only when the source boundary, rows,
    # call-site edges, and every target-boundary identity are current and
    # conserved.  Dynamic/external expressions and finite dispatch sets are
    # closed by _surface_resolve_call_edge, so any remaining finding is
    # structural and must block directly.
    non_typed_blocker = any(row.get("severity") == "blocker" for row in findings)
    return {
        "schema_version": IMPLEMENTATION_SURFACE_AUDIT_SCHEMA,
        "shard_id": "merged",
        "source_paths": sorted(expected_paths),
        "shard_plan_fingerprint": plan.get("plan_fingerprint", ""),
        "shard_ids": sorted(expected_by_id),
        "status": "blocked" if non_typed_blocker else "passed",
        "claim_boundary": (
            "Merged static production implementation surfaces only; no intent, "
            "model, test execution, or runtime behavior is inferred."
        ),
        "source_identities": list(ordered_sources),
        "surfaces": list(ordered_rows),
        "surface_count": len(ordered_rows),
        "call_graph": merged_call_graph,
        "external_contracts": _surface_external_contracts(merged_call_graph),
        "unbound_surface_ids": sorted(merged_unbound_surface_ids),
        "findings": sorted(
            findings,
            key=lambda row: (
                row.get("source_path", ""),
                row.get("shard_id", ""),
                row.get("code", ""),
                row.get("message", ""),
            ),
        ),
        "discovery_fingerprint": _surface_hash(merged_payload),
    }


def _implementation_surface_candidate_class(surface_kind: str) -> str:
    """Map an observed parser kind to a review-only candidate bucket.

    These buckets are structural triage labels.  They are intentionally not
    the reverse-map dispositions and do not imply an intent, model owner, or
    test obligation.
    """

    return {
        "api": "public_api",
        "export": "public_api",
        "cli_command": "public_cli",
        "cli_entrypoint": "public_cli",
        "ui_like_action": "ui_like",
        "template": "template",
        "config": "configuration",
        "install": "installation",
        "effect": "effect",
        "error": "fault",
        "recovery": "recovery",
        "dynamic": "dynamic_boundary",
        "plugin": "plugin_boundary",
        "placeholder": "placeholder",
        "unreachable_or_unbound": "unbound_or_unreachable",
        "module": "implementation_code",
        "function": "implementation_code",
        "class": "implementation_code",
    }.get(str(surface_kind).strip(), "unclassified")


def _implementation_surface_candidate_reasons(
    row: Mapping[str, Any],
    *,
    dispatch_surface_ids: set[str],
    unbound_surface_ids: set[str],
) -> tuple[str, ...]:
    """Return deterministic structural reasons without inferring semantics."""

    surface_kind = str(row.get("surface_kind", "")).strip()
    surface_class = str(row.get("surface_class", "")).strip()
    reasons = [
        f"surface_kind:{surface_kind or 'missing'}",
        f"surface_class:{surface_class or 'missing'}",
    ]
    if surface_kind in {"api", "export", "cli_command", "cli_entrypoint"}:
        reasons.append("externally_declared_or_callable")
    if surface_kind == "ui_like_action":
        reasons.append("ui_like_action_observed")
    if surface_kind in {"config", "install", "effect", "recovery"}:
        reasons.append("state_or_lifecycle_surface")
    if surface_kind == "error":
        reasons.append("error_path_observed")
    if surface_kind in {"dynamic", "plugin"}:
        reasons.append("dynamic_or_plugin_boundary")
    if surface_kind == "placeholder":
        reasons.append("placeholder_marker_observed")
    if surface_kind == "unreachable_or_unbound":
        reasons.append("unreachable_or_unbound_observed")
    surface_id = str(row.get("surface_id", "")).strip()
    if surface_id in dispatch_surface_ids:
        reasons.append("finite_dispatch_candidate_reference")
    if surface_id in unbound_surface_ids:
        reasons.append("unbound_denominator_reference")
    return tuple(sorted(set(reasons)))


def _implementation_surface_candidate_row(
    row: Mapping[str, Any],
    *,
    dispatch_surface_ids: set[str],
    unbound_surface_ids: set[str],
) -> dict[str, Any]:
    """Project one source observation into a semantic-free candidate row."""

    surface_id = str(row.get("surface_id", "")).strip()
    surface_kind = str(row.get("surface_kind", "")).strip()
    return {
        "candidate_class": _implementation_surface_candidate_class(surface_kind),
        "candidate_reason_codes": list(
            _implementation_surface_candidate_reasons(
                row,
                dispatch_surface_ids=dispatch_surface_ids,
                unbound_surface_ids=unbound_surface_ids,
            )
        ),
        "review_group_id": str(row.get("review_group_id", "")).strip(),
        "review_granularity": str(row.get("review_granularity", "")).strip(),
        "source_fingerprint": str(row.get("source_fingerprint", "")).strip(),
        "source_path": str(row.get("source_path", "")).strip(),
        "source_ref": str(row.get("source_ref", "")).strip(),
        "surface_class": str(row.get("surface_class", "")).strip(),
        "surface_fingerprint": str(row.get("surface_fingerprint", "")).strip(),
        "surface_id": surface_id,
        "surface_kind": surface_kind,
    }


def classify_implementation_surface_candidates(
    discovery: Mapping[str, Any],
    *,
    plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a read-only candidate triage report from source observations.

    The report is deliberately *candidate-only*.  It preserves the complete
    observed denominator and labels each row by finite source kind/class
    buckets, but it never creates intent ids, model obligations, owners,
    tests, receipts, or dispositions.  A generated report therefore cannot
    license reverse closure or a broad DNA claim.
    """

    findings: list[dict[str, Any]] = []
    raw_rows = discovery.get("surfaces") if isinstance(discovery, Mapping) else None
    if not isinstance(raw_rows, list):
        findings.append(
            {
                "code": "implementation_surface_candidate_discovery_rows_invalid",
                "severity": "blocker",
                "message": "candidate classification requires a surfaces array",
            }
        )
        raw_rows = []

    observed_surface_ids: list[str] = []
    duplicate_discovery_ids: set[str] = set()
    seen_ids: set[str] = set()
    structural_kinds = set(IMPLEMENTATION_SURFACE_KINDS)
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, Mapping):
            findings.append(
                {
                    "code": "implementation_surface_candidate_row_invalid",
                    "severity": "blocker",
                    "row_index": index,
                    "message": "every candidate source observation must be an object row",
                }
            )
            continue
        surface_id = str(raw.get("surface_id", "")).strip()
        if not surface_id:
            findings.append(
                {
                    "code": "implementation_surface_candidate_surface_id_missing",
                    "severity": "blocker",
                    "row_index": index,
                    "message": "every candidate source observation needs a surface_id",
                }
            )
            continue
        observed_surface_ids.append(surface_id)
        if surface_id in seen_ids:
            duplicate_discovery_ids.add(surface_id)
            findings.append(
                {
                    "code": "implementation_surface_candidate_discovery_duplicate_id",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": "source discovery contains duplicate candidate surface ids",
                }
            )
        seen_ids.add(surface_id)
        surface_kind = str(raw.get("surface_kind", "")).strip()
        surface_class = str(raw.get("surface_class", "")).strip()
        if surface_kind not in structural_kinds:
            findings.append(
                {
                    "code": "implementation_surface_candidate_kind_unknown",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": f"source observation kind is not current: {surface_kind!r}",
                }
            )
        expected_class = _surface_class_for_kind(surface_kind)
        if not expected_class or surface_class != expected_class:
            findings.append(
                {
                    "code": "implementation_surface_candidate_class_mismatch",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": (
                        f"source observation class {surface_class!r} does not match "
                        f"kind {surface_kind!r} ({expected_class or 'unknown'!r})"
                    ),
                }
            )
        for field_name in (
            "source_path",
            "source_ref",
            "source_fingerprint",
            "surface_fingerprint",
            "review_group_id",
        ):
            value = str(raw.get(field_name, "")).strip()
            if not value:
                findings.append(
                    {
                        "code": "implementation_surface_candidate_identity_missing",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "field": field_name,
                        "message": f"candidate source observation needs {field_name}",
                    }
                )
        for field_name in ("source_fingerprint", "surface_fingerprint"):
            value = str(raw.get(field_name, "")).strip()
            if value and not _CURRENT_IDENTITY_FINGERPRINT_RE.fullmatch(value):
                findings.append(
                    {
                        "code": "implementation_surface_candidate_identity_invalid",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "field": field_name,
                        "message": f"candidate {field_name} is not canonical sha256",
                    }
                )
        if str(raw.get("review_granularity", "")).strip() not in {"surface", "component"}:
            findings.append(
                {
                    "code": "implementation_surface_candidate_review_granularity_invalid",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": "candidate source observation needs surface or component review granularity",
                }
            )

    discovered_ids = set(observed_surface_ids)
    raw_unbound = discovery.get("unbound_surface_ids", ())
    if not isinstance(raw_unbound, list):
        findings.append(
            {
                "code": "implementation_surface_candidate_unbound_ids_invalid",
                "severity": "blocker",
                "message": "discovery unbound_surface_ids must be an array",
            }
        )
        raw_unbound = []
    unbound_ids = [str(value).strip() for value in raw_unbound]
    if len(unbound_ids) != len(set(unbound_ids)):
        findings.append(
            {
                "code": "implementation_surface_candidate_unbound_ids_duplicate",
                "severity": "blocker",
                "message": "discovery unbound_surface_ids must be unique",
            }
        )
    expected_unbound_ids = sorted(
        str(row.get("surface_id", "")).strip()
        for row in raw_rows
        if isinstance(row, Mapping)
        and str(row.get("surface_kind", "")).strip() == "unreachable_or_unbound"
        and str(row.get("surface_id", "")).strip()
    )
    if sorted(set(unbound_ids)) != expected_unbound_ids:
        findings.append(
            {
                "code": "implementation_surface_candidate_unbound_conservation_failed",
                "severity": "blocker",
                "message": "discovery unbound ids do not match candidate observations",
                "expected": expected_unbound_ids,
                "actual": sorted(set(unbound_ids)),
            }
        )
    unbound_surface_ids = set(unbound_ids)

    dispatch_surface_ids: set[str] = set()
    source_findings = discovery.get("findings", ())
    if not isinstance(source_findings, list):
        source_findings = []
    raw_call_graph = discovery.get("call_graph", ())
    if not isinstance(raw_call_graph, list):
        raw_call_graph = []
    for edge in raw_call_graph:
        if not isinstance(edge, Mapping):
            continue
        if str(edge.get("resolution", "")).strip() != "resolved_static_dispatch":
            continue
        references: list[str] = []
        caller_surface_id = str(edge.get("caller_surface_id", "")).strip()
        if caller_surface_id:
            references.append(caller_surface_id)
        candidate_ids = edge.get("resolved_surface_ids", ())
        if isinstance(candidate_ids, list):
            references.extend(str(value).strip() for value in candidate_ids if str(value).strip())
        for surface_id in references:
            if surface_id not in discovered_ids:
                findings.append(
                    {
                        "code": "implementation_surface_candidate_dispatch_reference_orphan",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "message": "finite dispatch edge references an unknown current source surface",
                    }
                )
            else:
                dispatch_surface_ids.add(surface_id)

    plan_fingerprint = str((plan or {}).get("plan_fingerprint", "")).strip()
    shard_plan_fingerprint = str(discovery.get("shard_plan_fingerprint", "")).strip()
    if plan_fingerprint and shard_plan_fingerprint and plan_fingerprint != shard_plan_fingerprint:
        findings.append(
            {
                "code": "implementation_surface_candidate_plan_fingerprint_mismatch",
                "severity": "blocker",
                "message": "candidate report plan fingerprint does not match the discovery shard plan",
            }
        )

    # Keep the candidate projection independent of any semantic map.  It only
    # copies source identity and finite structural labels.
    candidate_rows = [
        _implementation_surface_candidate_row(
            raw,
            dispatch_surface_ids=dispatch_surface_ids,
            unbound_surface_ids=unbound_surface_ids,
        )
        for raw in raw_rows
        if isinstance(raw, Mapping) and str(raw.get("surface_id", "")).strip()
    ]
    candidate_rows.sort(key=lambda row: row["surface_id"])
    candidate_ids = [str(row["surface_id"]) for row in candidate_rows]
    candidate_duplicate_ids = sorted(
        surface_id
        for surface_id in set(candidate_ids)
        if candidate_ids.count(surface_id) > 1
    )
    missing_surface_ids = sorted(discovered_ids - set(candidate_ids))
    unexpected_surface_ids = sorted(set(candidate_ids) - discovered_ids)
    conservation_status = (
        "passed"
        if not duplicate_discovery_ids
        and not candidate_duplicate_ids
        and not missing_surface_ids
        and not unexpected_surface_ids
        and len(candidate_rows) == len(raw_rows)
        else "blocked"
    )
    candidate_class_counts: dict[str, int] = {}
    candidate_reason_counts: dict[str, int] = {}
    for row in candidate_rows:
        candidate_class = str(row["candidate_class"])
        candidate_class_counts[candidate_class] = candidate_class_counts.get(candidate_class, 0) + 1
        for reason in row["candidate_reason_codes"]:
            candidate_reason_counts[reason] = candidate_reason_counts.get(reason, 0) + 1

    source_finding_counts: dict[str, int] = {}
    for source_finding in source_findings:
        if isinstance(source_finding, Mapping):
            code = str(source_finding.get("code", "")).strip()
            if code:
                source_finding_counts[code] = source_finding_counts.get(code, 0) + 1

    result: dict[str, Any] = {
        "schema_version": IMPLEMENTATION_SURFACE_CANDIDATE_REPORT_SCHEMA,
        "status": "candidate_only"
        if conservation_status == "passed"
        and not any(item.get("severity") == "blocker" for item in findings)
        else "blocked",
        "candidate_only": True,
        "semantic_authority": "none",
        "reverse_closure_complete": False,
        "claim_boundary": (
            "Source-derived implementation-surface candidate triage only. "
            "No intent, model obligation, owner, test, terminal receipt, or "
            "disposition is inferred or licensed."
        ),
        "discovery_schema_version": str(discovery.get("schema_version", "")),
        "source_discovery_status": str(discovery.get("status", "")),
        "discovery_fingerprint": str(discovery.get("discovery_fingerprint", "")).strip(),
        "plan_fingerprint": plan_fingerprint or shard_plan_fingerprint,
        "shard_ids": sorted(str(value) for value in discovery.get("shard_ids", ()) if str(value).strip()),
        "source_paths": sorted(str(value) for value in discovery.get("source_paths", ()) if str(value).strip()),
        "source_discovery_finding_counts": dict(sorted(source_finding_counts.items())),
        "dispatch_surface_ids": sorted(dispatch_surface_ids),
        "unbound_surface_ids": sorted(unbound_surface_ids),
        "candidate_surface_count": len(candidate_rows),
        "candidate_surface_ids": candidate_ids,
        "candidate_class_counts": dict(sorted(candidate_class_counts.items())),
        "candidate_reason_counts": dict(sorted(candidate_reason_counts.items())),
        "candidate_conservation": {
            "status": conservation_status,
            "discovery_surface_count": len(raw_rows),
            "discovery_unique_surface_count": len(discovered_ids),
            "candidate_surface_count": len(candidate_rows),
            "candidate_unique_surface_count": len(set(candidate_ids)),
            "missing_surface_ids": missing_surface_ids,
            "unexpected_surface_ids": unexpected_surface_ids,
            "duplicate_discovery_surface_ids": sorted(duplicate_discovery_ids),
            "duplicate_candidate_surface_ids": candidate_duplicate_ids,
        },
        "findings": sorted(
            findings,
            key=lambda item: (
                str(item.get("surface_id", "")),
                str(item.get("code", "")),
                str(item.get("message", "")),
            ),
        ),
        "candidates": candidate_rows,
    }
    result["evidence_fingerprint"] = _surface_hash(result)
    return result


_IMPLEMENTATION_SURFACE_CANDIDATE_FORBIDDEN_FIELDS = frozenset(
    {
        "intent_id",
        "model_owner_id",
        "model_obligation_id",
        "model_obligation_ids",
        "owner",
        "owner_id",
        "test_ref",
        "test_refs",
        "receipt_ref",
        "receipt_refs",
        "disposition",
        "proof_ref",
        "reason",
        "gap_reason",
        "not_applicable_reason",
    }
)


def validate_implementation_surface_candidate_report(
    report: Mapping[str, Any],
    discovery: Mapping[str, Any],
    *,
    plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a candidate report without treating it as semantic coverage."""

    findings: list[dict[str, Any]] = []
    if not isinstance(report, Mapping):
        findings.append(
            {
                "code": "implementation_surface_candidate_report_invalid",
                "severity": "blocker",
                "message": "candidate report must be an object",
            }
        )
        report = {}
    if report.get("schema_version") != IMPLEMENTATION_SURFACE_CANDIDATE_REPORT_SCHEMA:
        findings.append(
            {
                "code": "implementation_surface_candidate_report_schema_invalid",
                "severity": "blocker",
                "message": "candidate report schema is not current",
            }
        )
    if report.get("status") != "candidate_only":
        findings.append(
            {
                "code": "implementation_surface_candidate_report_status_invalid",
                "severity": "blocker",
                "message": "candidate report must remain candidate_only, never pass",
            }
        )
    if report.get("candidate_only") is not True or report.get("semantic_authority") != "none":
        findings.append(
            {
                "code": "implementation_surface_candidate_report_authority_invalid",
                "severity": "blocker",
                "message": "candidate report must declare candidate_only and semantic_authority=none",
            }
        )
    if report.get("reverse_closure_complete") is not False:
        findings.append(
            {
                "code": "implementation_surface_candidate_report_closure_invalid",
                "severity": "blocker",
                "message": "candidate report cannot claim reverse closure",
            }
        )

    expected = classify_implementation_surface_candidates(
        discovery,
        plan=plan
        or {
            "plan_fingerprint": str(report.get("plan_fingerprint", "")).strip()
        },
    )
    expected_ids = [str(value) for value in expected.get("candidate_surface_ids", ())]
    raw_candidates = report.get("candidates")
    if not isinstance(raw_candidates, list):
        findings.append(
            {
                "code": "implementation_surface_candidate_report_rows_invalid",
                "severity": "blocker",
                "message": "candidate report must contain a candidates array",
            }
        )
        raw_candidates = []
    actual_ids = [
        str(row.get("surface_id", "")).strip()
        for row in raw_candidates
        if isinstance(row, Mapping)
    ]
    expected_id_set = set(expected_ids)
    actual_id_set = set(actual_ids)
    duplicate_actual_ids = sorted(
        surface_id for surface_id in set(actual_ids) if actual_ids.count(surface_id) > 1
    )
    missing_ids = sorted(expected_id_set - actual_id_set)
    unexpected_ids = sorted(actual_id_set - expected_id_set)
    if duplicate_actual_ids or missing_ids or unexpected_ids or len(actual_ids) != len(expected_ids):
        findings.append(
            {
                "code": "implementation_surface_candidate_report_conservation_failed",
                "severity": "blocker",
                "message": "candidate report rows do not conserve the discovery denominator",
                "missing_surface_ids": missing_ids,
                "unexpected_surface_ids": unexpected_ids,
                "duplicate_surface_ids": duplicate_actual_ids,
            }
        )
    if report.get("candidate_surface_ids") != actual_ids:
        findings.append(
            {
                "code": "implementation_surface_candidate_report_id_projection_mismatch",
                "severity": "blocker",
                "message": "candidate_surface_ids must equal the ordered candidate rows",
            }
        )
    expected_rows_by_id = {
        str(row.get("surface_id")): row
        for row in expected.get("candidates", ())
        if isinstance(row, Mapping)
    }
    for index, raw in enumerate(raw_candidates):
        if not isinstance(raw, Mapping):
            findings.append(
                {
                    "code": "implementation_surface_candidate_report_row_invalid",
                    "severity": "blocker",
                    "row_index": index,
                    "message": "candidate report rows must be objects",
                }
            )
            continue
        forbidden = sorted(_IMPLEMENTATION_SURFACE_CANDIDATE_FORBIDDEN_FIELDS & set(raw))
        if forbidden:
            findings.append(
                {
                    "code": "implementation_surface_candidate_semantic_field_forbidden",
                    "severity": "blocker",
                    "surface_id": str(raw.get("surface_id", "")),
                    "fields": forbidden,
                    "message": "candidate rows cannot carry semantic bindings or dispositions",
                }
            )
        surface_id = str(raw.get("surface_id", "")).strip()
        expected_row = expected_rows_by_id.get(surface_id)
        if expected_row is None:
            continue
        if dict(raw) != dict(expected_row):
            findings.append(
                {
                    "code": "implementation_surface_candidate_row_mismatch",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": "candidate row does not match the independently recomputed source projection",
                }
            )

    if report.get("discovery_fingerprint") != expected.get("discovery_fingerprint"):
        findings.append(
            {
                "code": "implementation_surface_candidate_discovery_fingerprint_mismatch",
                "severity": "blocker",
                "message": "candidate report does not bind to the current discovery fingerprint",
            }
        )
    if report.get("candidate_conservation") != expected.get("candidate_conservation"):
        findings.append(
            {
                "code": "implementation_surface_candidate_conservation_projection_mismatch",
                "severity": "blocker",
                "message": "candidate conservation projection is not current",
            }
        )
    supplied_fingerprint = str(report.get("evidence_fingerprint", "")).strip()
    expected_fingerprint = _surface_hash(
        {key: value for key, value in report.items() if key != "evidence_fingerprint"}
    )
    if supplied_fingerprint != expected_fingerprint:
        findings.append(
            {
                "code": "implementation_surface_candidate_evidence_fingerprint_mismatch",
                "severity": "blocker",
                "message": "candidate report evidence fingerprint does not match its content",
            }
        )
    result: dict[str, Any] = {
        "schema_version": IMPLEMENTATION_SURFACE_CANDIDATE_REPORT_SCHEMA,
        "status": "passed" if not findings else "blocked",
        "candidate_only": True,
        "semantic_authority": "none",
        "reverse_closure_complete": False,
        "claim_boundary": (
            "Structural candidate-report validation only; this result does not "
            "license semantic reverse closure or a broad DNA claim."
        ),
        "validated_discovery_fingerprint": str(expected.get("discovery_fingerprint", "")),
        "validated_candidate_surface_count": len(expected_ids),
        "findings": sorted(
            findings,
            key=lambda item: (
                str(item.get("surface_id", "")),
                str(item.get("code", "")),
                str(item.get("message", "")),
            ),
        ),
    }
    result["evidence_fingerprint"] = _surface_hash(result)
    return result


def _validate_discovery_snapshot(
    root: Path,
    observed: Mapping[str, Any],
    *,
    currentness_profile: str = "full",
) -> list[dict[str, Any]]:
    """Re-verify a supplied source observation before using its denominator.

    ``audit_implementation_behavior_surface`` accepts a producer artifact so
    shard merges can be audited without rediscovering the whole tree.  That
    artifact is still an input, not an authority: source paths, source hashes,
    row hashes, call-graph shape, and the canonical discovery fingerprint are
    all checked against the current workspace.  A caller cannot make a stale
    or hand-authored ``status=passed`` snapshot green merely by pairing it
    with a matching map.
    """

    findings: list[dict[str, Any]] = []
    if currentness_profile not in IMPLEMENTATION_SURFACE_CURRENTNESS_PROFILES:
        findings.append(
            {
                "code": "implementation_surface_currentness_profile_invalid",
                "severity": "blocker",
                "message": (
                    "currentness_profile must be one of "
                    f"{IMPLEMENTATION_SURFACE_CURRENTNESS_PROFILES}"
                ),
            }
        )
        currentness_profile = "full"
    if observed.get("schema_version") != IMPLEMENTATION_SURFACE_AUDIT_SCHEMA:
        findings.append(
            {
                "code": "implementation_surface_discovery_schema_invalid",
                "severity": "blocker",
                "message": "implementation-surface discovery schema is not current",
            }
        )

    raw_source_paths = observed.get("source_paths")
    source_paths: list[str] = []
    if not isinstance(raw_source_paths, list):
        findings.append(
            {
                "code": "implementation_surface_discovery_source_paths_invalid",
                "severity": "blocker",
                "message": "implementation-surface discovery must carry a source_paths array",
            }
        )
    else:
        for index, raw_path in enumerate(raw_source_paths):
            if not isinstance(raw_path, str) or not raw_path.strip():
                findings.append(
                    {
                        "code": "implementation_surface_discovery_source_path_invalid",
                        "severity": "blocker",
                        "row_index": index,
                        "message": "discovery source paths must be non-empty strings",
                    }
                )
                continue
            normalized = raw_path.replace("\\", "/")
            candidate = (root / normalized).resolve()
            try:
                candidate.relative_to(root.resolve())
            except ValueError:
                findings.append(
                    {
                        "code": "implementation_surface_discovery_source_path_escape",
                        "severity": "blocker",
                        "source_path": normalized,
                        "message": "discovery source path escapes the project root",
                    }
                )
                continue
            if normalized in source_paths:
                findings.append(
                    {
                        "code": "implementation_surface_discovery_source_path_duplicate",
                        "severity": "blocker",
                        "source_path": normalized,
                        "message": "discovery source paths must be unique",
                    }
                )
                continue
            source_paths.append(normalized)

    source_paths = sorted(source_paths)
    source_identities = observed.get("source_identities")
    identity_by_path: dict[str, Mapping[str, Any]] = {}
    if not isinstance(source_identities, list):
        findings.append(
            {
                "code": "implementation_surface_discovery_source_identities_missing",
                "severity": "blocker",
                "message": "discovery must carry source identities for every source path",
            }
        )
    else:
        for index, raw_identity in enumerate(source_identities):
            if not isinstance(raw_identity, Mapping):
                findings.append(
                    {
                        "code": "implementation_surface_discovery_source_identity_invalid",
                        "severity": "blocker",
                        "row_index": index,
                        "message": "discovery source identity must be an object",
                    }
                )
                continue
            source_path = str(raw_identity.get("source_path", "")).replace("\\", "/")
            if not source_path:
                findings.append(
                    {
                        "code": "implementation_surface_discovery_source_identity_path_missing",
                        "severity": "blocker",
                        "row_index": index,
                        "message": "discovery source identity has no source_path",
                    }
                )
                continue
            if source_path in identity_by_path:
                findings.append(
                    {
                        "code": "implementation_surface_discovery_source_identity_duplicate",
                        "severity": "blocker",
                        "source_path": source_path,
                        "message": "discovery source identities must be unique",
                    }
                )
                continue
            identity_by_path[source_path] = raw_identity
    if set(identity_by_path) != set(source_paths):
        findings.append(
            {
                "code": "implementation_surface_discovery_source_identity_conservation_failed",
                "severity": "blocker",
                "message": "discovery source identities do not conserve source_paths",
                "missing": sorted(set(source_paths) - set(identity_by_path)),
                "unexpected": sorted(set(identity_by_path) - set(source_paths)),
            }
        )

    current_source_identities: dict[str, dict[str, Any]] = {}
    for source_path in source_paths:
        path = (root / source_path).resolve()
        try:
            path.relative_to(root.resolve())
            stat = path.stat() if path.is_file() else None
        except (OSError, ValueError):
            stat = None
        declared = identity_by_path.get(source_path)
        current_fingerprint = ""
        # Light currentness uses the producer's exact content identity only
        # when the cheap file pointer (size + mtime) is unchanged.  A changed
        # pointer, a missing pointer, or the explicit full profile performs
        # one exact content read.  This keeps normal invocations cheap without
        # creating a second authority or silently accepting changed files.
        if (
            currentness_profile == "light"
            and stat is not None
            and isinstance(declared, Mapping)
            and isinstance(declared.get("source_size"), int)
            and isinstance(declared.get("source_mtime_ns"), int)
            and int(declared["source_size"]) == int(stat.st_size)
            and int(declared["source_mtime_ns"]) == int(stat.st_mtime_ns)
            and _CURRENT_IDENTITY_FINGERPRINT_RE.fullmatch(
                str(declared.get("source_fingerprint", ""))
            )
        ):
            current_fingerprint = str(declared["source_fingerprint"])
        elif stat is not None:
            try:
                current_fingerprint = _sha256_file(path)
            except OSError:
                current_fingerprint = ""
        if not current_fingerprint:
            findings.append(
                {
                    "code": "implementation_surface_discovery_source_missing",
                    "severity": "blocker",
                    "source_path": source_path,
                    "message": "discovery source path is missing or unreadable",
                }
            )
            continue
        current_source_identities[source_path] = {
            "source_path": source_path,
            "source_fingerprint": current_fingerprint,
        }
        if stat is not None:
            current_source_identities[source_path].update(
                {
                    "source_size": int(stat.st_size),
                    "source_mtime_ns": int(stat.st_mtime_ns),
                }
            )
        if not isinstance(declared, Mapping) or declared.get("source_fingerprint") != current_fingerprint:
            findings.append(
                {
                    "code": "implementation_surface_discovery_source_identity_stale",
                    "severity": "blocker",
                    "source_path": source_path,
                    "message": "discovery source identity does not match the current file",
                }
            )

    raw_rows = observed.get("surfaces")
    rows: list[Mapping[str, Any]] = []
    if not isinstance(raw_rows, list):
        findings.append(
            {
                "code": "implementation_surface_discovery_rows_invalid",
                "severity": "blocker",
                "message": "implementation-surface discovery surfaces must be an array",
            }
        )
    else:
        for index, raw_row in enumerate(raw_rows):
            if not isinstance(raw_row, Mapping):
                findings.append(
                    {
                        "code": "implementation_surface_discovery_row_invalid",
                        "severity": "blocker",
                        "row_index": index,
                        "message": "discovery surface row must be an object",
                    }
                )
                continue
            rows.append(raw_row)

    # A partitioned/merged observation is allowed to skip the expensive
    # whole-tree replay only after the shard verifier has established the
    # complete current production boundary.  Requiring that boundary here
    # prevents a caller-authored ``merged`` snapshot from omitting a newly
    # added source file while keeping the bounded shard route intact.
    partitioned_snapshot = (
        str(observed.get("shard_id", "")) == "merged"
        or "shard_ids" in observed
        or "shard_plan_fingerprint" in observed
    )
    if partitioned_snapshot:
        if str(observed.get("shard_id", "")) != "merged":
            findings.append(
                {
                    "code": "implementation_surface_discovery_partition_marker_invalid",
                    "severity": "blocker",
                    "message": "a partitioned implementation observation must be the verified merged artifact",
                }
            )
        raw_shard_ids = observed.get("shard_ids")
        if (
            not isinstance(raw_shard_ids, list)
            or not raw_shard_ids
            or any(not isinstance(item, str) or not item.strip() for item in raw_shard_ids)
            or len(raw_shard_ids) != len(set(raw_shard_ids))
        ):
            findings.append(
                {
                    "code": "implementation_surface_discovery_shard_ids_invalid",
                    "severity": "blocker",
                    "message": "a merged implementation observation needs a non-empty unique shard id list",
                }
            )
        plan_fingerprint = str(observed.get("shard_plan_fingerprint", ""))
        if not _CURRENT_IDENTITY_FINGERPRINT_RE.fullmatch(plan_fingerprint):
            findings.append(
                {
                    "code": "implementation_surface_discovery_shard_plan_identity_invalid",
                    "severity": "blocker",
                    "message": "a merged implementation observation needs a canonical current shard-plan fingerprint",
                }
            )
        try:
            current_boundary = sorted(
                _surface_relative_paths(root, _surface_candidate_files(root))
            )
        except (OSError, ValueError, PublicBehaviorSurfaceAuditError) as exc:
            findings.append(
                {
                    "code": "implementation_surface_discovery_current_boundary_unreadable",
                    "severity": "blocker",
                    "message": f"current production source boundary could not be verified: {exc}",
                }
            )
        else:
            if source_paths != current_boundary:
                findings.append(
                    {
                        "code": "implementation_surface_discovery_merged_source_boundary_mismatch",
                        "severity": "blocker",
                        "message": "merged implementation observation does not conserve the complete current production source boundary",
                        "missing": sorted(set(current_boundary) - set(source_paths)),
                        "unexpected": sorted(set(source_paths) - set(current_boundary)),
                    }
                )

    discovered_ids = {
        str(row.get("surface_id", "")).strip()
        for row in rows
        if str(row.get("surface_id", "")).strip()
    }
    for row in rows:
        surface_id = str(row.get("surface_id", "")).strip()
        source_path = str(row.get("source_path", "")).replace("\\", "/")
        if not surface_id:
            findings.append(
                {
                    "code": "implementation_surface_discovery_surface_id_missing",
                    "severity": "blocker",
                    "message": "every discovery row needs a stable surface_id",
                }
            )
        if source_path not in source_paths:
            findings.append(
                {
                    "code": "implementation_surface_discovery_row_foreign_source",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": "discovery row belongs to a source outside source_paths",
                }
            )
        current_fingerprint = current_source_identities.get(source_path, {}).get(
            "source_fingerprint"
        )
        if current_fingerprint and row.get("source_fingerprint") != current_fingerprint:
            findings.append(
                {
                    "code": "implementation_surface_discovery_row_source_stale",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": "discovery row source fingerprint is not current",
                }
            )
        row_without_fingerprint = {
            key: value for key, value in row.items() if key != "surface_fingerprint"
        }
        if row.get("surface_fingerprint") != _surface_hash(row_without_fingerprint):
            findings.append(
                {
                    "code": "implementation_surface_discovery_surface_fingerprint_stale",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": "discovery surface fingerprint does not match its canonical row",
                }
            )
        expected_class = _surface_class_for_kind(str(row.get("surface_kind", "")))
        if not expected_class or row.get("surface_class") != expected_class:
            findings.append(
                {
                    "code": "implementation_surface_discovery_surface_class_invalid",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": "discovery surface class is missing or mismatched",
                }
            )
        expected_group_id, expected_granularity = _surface_review_group(
            source_path,
            str(row.get("surface_kind", "")),
            str(row.get("symbol", "")),
        )
        if (
            row.get("review_group_id") != expected_group_id
            or row.get("review_granularity") != expected_granularity
        ):
            findings.append(
                {
                    "code": "implementation_surface_discovery_review_group_invalid",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": "discovery review_group_id/review_granularity does not match the current deterministic review boundary",
                }
            )

    raw_unbound = observed.get("unbound_surface_ids")
    if not isinstance(raw_unbound, list):
        findings.append(
            {
                "code": "implementation_surface_discovery_unbound_ids_invalid",
                "severity": "blocker",
                "message": "discovery must carry an unbound_surface_ids array",
            }
        )
        unbound_ids: list[str] = []
    else:
        unbound_ids = [str(item) for item in raw_unbound]
        if len(unbound_ids) != len(set(unbound_ids)):
            findings.append(
                {
                    "code": "implementation_surface_discovery_unbound_ids_duplicate",
                    "severity": "blocker",
                    "message": "discovery unbound_surface_ids must be unique",
                }
            )
    expected_unbound_ids = sorted(
        str(row.get("surface_id"))
        for row in rows
        if row.get("surface_kind") == "unreachable_or_unbound"
        and str(row.get("surface_id", "")).strip()
    )
    if sorted(set(unbound_ids)) != expected_unbound_ids:
        findings.append(
            {
                "code": "implementation_surface_discovery_unbound_conservation_failed",
                "severity": "blocker",
                "message": "discovery unbound_surface_ids do not match the observed rows",
                "expected": expected_unbound_ids,
                "actual": sorted(set(unbound_ids)),
            }
        )

    raw_call_graph = observed.get("call_graph")
    call_graph: list[Mapping[str, Any]] = []
    if not isinstance(raw_call_graph, list):
        findings.append(
            {
                "code": "implementation_surface_discovery_call_graph_missing",
                "severity": "blocker",
                "message": "discovery must carry its source-only call graph",
            }
        )
    else:
        for index, raw_edge in enumerate(raw_call_graph):
            if not isinstance(raw_edge, Mapping):
                findings.append(
                    {
                        "code": "implementation_surface_discovery_call_graph_row_invalid",
                        "severity": "blocker",
                        "row_index": index,
                        "message": "discovery call-graph row must be an object",
                    }
                )
                continue
            call_graph.append(raw_edge)
            caller = str(raw_edge.get("caller_surface_id", ""))
            resolution = str(raw_edge.get("resolution", ""))
            resolved = raw_edge.get("resolved_surface_ids")
            if caller not in discovered_ids:
                findings.append(
                    {
                        "code": "implementation_surface_discovery_call_graph_orphan_caller",
                        "severity": "blocker",
                        "surface_id": caller,
                        "message": "call-graph caller is not present in the discovery denominator",
                    }
                )
            if not isinstance(resolved, list):
                findings.append(
                    {
                        "code": "implementation_surface_discovery_call_graph_targets_invalid",
                        "severity": "blocker",
                        "surface_id": caller,
                        "message": "call-graph resolved_surface_ids must be an array",
                    }
                )
                resolved = []
            elif len(resolved) != len(set(str(item) for item in resolved)):
                findings.append(
                    {
                        "code": "implementation_surface_discovery_call_graph_targets_duplicate",
                        "severity": "blocker",
                        "surface_id": caller,
                        "message": "call-graph source target ids must be unique",
                    }
                )
            for target in resolved:
                if str(target) not in discovered_ids:
                    findings.append(
                        {
                            "code": "implementation_surface_discovery_call_graph_orphan_callee",
                            "severity": "blocker",
                            "surface_id": str(target),
                        "message": "call-graph callee is not present in the discovery denominator",
                    }
                )
            if resolution not in {
                "resolved",
                "resolved_static_dispatch",
                "resolved_external_contract",
            }:
                findings.append(
                    {
                        "code": "implementation_surface_discovery_call_graph_resolution_invalid",
                        "severity": "blocker",
                        "surface_id": caller,
                        "message": "call-graph resolution is not a current vocabulary value",
                    }
                )
            if resolution == "resolved_static_dispatch" and len(resolved) < 2:
                findings.append(
                    {
                        "code": "implementation_surface_discovery_call_graph_dispatch_invalid",
                        "severity": "blocker",
                        "surface_id": caller,
                        "message": "resolved_static_dispatch edges must enumerate at least two current source targets",
                    }
                )
            if resolution == "resolved" and len(resolved) != 1:
                findings.append(
                    {
                        "code": "implementation_surface_discovery_call_graph_resolution_invalid",
                        "severity": "blocker",
                        "surface_id": caller,
                        "message": "resolved call-graph edges must name exactly one callee",
                    }
                )
            if resolution == "resolved_external_contract":
                external_contract_id = str(
                    raw_edge.get("external_contract_id", "")
                ).strip()
                boundary_kind = str(raw_edge.get("boundary_kind", "")).strip()
                if resolved or not _CURRENT_CALL_CONTRACT_ID_RE.fullmatch(
                    external_contract_id
                ):
                    findings.append(
                        {
                            "code": "implementation_surface_discovery_call_graph_boundary_invalid",
                            "severity": "blocker",
                            "surface_id": caller,
                            "message": "external/dynamic call edges need one stable target identity and no source callee",
                        }
                    )
                if boundary_kind not in _CURRENT_EXTERNAL_CONTRACT_BOUNDARY_KINDS:
                    findings.append(
                        {
                            "code": "implementation_surface_discovery_call_graph_external_target_invalid",
                            "severity": "blocker",
                            "surface_id": caller,
                            "message": (
                                "external/dynamic call edges need a current external "
                                "contract boundary kind"
                            ),
                        }
                    )
                expected_target_fields = _surface_external_contract_target_fields(
                    external_contract_id
                )
                target_field_mismatches = {
                    field: {
                        "expected": expected,
                        "actual": raw_edge.get(field),
                    }
                    for field, expected in expected_target_fields.items()
                    if raw_edge.get(field) != expected
                }
                if target_field_mismatches:
                    findings.append(
                        {
                            "code": "implementation_surface_discovery_call_graph_external_target_invalid",
                            "severity": "blocker",
                            "surface_id": caller,
                            "message": (
                                "external/dynamic call edges must carry an exact "
                                "current external-contract target identity and registry proof"
                            ),
                            "mismatches": target_field_mismatches,
                        }
                    )

    declared_external_contracts = observed.get("external_contracts")
    expected_external_contracts = _surface_external_contracts(call_graph)
    if declared_external_contracts != expected_external_contracts:
        findings.append(
            {
                "code": "implementation_surface_discovery_external_contract_conservation_failed",
                "severity": "blocker",
                "message": (
                    "discovery external-contract rows must exactly conserve "
                    "resolved external-contract call edges"
                ),
            }
        )

    shard_id = str(observed.get("shard_id", "full"))
    canonical_payload: dict[str, Any] = {
        "schema_version": IMPLEMENTATION_SURFACE_AUDIT_SCHEMA,
        "shard_id": shard_id,
        "source_paths": source_paths,
        "source_identities": [
            _source_identity_content_projection(current_source_identities[path])
            for path in sorted(current_source_identities)
        ],
        "surfaces": sorted(rows, key=lambda row: str(row.get("surface_id", ""))),
        "call_graph": sorted(
            call_graph,
            key=lambda row: (
                str(row.get("caller_surface_id", "")),
                str(row.get("callee_name", "")),
                str(row.get("resolution", "")),
            ),
        ),
        "external_contracts": expected_external_contracts,
        "unbound_surface_ids": expected_unbound_ids,
    }
    if shard_id == "merged" or "shard_ids" in observed or "shard_plan_fingerprint" in observed:
        canonical_payload["shard_plan_fingerprint"] = str(
            observed.get("shard_plan_fingerprint", "")
        )
        raw_shard_ids = observed.get("shard_ids", ())
        canonical_payload["shard_ids"] = sorted(
            str(item) for item in raw_shard_ids if isinstance(item, str)
        ) if isinstance(raw_shard_ids, list) else []
    expected_discovery_fingerprint = _surface_hash(canonical_payload)
    if observed.get("discovery_fingerprint") != expected_discovery_fingerprint:
        findings.append(
            {
                "code": "implementation_surface_discovery_fingerprint_stale",
                "severity": "blocker",
                "message": "discovery fingerprint does not match the current source observation",
            }
        )
    return findings


def _discovery_observation_is_usable(observed: Mapping[str, Any]) -> bool:
    """Return whether a discovery artifact is a safe reverse-map denominator.

    The producer is terminal only after every call site has a current source,
    dispatch-set, external-boundary, or dynamic-boundary identity.  Parse,
    identity, shard, source, or any other finding remains a hard discovery
    blocker.  Stale blocked-only or unresolved call-graph artifacts are not
    accepted as a compatibility path.
    """

    if str(observed.get("status", "")).strip() != "passed":
        return False
    if str(observed.get("shard_id", "")).strip() != "merged":
        # A non-sharded terminal producer is already a complete source
        # observation.  Its own call graph is still validated below by the
        # normal discovery snapshot checks.
        return True
    shard_ids = observed.get("shard_ids")
    if (
        not isinstance(shard_ids, list)
        or not shard_ids
        or any(not isinstance(item, str) or not item.strip() for item in shard_ids)
        or len(shard_ids) != len(set(shard_ids))
    ):
        return False
    plan_fingerprint = str(observed.get("shard_plan_fingerprint", "")).strip()
    if not _CURRENT_IDENTITY_FINGERPRINT_RE.fullmatch(plan_fingerprint):
        return False
    return True


def _load_surface_map(value: Mapping[str, Any] | str | Path) -> Mapping[str, Any]:
    if isinstance(value, (str, Path)):
        try:
            value = json.loads(Path(value).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PublicBehaviorSurfaceAuditError(f"cannot load implementation surface map: {exc}") from exc
    if not isinstance(value, Mapping):
        raise PublicBehaviorSurfaceAuditError("implementation surface map must be an object")
    return value


def _expand_component_group_mappings(
    value: Any,
    *,
    discovered_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Expand explicit component-group bindings into member-level checks.

    A component group is an authoring compression only.  It must name the
    complete deterministic component group, and every member is expanded into
    the same effective binding before the normal reverse validator runs.  No
    group can contain an externally addressable surface, and a partial group
    never silently covers its omitted members.
    """

    findings: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return [], [], [
            {
                "code": "implementation_surface_component_groups_invalid",
                "severity": "blocker",
                "message": "component_groups must be an array when supplied",
            }
        ]

    expected_members_by_group: dict[str, set[str]] = {}
    for surface_id, row in discovered_by_id.items():
        if str(row.get("review_granularity", "")).strip() != "component":
            continue
        group_id = str(row.get("review_group_id", "")).strip()
        if group_id:
            expected_members_by_group.setdefault(group_id, set()).add(surface_id)

    expanded: list[Mapping[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    seen_group_ids: set[str] = set()
    seen_member_ids: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            findings.append(
                {
                    "code": "implementation_surface_component_group_invalid",
                    "severity": "blocker",
                    "row_index": index,
                    "message": "every component group must be an object",
                }
            )
            continue
        group_id = str(raw.get("review_group_id", "")).strip()
        if not group_id:
            findings.append(
                {
                    "code": "implementation_surface_component_group_id_missing",
                    "severity": "blocker",
                    "row_index": index,
                    "message": "component group needs a review_group_id",
                }
            )
            continue
        if group_id in seen_group_ids:
            findings.append(
                {
                    "code": "implementation_surface_component_group_duplicate_id",
                    "severity": "blocker",
                    "review_group_id": group_id,
                    "message": "component group ids must be unique",
                }
            )
            continue
        seen_group_ids.add(group_id)
        if raw.get("review_granularity") != "component":
            findings.append(
                {
                    "code": "implementation_surface_component_group_granularity_invalid",
                    "severity": "blocker",
                    "review_group_id": group_id,
                    "message": "component_groups may contain only component review boundaries",
                }
            )
        if "surface_id" in raw:
            findings.append(
                {
                    "code": "implementation_surface_component_group_surface_id_forbidden",
                    "severity": "blocker",
                    "review_group_id": group_id,
                    "message": "a component group uses surface_ids; it cannot claim one singular surface_id",
                }
            )
        try:
            member_ids = _surface_strings(
                raw.get("surface_ids", ()),
                context=f"component group {group_id}.surface_ids",
            )
        except PublicBehaviorSurfaceAuditError as exc:
            findings.append(
                {
                    "code": "implementation_surface_component_group_members_invalid",
                    "severity": "blocker",
                    "review_group_id": group_id,
                    "message": str(exc),
                }
            )
            continue
        if not member_ids:
            findings.append(
                {
                    "code": "implementation_surface_component_group_members_missing",
                    "severity": "blocker",
                    "review_group_id": group_id,
                    "message": "a component group must name at least one member surface",
                }
            )
            continue
        expected_members = expected_members_by_group.get(group_id, set())
        if not expected_members:
            findings.append(
                {
                    "code": "implementation_surface_component_group_unknown",
                    "severity": "blocker",
                    "review_group_id": group_id,
                    "message": "component group does not resolve to a current observed component boundary",
                }
            )
        if set(member_ids) != expected_members:
            findings.append(
                {
                    "code": "implementation_surface_component_group_membership_mismatch",
                    "severity": "blocker",
                    "review_group_id": group_id,
                    "missing_surface_ids": sorted(expected_members - set(member_ids)),
                    "unexpected_surface_ids": sorted(set(member_ids) - expected_members),
                    "message": "component group must enumerate exactly every current member and no other surface",
                }
            )
        ineligible_members = sorted(
            surface_id
            for surface_id in member_ids
            if surface_id in discovered_by_id
            and str(discovered_by_id[surface_id].get("surface_kind", ""))
            not in IMPLEMENTATION_SURFACE_COMPONENT_GROUP_MEMBER_KINDS
        )
        if ineligible_members:
            findings.append(
                {
                    "code": "implementation_surface_component_group_kind_invalid",
                    "severity": "blocker",
                    "review_group_id": group_id,
                    "surface_ids": ineligible_members,
                    "message": (
                        "component group-level mapping is limited to ordinary "
                        "module/function/class implementation members; dynamic, "
                        "placeholder, and unbound observations remain individual"
                    ),
                }
            )
        for surface_id in member_ids:
            if surface_id in seen_member_ids:
                findings.append(
                    {
                        "code": "implementation_surface_component_group_member_duplicate",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "message": "a component surface cannot be covered by multiple component groups",
                    }
                )
            seen_member_ids.add(surface_id)
            observed = discovered_by_id.get(surface_id)
            if observed is None:
                findings.append(
                    {
                        "code": "implementation_surface_component_group_orphan_member",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "message": "component group member is not a current observed surface",
                    }
                )
            elif str(observed.get("review_granularity", "")).strip() != "component":
                findings.append(
                    {
                        "code": "implementation_surface_component_group_external_member",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "message": "public/external surfaces must remain individual map rows",
                    }
                )

        base = dict(raw)
        base.pop("surface_ids", None)
        base.pop("review_group_id", None)
        base["review_group_id"] = group_id
        base["review_granularity"] = "component"
        for surface_id in member_ids:
            member = dict(base)
            member["surface_id"] = surface_id
            expanded.append(member)
        summaries.append(
            {
                "review_group_id": group_id,
                "review_granularity": "component",
                "surface_ids": sorted(member_ids),
                "surface_count": len(member_ids),
            }
        )
    return expanded, summaries, findings


def _test_reference_exists(root: Path, reference: str) -> tuple[bool, str]:
    if not isinstance(reference, str) or "#" not in reference:
        return False, "test reference must include a repository-relative path and #anchor"
    path_text, anchor = reference.split("#", 1)
    path = (root / path_text).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return False, "test reference escapes the project root"
    if not path.is_file():
        return False, "test reference file is missing"
    if not anchor.strip():
        return False, "test reference anchor is empty"
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        return False, f"test reference file cannot be parsed: {exc}"
    anchor_parts = tuple(part for part in anchor.strip().split(".") if part)
    if not anchor_parts:
        return False, "test reference anchor is empty"
    target_name = anchor_parts[-1]
    target_nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.name == target_name
    ]
    if not target_nodes:
        return False, "test reference anchor is not present"
    for node in target_nodes:
        body = list(getattr(node, "body", ()))
        meaningful = [
            item
            for item in body
            if not (
                isinstance(item, ast.Expr)
                and isinstance(getattr(item, "value", None), ast.Constant)
                and isinstance(item.value.value, str)
            )
        ]
        if isinstance(node, ast.ClassDef):
            if not target_name.casefold().startswith("test"):
                continue
            # A test class is not empty when it contains at least one actual
            # test method.  A production helper class or an arbitrary class
            # anchor is not test evidence.
            if any(
                isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name.casefold().startswith("test")
                and any(
                    not (
                        isinstance(statement, ast.Expr)
                        and isinstance(
                            getattr(statement, "value", None), ast.Constant
                        )
                        and isinstance(statement.value.value, str)
                    )
                    and not isinstance(statement, ast.Pass)
                    for statement in getattr(item, "body", ())
                )
                for item in meaningful
            ):
                return True, ""
        elif (
            (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
            and target_name.casefold().startswith("test")
            and meaningful
            and not all(isinstance(item, ast.Pass) for item in meaningful)
        ):
            return True, ""
    if not target_name.casefold().startswith("test"):
        return False, "test reference anchor is not a test member"
    return False, "test reference target is empty"


def _proof_reference_exists(root: Path, reference: str) -> tuple[bool, str]:
    """Resolve an evidence/proof anchor without treating it as a test node."""

    if not isinstance(reference, str) or "#" not in reference:
        return False, "proof reference must include a repository-relative path and #anchor"
    path_text, anchor = reference.split("#", 1)
    path = (root / path_text).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return False, "proof reference escapes the project root"
    if not path.is_file():
        return False, "proof reference file is missing"
    if not anchor.strip():
        return False, "proof reference anchor is empty"
    text = path.read_text(encoding="utf-8", errors="replace")
    if anchor.strip() in text:
        return True, ""
    return False, "proof reference anchor is not present"


def _receipt_reference_exists(root: Path, reference: str) -> tuple[bool, str]:
    """Resolve a current terminal receipt reference without executing it."""

    if not isinstance(reference, str) or "#" not in reference:
        return False, "receipt reference must include a repository-relative path and #anchor"
    path_text, anchor = reference.split("#", 1)
    path = (root / path_text).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return False, "receipt reference escapes the project root"
    if not path.is_file():
        return False, "receipt reference file is missing"
    if not anchor.strip():
        return False, "receipt reference anchor is empty"
    text = path.read_text(encoding="utf-8", errors="replace")
    if anchor.strip() in text:
        return True, ""
    return False, "receipt reference anchor is not present"


def _owner_values(value: Any, *, context: str) -> tuple[str, ...]:
    """Normalize an owner claim while preserving duplicate-owner failures.

    The reverse map's current canonical field is the scalar ``owner``.  A
    caller may still accidentally serialize a primary owner as ``owner_ids``
    (or put a list directly in ``owner``).  Treating that shape as a normal
    truthy value would make a mapping look owned while hiding an ownership
    conflict.  Keep the parser deliberately small and return the complete
    sequence so the caller can emit a stable duplicate-primary-owner finding.
    """

    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    return _surface_strings(value, context=context)


def audit_implementation_behavior_surface(
    root: str | Path,
    surface_map: Mapping[str, Any] | str | Path | None,
    *,
    discovery: Mapping[str, Any] | None = None,
    currentness_profile: str = "full",
) -> dict[str, Any]:
    """Close the reverse implementation -> intent/model/test direction.

    Discovery is a production-source observation.  The map is independent
    author input.  No model or test name is ever used to enlarge the observed
    denominator.  Missing map/owner/test/receipt, stale source identity,
    orphan test/receipt references, empty tests, blocked gaps, zero mappings,
    and unmodeled UI-like actions are blockers.
    """

    bounded_root = Path(root).resolve()
    # ``None`` means the native producer should run.  A supplied but empty or
    # malformed artifact is an explicit input and must remain a visible
    # blocker; truthiness fallback would silently replace it with a fresh
    # observation and could make a missing denominator look green.
    observed = dict(
        discover_implementation_behavior_surfaces(bounded_root)
        if discovery is None
        else discovery
    )
    observed_findings = observed.get("findings", ())
    if not isinstance(observed_findings, (list, tuple)):
        observed_findings = ()
    discovery_snapshot_findings = _validate_discovery_snapshot(
        bounded_root,
        observed,
        currentness_profile=currentness_profile,
    )
    all_discovery_findings = [
        item
        for item in [*observed_findings, *discovery_snapshot_findings]
        if isinstance(item, Mapping)
    ]
    discovery_observation_usable = _discovery_observation_is_usable(observed)
    # Every current call-graph edge is required to be a resolved source target,
    # an exact finite dispatch set, or an exact external-contract target.  Any
    # malformed, ambiguous, unknown, or boundary-only edge remains a blocker;
    # it is never retained as a typed observation or silently downgraded before
    # semantic-map validation.
    discovery_observation_findings = [dict(item) for item in all_discovery_findings]
    findings = [dict(item) for item in all_discovery_findings]
    # A direct source observation can be reproduced from its frozen source
    # selection.  Re-run that bounded producer here so an omitted/new surface
    # cannot be hidden by a caller-authored row set whose hashes merely agree
    # with itself.  Merged shard artifacts are verified by the shard protocol;
    # rerunning the unbounded whole tree here would violate its partition.
    if (
        "shard_ids" not in observed
        and "shard_plan_fingerprint" not in observed
    ):
        if currentness_profile == "full":
            try:
                full_reproduced = discover_implementation_behavior_surfaces(
                    bounded_root,
                    shard_id=str(observed.get("shard_id", "full")),
                )
            except Exception as exc:
                findings.append(
                    {
                        "code": "implementation_surface_discovery_replay_failed",
                        "severity": "blocker",
                        "message": f"current source observation could not be reproduced: {exc}",
                    }
                )
            else:
                # One full replay is the frozen source observation for both
                # exact replay and complete-boundary checks.  The previous
                # implementation performed a second discovery over the same
                # files with an explicit source-path list, which added a full
                # read/hash pass without adding an independent authority.
                if full_reproduced.get("discovery_fingerprint") != observed.get(
                    "discovery_fingerprint"
                ):
                    findings.append(
                        {
                            "code": "implementation_surface_discovery_replay_mismatch",
                            "severity": "blocker",
                            "message": "supplied discovery does not equal the current bounded source observation",
                        }
                    )
                if (
                    full_reproduced.get("source_paths")
                    != observed.get("source_paths")
                ):
                    findings.append(
                        {
                            "code": "implementation_surface_discovery_full_replay_mismatch",
                            "severity": "blocker",
                            "message": (
                                "supplied direct discovery does not cover the complete "
                                "current production source boundary"
                            ),
                        }
                    )
                if not _discovery_observation_is_usable(full_reproduced):
                    findings.append(
                        {
                            "code": "implementation_surface_discovery_full_replay_not_current",
                            "severity": "blocker",
                            "message": (
                                "the complete current production source observation is "
                                "not a terminal pass"
                            ),
                        }
                    )
        else:
            try:
                current_boundary = sorted(
                    _surface_relative_paths(
                        bounded_root, _surface_candidate_files(bounded_root)
                    )
                )
            except (OSError, ValueError, PublicBehaviorSurfaceAuditError) as exc:
                findings.append(
                    {
                        "code": "implementation_surface_discovery_current_boundary_unreadable",
                        "severity": "blocker",
                        "message": f"current production source boundary could not be verified: {exc}",
                    }
                )
            else:
                declared_boundary = sorted(
                    str(value).replace("\\", "/")
                    for value in observed.get("source_paths", ())
                    if isinstance(value, str)
                )
                if current_boundary != declared_boundary:
                    findings.append(
                        {
                            "code": "implementation_surface_discovery_light_boundary_mismatch",
                            "severity": "blocker",
                            "message": (
                                "light currentness found a changed production source "
                                "boundary; run a fresh discovery or full profile"
                            ),
                            "missing": sorted(set(current_boundary) - set(declared_boundary)),
                            "unexpected": sorted(set(declared_boundary) - set(current_boundary)),
                        }
                    )
    if not discovery_observation_usable:
        findings.append(
            {
                "code": "implementation_surface_discovery_not_current",
                "severity": "blocker",
                "message": (
                    "the supplied implementation-surface observation is not "
                    "a current terminal pass"
                ),
            }
        )
    raw_rows = observed.get("surfaces", ())
    if not isinstance(raw_rows, (list, tuple)):
        findings.append(
            {
                "code": "implementation_surface_discovery_rows_invalid",
                "severity": "blocker",
                "message": "the implementation-surface observation must contain an array of rows",
            }
        )
        rows: tuple[Any, ...] = ()
    else:
        rows = tuple(raw_rows)

    # Do not let a malformed or duplicated discovery row collapse the
    # denominator through a dict comprehension.  A map with one row for the
    # resulting dictionary would otherwise appear complete even though the
    # independent source observation was not conserved.
    discovered_by_id: dict[str, Mapping[str, Any]] = {}
    duplicate_discovery_ids: set[str] = set()
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            findings.append(
                {
                    "code": "implementation_surface_discovery_row_invalid",
                    "severity": "blocker",
                    "row_index": index,
                    "message": "every discovered implementation surface must be an object row",
                }
            )
            continue
        surface_id = str(raw.get("surface_id", "")).strip()
        if not surface_id:
            findings.append(
                {
                    "code": "implementation_surface_discovery_surface_id_missing",
                    "severity": "blocker",
                    "row_index": index,
                    "message": "every discovered implementation surface needs a stable surface_id",
                }
            )
            continue
        if surface_id in discovered_by_id:
            duplicate_discovery_ids.add(surface_id)
            findings.append(
                {
                    "code": "implementation_surface_discovery_duplicate_id",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": "independent implementation discovery contains duplicate surface_id rows",
                }
            )
            continue
        discovered_by_id[surface_id] = raw
    result: dict[str, Any] = {
        "schema_version": IMPLEMENTATION_SURFACE_AUDIT_SCHEMA,
        "status": "blocked",
        "claim_boundary": "Reverse static implementation surface closure to explicit intent, model owner, owner, and test references.",
        "discovery_fingerprint": observed.get("discovery_fingerprint", ""),
        "currentness_profile": currentness_profile,
        "current_authority_join": {"status": "not_required"},
        "current_behavior_ledger_join": {"status": "not_required"},
        "discovered_surface_count": len(discovered_by_id),
        "mapping_input_surface_row_count": 0,
        "mapping_surface_count": 0,
        "mapping_component_group_count": 0,
        "mapping_component_group_member_count": 0,
        "mapped_surface_ids": [],
        "unmapped_surface_ids": [],
        "orphan_mapping_surface_ids": [],
        "orphan_test_references": [],
        "orphan_receipt_references": [],
        "unmapped_model_obligation_ids": [],
        "orphan_model_obligation_surface_ids": [],
        "model_obligation_inventory_count": 0,
        "current_model_obligation_ids": [],
        "unmodeled_ui_like_action_ids": [],
        "duplicate_primary_owner_surface_ids": [],
        "duplicate_primary_model_owner_surface_ids": [],
        "duplicate_discovery_surface_ids": sorted(duplicate_discovery_ids),
        "surface_group_count": 0,
        "component_grouped_surface_count": 0,
        "individual_surface_count": 0,
        "surface_groups": [],
        "reverse_closure_complete": False,
        "discovery_observation_status": (
            "terminal_pass"
            if str(observed.get("status", "")).strip() == "passed"
            else "blocked"
        ),
        "discovery_observation_findings": discovery_observation_findings,
    }
    grouped: dict[str, dict[str, Any]] = {}
    for surface_id, row in sorted(discovered_by_id.items()):
        group_id = str(row.get("review_group_id", "")).strip()
        granularity = str(row.get("review_granularity", "")).strip()
        if not group_id or granularity not in {"surface", "component"}:
            findings.append(
                {
                    "code": "implementation_surface_review_group_missing",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": (
                        "every source observation needs a current review_group_id "
                        "and review_granularity; source lines are anchors, not rows"
                    ),
                }
            )
            continue
        group = grouped.setdefault(
            group_id,
            {
                "review_group_id": group_id,
                "review_granularity": granularity,
                "source_paths": set(),
                "surface_ids": [],
            },
        )
        if group["review_granularity"] != granularity:
            findings.append(
                {
                    "code": "implementation_surface_review_group_granularity_mismatch",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": "one review group cannot mix component and individual granularity",
                }
            )
        group["source_paths"].add(str(row.get("source_path", "")))
        group["surface_ids"].append(surface_id)
    normalized_groups = []
    for group_id, group in sorted(grouped.items()):
        normalized_groups.append(
            {
                "review_group_id": group_id,
                "review_granularity": group["review_granularity"],
                "source_paths": sorted(group["source_paths"]),
                "surface_ids": sorted(group["surface_ids"]),
                "surface_count": len(group["surface_ids"]),
            }
        )
    result["surface_groups"] = normalized_groups
    result["surface_group_count"] = len(normalized_groups)
    result["component_grouped_surface_count"] = sum(
        group["surface_count"]
        for group in normalized_groups
        if group["review_granularity"] == "component"
    )
    result["individual_surface_count"] = sum(
        group["surface_count"]
        for group in normalized_groups
        if group["review_granularity"] == "surface"
    )
    if not discovered_by_id:
        findings.append(
            {
                "code": "implementation_surface_discovery_denominator_empty",
                "severity": "blocker",
                "message": "an implementation-surface audit cannot pass with zero discovered production surfaces",
            }
        )
    current_authority_join = _load_current_authority_join(bounded_root)
    current_authority_join_valid = False
    if current_authority_join is None:
        result["current_authority_join"] = {"status": "not_required"}
    elif current_authority_join.get("load_error"):
        result["current_authority_join"] = {
            "status": "blocked",
            "load_error": str(current_authority_join.get("load_error")),
        }
        findings.append(
            {
                "code": "implementation_surface_current_authority_invalid",
                "severity": "blocker",
                "message": (
                    "the target declares a FlowGuard project but its native "
                    "current model authority could not be loaded"
                ),
            }
        )
    current_behavior_ledger_join = _load_current_behavior_ledger_join(bounded_root)
    current_behavior_ledger_join_valid = False
    if current_behavior_ledger_join is None:
        result["current_behavior_ledger_join"] = {"status": "not_required"}
    elif current_behavior_ledger_join.get("load_error"):
        result["current_behavior_ledger_join"] = {
            "status": "blocked",
            "load_error": str(current_behavior_ledger_join.get("load_error")),
        }
        findings.append(
            {
                "code": "implementation_surface_current_behavior_ledger_invalid",
                "severity": "blocker",
                "message": (
                    "the target declares a FlowGuard project but its native "
                    "current behavior ledger could not be loaded"
                ),
            }
        )
    if surface_map is None:
        findings.append({"code": "implementation_surface_mapping_missing", "severity": "blocker", "message": "An independently authored implementation surface map is required; discovery cannot invent intent/model/test bindings."})
        result["findings"] = findings
        result["evidence_fingerprint"] = _surface_hash(result)
        return result
    try:
        mapping = _load_surface_map(surface_map)
    except PublicBehaviorSurfaceAuditError as exc:
        findings.append({"code": "implementation_surface_mapping_invalid", "severity": "blocker", "message": str(exc)})
        result["findings"] = findings
        result["evidence_fingerprint"] = _surface_hash(result)
        return result
    if mapping.get("schema_version") != IMPLEMENTATION_SURFACE_MAP_SCHEMA:
        findings.append({"code": "implementation_surface_mapping_invalid", "severity": "blocker", "message": "implementation surface map schema is not current"})
    for field in ("inventory_id", "project_boundary", "current_revision", "discovery_fingerprint", "claim_boundary"):
        if not isinstance(mapping.get(field), str) or not mapping.get(field, "").strip():
            findings.append({"code": "implementation_surface_mapping_field_missing", "severity": "blocker", "field": field, "message": f"surface map field {field} is required"})
    mapped_rows = mapping.get("surfaces")
    component_group_rows = mapping.get("component_groups")
    has_component_groups = "component_groups" in mapping
    if not isinstance(mapped_rows, list):
        if not has_component_groups:
            findings.append({"code": "implementation_surface_mapping_rows_missing", "severity": "blocker", "message": "surface map must contain a surfaces array or explicit component_groups"})
        mapped_rows = []
    elif not mapped_rows and not has_component_groups:
        findings.append({"code": "implementation_surface_mapping_rows_missing", "severity": "blocker", "message": "surface map must contain a non-empty surfaces array"})
    if has_component_groups:
        component_group_mapped_rows, component_group_summaries, component_group_findings = _expand_component_group_mappings(
            component_group_rows,
            discovered_by_id=discovered_by_id,
        )
    else:
        component_group_mapped_rows, component_group_summaries, component_group_findings = (
            [],
            [],
            [],
        )
    findings.extend(component_group_findings)
    raw_surface_rows = list(mapped_rows)
    mapped_rows = [*raw_surface_rows, *component_group_mapped_rows]
    result["mapping_input_surface_row_count"] = len(raw_surface_rows)
    result["mapping_component_group_count"] = len(component_group_summaries)
    result["mapping_component_group_member_count"] = sum(
        int(group["surface_count"]) for group in component_group_summaries
    )
    result["component_groups"] = component_group_summaries
    model_obligation_rows = mapping.get("model_obligations")
    if not isinstance(model_obligation_rows, list) or not model_obligation_rows:
        findings.append({"code": "implementation_surface_model_obligation_inventory_missing", "severity": "blocker", "message": "surface map must carry an independently authored model_obligations array for reverse model->surface closure"})
        model_obligation_rows = []
    result["mapping_surface_count"] = len(mapped_rows)
    if result["mapping_surface_count"] == 0:
        findings.append(
            {
                "code": "implementation_surface_mapping_zero",
                "severity": "blocker",
                "message": "mapping_surface_count=0 is never a valid reverse-closure pass",
            }
        )
    if mapping.get("discovery_fingerprint") != observed.get("discovery_fingerprint"):
        findings.append({"code": "implementation_surface_mapping_stale", "severity": "blocker", "message": "surface map discovery fingerprint does not match the current production-source observation"})
    if current_authority_join is not None and not current_authority_join.get("load_error"):
        native_join_invalid = False
        if current_authority_join.get("status") not in {None, "current"}:
            native_join_invalid = True
            findings.append(
                {
                    "code": "implementation_surface_current_authority_invalid",
                    "severity": "blocker",
                    "message": "native current authority join is not in a current state",
                }
            )
        if current_authority_join.get("schema_version") != IMPLEMENTATION_SURFACE_CURRENT_AUTHORITY_JOIN_SCHEMA:
            native_join_invalid = True
            findings.append(
                {
                    "code": "implementation_surface_current_authority_join_schema_invalid",
                    "severity": "blocker",
                    "message": "native current authority join schema is not current",
                }
            )
        for field_name in (
            "head_fingerprint",
            "snapshot_fingerprint",
            "revision_set_fingerprint",
            "activation_receipt_fingerprint",
            "model_owner_ids",
            "owner_receipt_identities",
            "join_fingerprint",
        ):
            if field_name not in current_authority_join:
                native_join_invalid = True
                findings.append(
                    {
                        "code": "implementation_surface_current_authority_field_missing",
                        "severity": "blocker",
                        "field": field_name,
                        "message": "native current authority join is missing a required identity field",
                    }
                )
        native_projection_findings = _validate_current_authority_join_projection(
            current_authority_join
        )
        findings.extend(native_projection_findings)
        if native_projection_findings:
            native_join_invalid = True
        result["current_authority_join"] = {
            "status": "blocked" if native_join_invalid else "current",
            "join_fingerprint": current_authority_join.get("join_fingerprint", ""),
            "head_fingerprint": current_authority_join.get("head_fingerprint", ""),
            "snapshot_fingerprint": current_authority_join.get("snapshot_fingerprint", ""),
            "revision_set_fingerprint": current_authority_join.get(
                "revision_set_fingerprint", ""
            ),
            "activation_receipt_fingerprint": current_authority_join.get(
                "activation_receipt_fingerprint", ""
            ),
        }
        supplied_join = mapping.get("current_authority_join")
        if not isinstance(supplied_join, Mapping):
            findings.append(
                {
                    "code": "implementation_surface_current_authority_join_missing",
                    "severity": "blocker",
                    "message": (
                        "a modeled target requires an exact current model/owner/"
                        "receipt identity join in the reverse surface map"
                    ),
                }
            )
        else:
            expected_join = current_authority_join
            if supplied_join.get("schema_version") != expected_join.get("schema_version"):
                findings.append(
                    {
                        "code": "implementation_surface_current_authority_join_schema_invalid",
                        "severity": "blocker",
                        "message": "current authority join schema is not current",
                    }
                )
            for field_name in (
                "head_fingerprint",
                "snapshot_fingerprint",
                "revision_set_fingerprint",
                "activation_receipt_fingerprint",
                "model_owner_ids",
                "owner_receipt_identities",
                "join_fingerprint",
            ):
                if supplied_join.get(field_name) != expected_join.get(field_name):
                    findings.append(
                        {
                            "code": "implementation_surface_current_authority_identity_mismatch",
                            "severity": "blocker",
                            "field": field_name,
                            "message": (
                                "reverse surface map current authority identity "
                                f"does not match native current {field_name}"
                            ),
                        }
                    )
            current_authority_join_valid = not native_join_invalid and not any(
                item.get("code")
                in {
                    "implementation_surface_current_authority_join_schema_invalid",
                    "implementation_surface_current_authority_identity_mismatch",
                }
                for item in findings
            )
    if current_behavior_ledger_join is not None and not current_behavior_ledger_join.get(
        "load_error"
    ):
        native_ledger_join_invalid = False
        if current_behavior_ledger_join.get("status") != "current":
            native_ledger_join_invalid = True
            findings.append(
                {
                    "code": "implementation_surface_current_behavior_ledger_invalid",
                    "severity": "blocker",
                    "message": "native current behavior-ledger join is not in a current state",
                }
            )
        native_ledger_projection_findings = (
            _validate_current_behavior_ledger_join_projection(
                current_behavior_ledger_join
            )
        )
        findings.extend(native_ledger_projection_findings)
        if native_ledger_projection_findings:
            native_ledger_join_invalid = True
        result["current_behavior_ledger_join"] = {
            "status": "blocked" if native_ledger_join_invalid else "current",
            "ledger_path": current_behavior_ledger_join.get("ledger_path", ""),
            "ledger_id": current_behavior_ledger_join.get("ledger_id", ""),
            "current_revision": current_behavior_ledger_join.get(
                "current_revision", ""
            ),
            "ledger_fingerprint": current_behavior_ledger_join.get(
                "ledger_fingerprint", ""
            ),
            "commitment_ids": current_behavior_ledger_join.get(
                "commitment_ids", []
            ),
            "intent_ids": current_behavior_ledger_join.get("intent_ids", []),
            "model_obligation_ids": current_behavior_ledger_join.get(
                "model_obligation_ids", []
            ),
            "commitment_bindings": current_behavior_ledger_join.get(
                "commitment_bindings", []
            ),
            "join_fingerprint": current_behavior_ledger_join.get(
                "join_fingerprint", ""
            ),
        }
        supplied_ledger_join = mapping.get("current_behavior_ledger_join")
        if not isinstance(supplied_ledger_join, Mapping):
            findings.append(
                {
                    "code": "implementation_surface_current_behavior_ledger_join_missing",
                    "severity": "blocker",
                    "message": (
                        "a modeled target requires an exact current behavior "
                        "ledger identity join in the reverse surface map"
                    ),
                }
            )
        else:
            expected_ledger_join = current_behavior_ledger_join
            for field_name in (
                "schema_version",
                "ledger_path",
                "ledger_id",
                "current_revision",
                "ledger_fingerprint",
                "commitment_ids",
                "intent_ids",
                "model_obligation_ids",
                "commitment_bindings",
                "join_fingerprint",
            ):
                if supplied_ledger_join.get(field_name) != expected_ledger_join.get(
                    field_name
                ):
                    findings.append(
                        {
                            "code": "implementation_surface_current_behavior_ledger_identity_mismatch",
                            "severity": "blocker",
                            "field": field_name,
                            "message": (
                                "reverse surface map current behavior-ledger "
                                f"identity does not match native current {field_name}"
                            ),
                        }
                    )
            current_behavior_ledger_join_valid = (
                not native_ledger_join_invalid
                and not any(
                    item.get("code")
                    == "implementation_surface_current_behavior_ledger_identity_mismatch"
                    for item in findings
                )
            )
    mapped_by_id: dict[str, Mapping[str, Any]] = {}
    for index, raw in enumerate(mapped_rows):
        if not isinstance(raw, Mapping):
            findings.append({"code": "implementation_surface_mapping_row_invalid", "severity": "blocker", "message": f"surface map row {index} is not an object"})
            continue
        surface_id = str(raw.get("surface_id", ""))
        if not surface_id:
            findings.append({"code": "implementation_surface_mapping_surface_id_missing", "severity": "blocker", "message": f"surface map row {index} has no surface_id"})
            continue
        if surface_id in mapped_by_id:
            findings.append({"code": "implementation_surface_mapping_duplicate_id", "severity": "blocker", "surface_id": surface_id, "message": "surface map contains duplicate surface_id"})
            continue
        mapped_by_id[surface_id] = raw
    model_obligation_to_surfaces: dict[str, tuple[str, ...]] = {}
    model_obligation_dispositions: dict[str, str] = {}
    model_obligation_dispositions_allowed = {
        "governed",
        "model_only_proven",
        "retired_proven",
        "not_applicable_proven",
        "blocked_gap",
    }
    for index, raw in enumerate(model_obligation_rows):
        if not isinstance(raw, Mapping):
            findings.append({"code": "implementation_surface_model_obligation_row_invalid", "severity": "blocker", "message": f"model obligation row {index} is not an object"})
            continue
        obligation_id = str(raw.get("obligation_id", ""))
        if not obligation_id.strip():
            findings.append({"code": "implementation_surface_model_obligation_id_missing", "severity": "blocker", "message": f"model obligation row {index} has no obligation_id"})
            continue
        disposition = str(raw.get("disposition", "")).strip()
        if disposition not in model_obligation_dispositions_allowed:
            findings.append({"code": "implementation_surface_model_obligation_disposition_invalid", "severity": "blocker", "message": f"model obligation {obligation_id} needs one typed disposition"})
            disposition = ""
        model_obligation_dispositions[obligation_id] = disposition
        try:
            obligation_surface_ids = _surface_strings(raw.get("surface_ids", ()), context=f"model obligation {obligation_id}.surface_ids")
        except PublicBehaviorSurfaceAuditError as exc:
            obligation_surface_ids = ()
            findings.append({"code": "implementation_surface_model_obligation_surface_ids_invalid", "severity": "blocker", "message": str(exc)})
        if obligation_id in model_obligation_to_surfaces:
            findings.append({"code": "implementation_surface_model_obligation_duplicate_id", "severity": "blocker", "message": f"model obligation {obligation_id} is declared more than once"})
        model_obligation_to_surfaces[obligation_id] = obligation_surface_ids
        if disposition == "governed" and not obligation_surface_ids:
            findings.append({"code": "implementation_surface_model_obligation_surface_missing", "severity": "blocker", "message": f"governed model obligation {obligation_id} has no surface binding"})
        if disposition == "blocked_gap":
            if obligation_surface_ids:
                findings.append({"code": "implementation_surface_model_obligation_blocked_gap_has_surface", "severity": "blocker", "message": f"blocked-gap model obligation {obligation_id} must not point to an implementation surface"})
            if not str(raw.get("gap_reason", "")).strip():
                findings.append({"code": "implementation_surface_model_obligation_blocked_gap_reason_missing", "severity": "blocker", "message": f"blocked-gap model obligation {obligation_id} needs an explicit gap_reason"})
        elif disposition in {"model_only_proven", "retired_proven", "not_applicable_proven"}:
            if obligation_surface_ids:
                findings.append({"code": "implementation_surface_model_obligation_typed_proof_has_surface", "severity": "blocker", "message": f"typed non-governed model obligation {obligation_id} must not point to an implementation surface"})
            if not str(raw.get("proof_ref", "")).strip() or not str(raw.get("reason", "")).strip():
                findings.append({"code": "implementation_surface_model_obligation_typed_proof_missing", "severity": "blocker", "message": f"typed model obligation {obligation_id} needs proof_ref and reason"})
            else:
                proof_ok, proof_reason = _proof_reference_exists(bounded_root, str(raw.get("proof_ref")))
                if not proof_ok:
                    findings.append({"code": "implementation_surface_model_obligation_typed_proof_orphan", "severity": "blocker", "message": f"typed model obligation {obligation_id} proof reference is not current: {proof_reason}"})
    result["model_obligation_inventory_count"] = len(model_obligation_to_surfaces)
    current_ledger_intent_ids: set[str] = set()
    current_ledger_obligation_ids: set[str] = set()
    current_ledger_obligation_bindings: dict[str, Mapping[str, Any]] = {}
    if current_behavior_ledger_join_valid:
        current_ledger_intent_ids = {
            str(value).strip()
            for value in current_behavior_ledger_join.get("intent_ids", ())
            if str(value).strip()
        }
        current_ledger_obligation_ids = {
            str(value).strip()
            for value in current_behavior_ledger_join.get(
                "model_obligation_ids", ()
            )
            if str(value).strip()
        }
        result["current_model_obligation_ids"] = sorted(
            current_ledger_obligation_ids
        )
        for binding in current_behavior_ledger_join.get(
            "commitment_bindings", ()
        ):
            if not isinstance(binding, Mapping):
                continue
            for obligation_id in binding.get("model_obligation_ids", ()):
                current_ledger_obligation_bindings[str(obligation_id)] = binding
        for obligation_id, disposition in sorted(
            model_obligation_dispositions.items()
        ):
            if disposition in {"governed", "model_only_proven", "blocked_gap"} and obligation_id not in current_ledger_obligation_ids:
                findings.append(
                    {
                        "code": "implementation_surface_model_obligation_current_unknown",
                        "severity": "blocker",
                        "message": (
                            f"current governed/model-only obligation {obligation_id} "
                            "is not present in the native current behavior ledger"
                        ),
                    }
                )
            if disposition == "governed":
                raw_row = next(
                    (
                        row
                        for row in model_obligation_rows
                        if isinstance(row, Mapping)
                        and str(row.get("obligation_id", "")).strip()
                        == obligation_id
                    ),
                    {},
                )
                if not str(raw_row.get("intent_id", "")).strip():
                    findings.append(
                        {
                            "code": "implementation_surface_model_obligation_intent_missing",
                            "severity": "blocker",
                            "message": (
                                f"governed model obligation {obligation_id} needs "
                                "the current ledger intent_id"
                            ),
                        }
                    )
                if not str(raw_row.get("model_owner_id", "")).strip():
                    findings.append(
                        {
                            "code": "implementation_surface_model_obligation_owner_missing",
                            "severity": "blocker",
                            "message": (
                                f"governed model obligation {obligation_id} needs "
                                "the current logical model_owner_id"
                            ),
                        }
                    )
                binding = current_ledger_obligation_bindings.get(obligation_id)
                if isinstance(binding, Mapping):
                    if str(raw_row.get("intent_id", "")).strip() != str(
                        binding.get("intent_id", "")
                    ).strip():
                        findings.append(
                            {
                                "code": "implementation_surface_model_obligation_intent_mismatch",
                                "severity": "blocker",
                                "message": (
                                    f"model obligation {obligation_id} does not use "
                                    "the current ledger intent binding"
                                ),
                            }
                        )
                    if str(raw_row.get("model_owner_id", "")).strip() != str(
                        binding.get("model_owner_id", "")
                    ).strip():
                        findings.append(
                            {
                                "code": "implementation_surface_model_obligation_owner_mismatch",
                                "severity": "blocker",
                                "message": (
                                    f"model obligation {obligation_id} does not use "
                                    "the current ledger model-owner binding"
                                ),
                            }
                        )
    discovered_ids = set(discovered_by_id)
    mapped_ids = set(mapped_by_id)
    result["mapped_surface_ids"] = sorted(discovered_ids & mapped_ids)
    result["unmapped_surface_ids"] = sorted(discovered_ids - mapped_ids)
    result["orphan_mapping_surface_ids"] = sorted(mapped_ids - discovered_ids)
    for surface_id in sorted(discovered_ids - mapped_ids):
        findings.append({"code": "implementation_surface_mapping_missing", "severity": "blocker", "surface_id": surface_id, "message": "discovered production surface has no independently authored mapping"})
    for surface_id in sorted(mapped_ids - discovered_ids):
        findings.append({"code": "implementation_surface_mapping_orphan", "severity": "blocker", "surface_id": surface_id, "message": "surface map row does not resolve to a current production observation"})
    obligation_reverse_surface_ids: set[str] = set()
    for obligation_id, obligation_surface_ids in sorted(model_obligation_to_surfaces.items()):
        if len(obligation_surface_ids) != len(set(obligation_surface_ids)):
            findings.append(
                {
                    "code": "implementation_surface_model_obligation_surface_duplicate",
                    "severity": "blocker",
                    "message": f"model obligation {obligation_id} lists a surface more than once",
                }
            )
        if model_obligation_dispositions.get(obligation_id) == "governed" and not obligation_surface_ids:
            findings.append({"code": "implementation_surface_model_obligation_surface_missing", "severity": "blocker", "message": f"governed model obligation {obligation_id} has no surface binding"})
        for surface_id in obligation_surface_ids:
            obligation_reverse_surface_ids.add(surface_id)
            if surface_id not in discovered_ids:
                result["orphan_model_obligation_surface_ids"].append(surface_id)
                findings.append({"code": "implementation_surface_model_obligation_orphan_surface", "severity": "blocker", "surface_id": surface_id, "message": f"model obligation {obligation_id} references an undiscovered surface"})
                continue
            mapped_surface = mapped_by_id.get(surface_id)
            mapped_disposition = (
                mapped_surface.get("disposition")
                if isinstance(mapped_surface, Mapping)
                else None
            )
            if model_obligation_dispositions.get(obligation_id) == "governed" and mapped_disposition not in {
                IMPLEMENTATION_SURFACE_DISPOSITION_GOVERNED,
                IMPLEMENTATION_SURFACE_DISPOSITION_INTERNAL_PROVEN,
            }:
                findings.append(
                    {
                        "code": "implementation_surface_model_obligation_surface_disposition_mismatch",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "message": (
                            f"governed model obligation {obligation_id} points to a "
                            f"surface with disposition {mapped_disposition!r}"
                        ),
                    }
                )
            if isinstance(mapped_surface, Mapping) and mapped_disposition in {
                IMPLEMENTATION_SURFACE_DISPOSITION_GOVERNED,
                IMPLEMENTATION_SURFACE_DISPOSITION_INTERNAL_PROVEN,
            }:
                try:
                    mapped_obligation_ids = _surface_strings(
                        mapped_surface.get("model_obligation_ids", ()),
                        context=f"surface {surface_id}.model_obligation_ids",
                    )
                except PublicBehaviorSurfaceAuditError:
                    mapped_obligation_ids = ()
                if obligation_id not in mapped_obligation_ids:
                    findings.append(
                        {
                            "code": "implementation_surface_model_obligation_reverse_mismatch",
                            "severity": "blocker",
                            "surface_id": surface_id,
                            "message": (
                                f"model obligation {obligation_id} does not point "
                                "back from its mapped surface"
                            ),
                        }
                    )
    for surface_id in sorted(discovered_ids & mapped_ids):
        observed_row = discovered_by_id[surface_id]
        mapped = mapped_by_id[surface_id]
        for legacy_field in sorted(
            _IMPLEMENTATION_SURFACE_LEGACY_FIELDS & set(mapped)
        ):
            findings.append(
                {
                    "code": "implementation_surface_legacy_field_forbidden",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "field": legacy_field,
                    "message": (
                        f"reverse surface map field {legacy_field!r} is retired; "
                        "use the current canonical field and do not fall back"
                    ),
                }
            )
        disposition = mapped.get("disposition")
        observed_class = str(observed_row.get("surface_class", "")).strip()
        expected_class = _surface_class_for_kind(str(observed_row.get("surface_kind", "")))
        if observed_class not in IMPLEMENTATION_SURFACE_CLASSES:
            findings.append(
                {
                    "code": "implementation_surface_class_missing_or_unknown",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": "every source observation needs one known stable surface_class",
                }
            )
        elif expected_class and observed_class != expected_class:
            findings.append(
                {
                    "code": "implementation_surface_class_mismatch",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": f"surface_class {observed_class!r} does not match surface_kind {observed_row.get('surface_kind')!r}",
                }
            )
        if disposition not in IMPLEMENTATION_SURFACE_DISPOSITIONS:
            findings.append({"code": "implementation_surface_disposition_invalid", "severity": "blocker", "surface_id": surface_id, "message": f"unknown implementation surface disposition: {disposition!r}"})
        # A current source boundary must not leave dynamic/plugin,
        # placeholder, or unreachable observations in a typed N/A or blocked
        # state.  Those states describe missing adjudication, not a resolved
        # product boundary.  The only accepted current closures are governed,
        # internal_proven, or retired_proven with their own evidence.
        observed_kind = str(observed_row.get("surface_kind", "")).strip()
        if (
            observed_kind
            in {"dynamic", "plugin", "placeholder", "unreachable_or_unbound"}
            and disposition
            in {
                IMPLEMENTATION_SURFACE_DISPOSITION_NOT_APPLICABLE_PROVEN,
                IMPLEMENTATION_SURFACE_DISPOSITION_BLOCKED_GAP,
            }
        ):
            code_stem = {
                "dynamic": "dynamic",
                "plugin": "plugin",
                "placeholder": "placeholder",
                "unreachable_or_unbound": "unbound",
            }[observed_kind]
            findings.append(
                {
                    "code": f"implementation_surface_{code_stem}_current_disposition_required",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": (
                        f"{observed_kind} implementation observation must be "
                        "closed by a current governed, internal_proven, or "
                        "retired_proven disposition; N/A and blocked_gap are "
                        "not current closure"
                    ),
                }
            )
        owner = mapped.get("owner")
        owner_values: tuple[str, ...] = ()
        try:
            owner_values = _owner_values(owner, context=f"surface {surface_id}.owner")
        except PublicBehaviorSurfaceAuditError as exc:
            findings.append(
                {
                    "code": "implementation_surface_owner_missing",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": str(exc),
                }
            )
        if not isinstance(owner, str):
            if len(owner_values) == 1:
                findings.append(
                    {
                        "code": "implementation_surface_owner_ambiguous",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "message": "canonical owner must be one scalar string, not a list-shaped alias",
                    }
                )
                owner_values = ()
        if len(owner_values) == 0:
            findings.append({"code": "implementation_surface_owner_missing", "severity": "blocker", "surface_id": surface_id, "message": "every observed implementation surface needs one explicit owner"})
        elif len(owner_values) > 1:
            result["duplicate_primary_owner_surface_ids"].append(surface_id)
            findings.append(
                {
                    "code": "implementation_surface_primary_owner_duplicate",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": "one implementation surface cannot claim multiple primary owners",
                }
            )

        # Keep accidental plural owner fields visible instead of silently
        # ignoring them.  The canonical map field remains ``owner``; these
        # aliases are accepted only as a diagnostic shape so a malformed
        # producer receives a deterministic blocker rather than a false pass.
        for owner_field in ("owner_ids", "owners", "primary_owner_ids", "primary_owners"):
            if owner_field not in mapped:
                continue
            try:
                declared_owner_values = _owner_values(
                    mapped.get(owner_field),
                    context=f"surface {surface_id}.{owner_field}",
                )
            except PublicBehaviorSurfaceAuditError as exc:
                findings.append(
                    {
                        "code": "implementation_surface_primary_owner_duplicate",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "message": str(exc),
                    }
                )
                continue
            if len(declared_owner_values) != 1:
                if len(declared_owner_values) > 1:
                    result["duplicate_primary_owner_surface_ids"].append(surface_id)
                    code = "implementation_surface_primary_owner_duplicate"
                    message = "one implementation surface cannot claim multiple primary owners"
                else:
                    code = "implementation_surface_owner_missing"
                    message = f"{owner_field} cannot be empty"
                findings.append(
                    {
                        "code": code,
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "message": message,
                    }
                )
            elif owner_values and declared_owner_values[0] != owner_values[0]:
                findings.append(
                    {
                        "code": "implementation_surface_primary_owner_mismatch",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "message": f"{owner_field} does not match the canonical owner field",
                    }
                )
        # Only the current plural field is accepted.  Singular/legacy aliases
        # are reported above and intentionally do not contribute evidence.
        raw_receipt_refs = mapped.get("receipt_refs", ())
        try:
            normalized_receipt_refs = _surface_strings(
                raw_receipt_refs,
                context=f"surface {surface_id}.receipt_refs",
            )
        except PublicBehaviorSurfaceAuditError as exc:
            normalized_receipt_refs = ()
            findings.append(
                {
                    "code": "implementation_surface_receipt_missing",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": str(exc),
                }
            )
        # A typed blocker is already a visible failure, but any disposition
        # that claims a source surface is internally/externally closed must
        # cite a current terminal receipt.  A proof_ref alone is not an
        # execution receipt and cannot make a governed row green.
        if disposition != IMPLEMENTATION_SURFACE_DISPOSITION_BLOCKED_GAP and not normalized_receipt_refs:
            findings.append(
                {
                    "code": "implementation_surface_receipt_missing",
                    "severity": "blocker",
                    "surface_id": surface_id,
                    "message": "every non-blocked implementation surface needs at least one explicit terminal receipt reference",
                }
            )
        for reference in normalized_receipt_refs:
            receipt_ok, receipt_reason = _receipt_reference_exists(bounded_root, reference)
            if not receipt_ok:
                result["orphan_receipt_references"].append(reference)
                findings.append(
                    {
                        "code": "implementation_surface_orphan_receipt_reference",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "receipt_ref": reference,
                        "message": receipt_reason,
                    }
                )
        # Do not reinterpret a retired ``tests`` alias as current coverage.
        test_refs = mapped.get("test_refs", ())
        try:
            normalized_test_refs = _surface_strings(test_refs, context=f"surface {surface_id}.test_refs")
        except PublicBehaviorSurfaceAuditError as exc:
            normalized_test_refs = ()
            findings.append({"code": "implementation_surface_test_missing", "severity": "blocker", "surface_id": surface_id, "message": str(exc)})
        if not normalized_test_refs:
            findings.append({"code": "implementation_surface_test_missing", "severity": "blocker", "surface_id": surface_id, "message": "every observed implementation surface needs at least one explicit test reference"})
        for reference in normalized_test_refs:
            exists, reason = _test_reference_exists(bounded_root, reference)
            if not exists:
                result["orphan_test_references"].append(reference)
                findings.append(
                    {
                        "code": "implementation_surface_test_empty" if reason == "test reference target is empty" else "implementation_surface_orphan_test_reference",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "test_ref": reference,
                        "message": reason,
                    }
                )
        intent_id = mapped.get("intent_id")
        model_owner_id = mapped.get("model_owner_id")
        # When this is a modeled FlowGuard target, a scalar owner and a
        # receipt path are not enough to establish currentness.  Join every
        # non-blocked row to the exact current native owner receipt and model
        # owner set.  A missing or stale tuple blocks; it never falls back to
        # the older path-anchor-only check.
        if current_authority_join is not None and current_authority_join_valid:
            current_model_owner_ids = {
                str(item)
                for item in current_authority_join.get("model_owner_ids", ())
                if str(item).strip()
            }
            if disposition in {
                IMPLEMENTATION_SURFACE_DISPOSITION_GOVERNED,
                IMPLEMENTATION_SURFACE_DISPOSITION_INTERNAL_PROVEN,
            } and str(model_owner_id).strip() not in current_model_owner_ids:
                findings.append(
                    {
                        "code": "implementation_surface_current_model_owner_unknown",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "message": (
                            "surface model_owner_id is not present in the native "
                            "current observed model owner set"
                        ),
                    }
                )
            if disposition != IMPLEMENTATION_SURFACE_DISPOSITION_BLOCKED_GAP:
                owner_route = owner_values[0] if len(owner_values) == 1 else ""
                owner_receipt_id = str(mapped.get("owner_receipt_id", "")).strip()
                owner_receipt_fingerprint = str(
                    mapped.get("owner_receipt_fingerprint", "")
                ).strip()
                if not owner_receipt_id or not owner_receipt_fingerprint:
                    findings.append(
                        {
                            "code": "implementation_surface_current_owner_receipt_missing",
                            "severity": "blocker",
                            "surface_id": surface_id,
                            "message": (
                                "non-blocked surface needs the exact current "
                                "native owner receipt id and fingerprint"
                            ),
                        }
                    )
                elif not _CURRENT_IDENTITY_FINGERPRINT_RE.fullmatch(
                    owner_receipt_fingerprint
                ):
                    findings.append(
                        {
                            "code": "implementation_surface_current_owner_receipt_invalid",
                            "severity": "blocker",
                            "surface_id": surface_id,
                            "message": "owner_receipt_fingerprint is not canonical sha256",
                        }
                    )
                else:
                    current_owner_receipt = {
                        (
                            str(item.get("owner_route", "")),
                            str(item.get("receipt_id", "")),
                            str(item.get("receipt_fingerprint", "")),
                        )
                        for item in current_authority_join.get(
                            "owner_receipt_identities", ()
                        )
                        if isinstance(item, Mapping)
                    }
                    if (
                        owner_route,
                        owner_receipt_id,
                        owner_receipt_fingerprint,
                    ) not in current_owner_receipt:
                        findings.append(
                            {
                                "code": "implementation_surface_current_owner_receipt_mismatch",
                                "severity": "blocker",
                                "surface_id": surface_id,
                                "message": (
                                    "surface owner does not join to one exact "
                                    "current native owner receipt"
                                ),
                            }
                        )
        intent_id = mapped.get("intent_id")
        model_owner_id = mapped.get("model_owner_id")
        model_owner_values: tuple[str, ...] = ()
        try:
            model_owner_values = _owner_values(
                model_owner_id,
                context=f"surface {surface_id}.model_owner_id",
            )
        except PublicBehaviorSurfaceAuditError:
            # The normal missing-owner diagnostic below carries the stable
            # surface-level code.  Plural model-owner aliases receive their
            # own explicit duplicate finding below.
            model_owner_values = ()
        if not isinstance(model_owner_id, str):
            if len(model_owner_values) == 1:
                findings.append(
                    {
                        "code": "implementation_surface_model_owner_ambiguous",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "message": "canonical model_owner_id must be one scalar string, not a list-shaped alias",
                    }
                )
                model_owner_values = ()
            elif len(model_owner_values) > 1:
                result["duplicate_primary_model_owner_surface_ids"].append(
                    surface_id
                )
                findings.append(
                    {
                        "code": "implementation_surface_primary_model_owner_duplicate",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "message": "one implementation surface cannot claim multiple primary model owners",
                    }
                )
        for model_owner_field in ("model_owner_ids", "primary_model_owner_ids"):
            if model_owner_field not in mapped:
                continue
            try:
                declared_model_owner_values = _owner_values(
                    mapped.get(model_owner_field),
                    context=f"surface {surface_id}.{model_owner_field}",
                )
            except PublicBehaviorSurfaceAuditError as exc:
                findings.append(
                    {
                        "code": "implementation_surface_primary_model_owner_duplicate",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "message": str(exc),
                    }
                )
                continue
            if len(declared_model_owner_values) != 1:
                if len(declared_model_owner_values) > 1:
                    result["duplicate_primary_model_owner_surface_ids"].append(surface_id)
                    code = "implementation_surface_primary_model_owner_duplicate"
                    message = "one implementation surface cannot claim multiple primary model owners"
                else:
                    code = "implementation_surface_model_owner_missing"
                    message = f"{model_owner_field} cannot be empty"
                findings.append(
                    {
                        "code": code,
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "message": message,
                    }
                )
            elif model_owner_values and declared_model_owner_values[0] != model_owner_values[0]:
                findings.append(
                    {
                        "code": "implementation_surface_primary_model_owner_mismatch",
                        "severity": "blocker",
                        "surface_id": surface_id,
                        "message": f"{model_owner_field} does not match the canonical model_owner_id field",
                    }
                )
        if disposition in {IMPLEMENTATION_SURFACE_DISPOSITION_GOVERNED, IMPLEMENTATION_SURFACE_DISPOSITION_INTERNAL_PROVEN}:
            if not isinstance(intent_id, str) or not intent_id.strip():
                findings.append({"code": "implementation_surface_intent_mapping_missing", "severity": "blocker", "surface_id": surface_id, "message": "governed/internal_proven surface has no intent_id"})
            if len(model_owner_values) != 1:
                findings.append({"code": "implementation_surface_model_owner_missing", "severity": "blocker", "surface_id": surface_id, "message": "governed/internal_proven surface has no model_owner_id"})
            try:
                model_obligation_ids = _surface_strings(mapped.get("model_obligation_ids", ()), context=f"surface {surface_id}.model_obligation_ids")
            except PublicBehaviorSurfaceAuditError as exc:
                model_obligation_ids = ()
                findings.append({"code": "implementation_surface_model_obligation_mapping_missing", "severity": "blocker", "surface_id": surface_id, "message": str(exc)})
            if not model_obligation_ids:
                findings.append({"code": "implementation_surface_model_obligation_mapping_missing", "severity": "blocker", "surface_id": surface_id, "message": "governed/internal_proven surface has no model_obligation_ids"})
            else:
                for obligation_id in model_obligation_ids:
                    if obligation_id not in model_obligation_to_surfaces:
                        findings.append({"code": "implementation_surface_model_obligation_unknown", "severity": "blocker", "surface_id": surface_id, "message": f"surface references unknown model obligation {obligation_id}"})
                    elif model_obligation_dispositions.get(obligation_id) != "governed":
                        findings.append(
                            {
                                "code": "implementation_surface_model_obligation_disposition_mismatch",
                                "severity": "blocker",
                                "surface_id": surface_id,
                                "message": (
                                    f"implementation surface {surface_id} is governed "
                                    f"but model obligation {obligation_id} is typed "
                                    f"{model_obligation_dispositions.get(obligation_id)!r}"
                                ),
                            }
                        )
                    elif surface_id not in model_obligation_to_surfaces[obligation_id]:
                        findings.append({"code": "implementation_surface_model_obligation_reverse_mismatch", "severity": "blocker", "surface_id": surface_id, "message": f"model obligation {obligation_id} does not point back to this surface"})
            if current_behavior_ledger_join_valid:
                intent_text = str(intent_id or "").strip()
                if intent_text not in current_ledger_intent_ids:
                    findings.append(
                        {
                            "code": "implementation_surface_current_intent_unknown",
                            "severity": "blocker",
                            "surface_id": surface_id,
                            "message": (
                                f"surface intent_id {intent_text!r} is not present "
                                "in the native current behavior ledger"
                            ),
                        }
                    )
                for obligation_id in model_obligation_ids:
                    if obligation_id not in current_ledger_obligation_ids:
                        findings.append(
                            {
                                "code": "implementation_surface_model_obligation_current_unknown",
                                "severity": "blocker",
                                "surface_id": surface_id,
                                "message": (
                                    f"surface model obligation {obligation_id!r} "
                                    "is not present in the native current behavior ledger"
                                ),
                            }
                        )
                        continue
                    binding = current_ledger_obligation_bindings.get(obligation_id)
                    if not isinstance(binding, Mapping):
                        findings.append(
                            {
                                "code": "implementation_surface_model_obligation_current_binding_missing",
                                "severity": "blocker",
                                "surface_id": surface_id,
                                "message": (
                                    f"current ledger obligation {obligation_id!r} "
                                    "has no commitment binding"
                                ),
                            }
                        )
                        continue
                    if intent_text != str(binding.get("intent_id", "")).strip():
                        findings.append(
                            {
                                "code": "implementation_surface_current_intent_obligation_mismatch",
                                "severity": "blocker",
                                "surface_id": surface_id,
                                "message": (
                                    f"surface intent_id {intent_text!r} does not match "
                                    f"the current ledger intent for obligation {obligation_id!r}"
                                ),
                            }
                        )
                    expected_model_owner_id = str(
                        binding.get("model_owner_id", "")
                    ).strip()
                    if (
                        len(model_owner_values) == 1
                        and model_owner_values[0] != expected_model_owner_id
                    ):
                        findings.append(
                            {
                                "code": "implementation_surface_current_model_owner_obligation_mismatch",
                                "severity": "blocker",
                                "surface_id": surface_id,
                                "message": (
                                    f"surface model_owner_id {model_owner_values[0]!r} "
                                    f"does not match the current ledger owner {expected_model_owner_id!r} "
                                    f"for obligation {obligation_id!r}"
                                ),
                            }
                        )
        if disposition == IMPLEMENTATION_SURFACE_DISPOSITION_RETIRED_PROVEN:
            proof_ref = str(mapped.get("proof_ref", "")).strip()
            proof_reason = str(mapped.get("reason", "")).strip()
            if not proof_ref or not proof_reason:
                findings.append({"code": "implementation_surface_retirement_proof_missing", "severity": "blocker", "surface_id": surface_id, "message": "retired_proven surface needs a current proof reference and explicit reason"})
            else:
                proof_ok, proof_reason = _proof_reference_exists(bounded_root, proof_ref)
                if not proof_ok:
                    findings.append({"code": "implementation_surface_retirement_proof_orphan", "severity": "blocker", "surface_id": surface_id, "message": f"retired_proven surface proof reference is not current: {proof_reason}"})
        if disposition == IMPLEMENTATION_SURFACE_DISPOSITION_INTERNAL_PROVEN:
            proof_ref = str(mapped.get("proof_ref", "")).strip()
            proof_reason = str(mapped.get("reason", "")).strip()
            if not proof_ref or not proof_reason:
                findings.append({"code": "implementation_surface_internal_proof_missing", "severity": "blocker", "surface_id": surface_id, "message": "internal_proven surface needs a current proof reference and explicit reason"})
            else:
                proof_ok, proof_reason_detail = _proof_reference_exists(bounded_root, proof_ref)
                if not proof_ok:
                    findings.append({"code": "implementation_surface_internal_proof_orphan", "severity": "blocker", "surface_id": surface_id, "message": f"internal_proven surface proof reference is not current: {proof_reason_detail}"})
        if disposition == IMPLEMENTATION_SURFACE_DISPOSITION_NOT_APPLICABLE_PROVEN:
            proof_ref = str(mapped.get("proof_ref", "")).strip()
            reason = str(mapped.get("not_applicable_reason", "")).strip()
            if not proof_ref or not reason:
                findings.append({"code": "implementation_surface_not_applicable_proof_missing", "severity": "blocker", "surface_id": surface_id, "message": "not_applicable_proven surface needs a proof_ref and explicit reason"})
            else:
                proof_ok, proof_reason = _proof_reference_exists(bounded_root, proof_ref)
                if not proof_ok:
                    findings.append({"code": "implementation_surface_not_applicable_proof_orphan", "severity": "blocker", "surface_id": surface_id, "message": f"not_applicable_proven surface proof reference is not current: {proof_reason}"})
        if disposition == IMPLEMENTATION_SURFACE_DISPOSITION_BLOCKED_GAP:
            findings.append({"code": "implementation_surface_blocked_gap", "severity": "blocker", "surface_id": surface_id, "message": "blocked_gap remains a visible reverse-closure blocker"})
            if not str(mapped.get("gap_reason", "")).strip():
                findings.append({"code": "implementation_surface_blocked_gap_reason_missing", "severity": "blocker", "surface_id": surface_id, "message": "blocked_gap needs an explicit gap_reason"})
        if observed_row.get("surface_kind") == "ui_like_action":
            if disposition not in {IMPLEMENTATION_SURFACE_DISPOSITION_GOVERNED, IMPLEMENTATION_SURFACE_DISPOSITION_INTERNAL_PROVEN} or not str(intent_id).strip() or not str(model_owner_id).strip():
                result["unmodeled_ui_like_action_ids"].append(surface_id)
                findings.append({"code": "implementation_surface_unmodeled_ui_like_action", "severity": "blocker", "surface_id": surface_id, "message": "UI-like action is not closed to an explicit intent and model owner"})
    result["orphan_test_references"] = sorted(set(result["orphan_test_references"]))
    result["orphan_receipt_references"] = sorted(set(result["orphan_receipt_references"]))
    result["orphan_model_obligation_surface_ids"] = sorted(set(result["orphan_model_obligation_surface_ids"]))
    result["duplicate_primary_owner_surface_ids"] = sorted(set(result["duplicate_primary_owner_surface_ids"]))
    result["duplicate_primary_model_owner_surface_ids"] = sorted(
        set(result["duplicate_primary_model_owner_surface_ids"])
    )
    governed_surface_ids = {
        surface_id
        for surface_id, mapped in mapped_by_id.items()
        if mapped.get("disposition") in {IMPLEMENTATION_SURFACE_DISPOSITION_GOVERNED, IMPLEMENTATION_SURFACE_DISPOSITION_INTERNAL_PROVEN}
    }
    result["unmapped_model_obligation_ids"] = sorted(
        obligation_id
        for obligation_id, surface_ids in model_obligation_to_surfaces.items()
        if model_obligation_dispositions.get(obligation_id) == "governed"
        and not (set(surface_ids) & discovered_ids)
    )
    for surface_id in sorted((discovered_ids & mapped_ids) & governed_surface_ids - obligation_reverse_surface_ids):
        findings.append({"code": "implementation_surface_model_obligation_unmapped", "severity": "blocker", "surface_id": surface_id, "message": "governed/internal_proven surface is absent from the reverse model-obligation inventory"})
    result["unmodeled_ui_like_action_ids"] = sorted(set(result["unmodeled_ui_like_action_ids"]))
    result["findings"] = sorted(findings, key=lambda item: (item.get("surface_id", ""), item.get("code", ""), item.get("message", "")))
    result["status"] = "passed" if not any(item.get("severity") == "blocker" for item in result["findings"]) else "blocked"
    result["reverse_closure_complete"] = result["status"] == "passed"
    result["evidence_fingerprint"] = _surface_hash(result)
    return result


def _compact_count_map(values: Any, *, key: str = "code") -> dict[str, int]:
    """Return deterministic counts without copying the source rows."""

    counts: dict[str, int] = {}
    if isinstance(values, (list, tuple)):
        for value in values:
            if isinstance(value, Mapping):
                item = str(value.get(key, "")).strip() or "<missing>"
            else:
                item = "<invalid>"
            counts[item] = counts.get(item, 0) + 1
    return dict(sorted(counts.items()))


def _compact_finding_samples(
    values: Any,
    *,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """Keep only stable, small finding samples for terminal output."""

    rows = [dict(value) for value in values if isinstance(value, Mapping)] \
        if isinstance(values, (list, tuple)) else []
    rows.sort(
        key=lambda row: (
            str(row.get("surface_id", "")),
            str(row.get("code", "")),
            str(row.get("message", "")),
        )
    )
    bounded = max(0, int(limit))
    samples: list[dict[str, Any]] = []
    for row in rows[:bounded]:
        # Messages and identity fields are useful at the terminal.  Do not
        # accidentally re-emit a large nested row or source excerpt.
        sample: dict[str, Any] = {}
        for field in ("code", "severity", "surface_id", "surface_class", "field", "message"):
            if field in row and isinstance(row[field], (str, int, float, bool)):
                sample[field] = row[field]
        samples.append(sample)
    return samples, max(0, len(rows) - len(samples))


def compact_implementation_behavior_surface_audit(
    discovery: Mapping[str, Any],
    audit: Mapping[str, Any],
    *,
    discovery_artifact: str = "",
    surface_map_artifact: str = "",
    full_artifact: str = "",
    max_finding_samples: int = 20,
) -> dict[str, Any]:
    """Build a deterministic, bounded terminal projection.

    This function deliberately does not include ``surfaces``, ``call_graph``,
    ``component_groups``, semantic rows, or full findings.  Consumers needing
    those rows must open the explicitly named full artifact.  No hash or
    second scan is performed here.
    """

    discovery_findings = discovery.get("findings", ())
    audit_findings = audit.get("findings", ())
    discovery_samples, discovery_omitted = _compact_finding_samples(
        discovery_findings, limit=max_finding_samples
    )
    audit_samples, audit_omitted = _compact_finding_samples(
        audit_findings, limit=max_finding_samples
    )
    call_graph = discovery.get("call_graph", ())
    resolution_counts: dict[str, int] = {}
    if isinstance(call_graph, (list, tuple)):
        for edge in call_graph:
            resolution = (
                str(edge.get("resolution", "")).strip() or "<missing>"
                if isinstance(edge, Mapping)
                else "<invalid>"
            )
            resolution_counts[resolution] = resolution_counts.get(resolution, 0) + 1
    refs = {
        name: str(value)
        for name, value in (
            ("discovery", discovery_artifact),
            ("surface_map", surface_map_artifact),
            ("full_audit", full_artifact),
        )
        if str(value).strip()
    }
    return {
        "schema_version": IMPLEMENTATION_SURFACE_AUDIT_COMPACT_SCHEMA,
        "claim_boundary": (
            "Bounded terminal projection only. Full discovery and audit JSON "
            "artifacts remain the sole current evidence authorities."
        ),
        "artifact_refs": refs,
        "discovery": {
            "status": discovery.get("status"),
            "discovery_fingerprint": discovery.get("discovery_fingerprint", ""),
            "source_count": len(discovery.get("source_paths", ()))
            if isinstance(discovery.get("source_paths", ()), (list, tuple))
            else 0,
            "surface_count": int(discovery.get("surface_count", len(discovery.get("surfaces", ()))) or 0),
            "call_graph_count": len(call_graph) if isinstance(call_graph, (list, tuple)) else 0,
            "external_contract_count": len(discovery.get("external_contracts", ()))
            if isinstance(discovery.get("external_contracts", ()), (list, tuple))
            else 0,
            "unbound_observation_count": len(discovery.get("unbound_surface_ids", ()))
            if isinstance(discovery.get("unbound_surface_ids", ()), (list, tuple))
            else 0,
            "finding_count": len(discovery_findings)
            if isinstance(discovery_findings, (list, tuple))
            else 0,
            "finding_code_counts": _compact_count_map(discovery_findings),
            "call_resolution_counts": dict(sorted(resolution_counts.items())),
            "finding_samples": discovery_samples,
            "omitted_finding_count": discovery_omitted,
        },
        "audit": {
            "status": audit.get("status"),
            "currentness_profile": audit.get("currentness_profile", "full"),
            "reverse_closure_complete": bool(audit.get("reverse_closure_complete")),
            "discovered_surface_count": int(audit.get("discovered_surface_count", 0) or 0),
            "mapping_input_surface_row_count": int(audit.get("mapping_input_surface_row_count", 0) or 0),
            "mapping_surface_count": int(audit.get("mapping_surface_count", 0) or 0),
            "mapping_component_group_count": int(audit.get("mapping_component_group_count", 0) or 0),
            "mapping_component_group_member_count": int(audit.get("mapping_component_group_member_count", 0) or 0),
            "surface_group_count": int(audit.get("surface_group_count", 0) or 0),
            "component_grouped_surface_count": int(audit.get("component_grouped_surface_count", 0) or 0),
            "individual_surface_count": int(audit.get("individual_surface_count", 0) or 0),
            "model_obligation_inventory_count": int(audit.get("model_obligation_inventory_count", 0) or 0),
            "unmapped_surface_count": len(audit.get("unmapped_surface_ids", ()))
            if isinstance(audit.get("unmapped_surface_ids", ()), (list, tuple))
            else 0,
            "orphan_mapping_surface_count": len(audit.get("orphan_mapping_surface_ids", ()))
            if isinstance(audit.get("orphan_mapping_surface_ids", ()), (list, tuple))
            else 0,
            "unmapped_model_obligation_count": len(audit.get("unmapped_model_obligation_ids", ()))
            if isinstance(audit.get("unmapped_model_obligation_ids", ()), (list, tuple))
            else 0,
            "unmodeled_ui_like_action_count": len(audit.get("unmodeled_ui_like_action_ids", ()))
            if isinstance(audit.get("unmodeled_ui_like_action_ids", ()), (list, tuple))
            else 0,
            "duplicate_primary_owner_count": len(audit.get("duplicate_primary_owner_surface_ids", ()))
            if isinstance(audit.get("duplicate_primary_owner_surface_ids", ()), (list, tuple))
            else 0,
            "finding_count": len(audit_findings)
            if isinstance(audit_findings, (list, tuple))
            else 0,
            "finding_code_counts": _compact_count_map(audit_findings),
            "finding_samples": audit_samples,
            "omitted_finding_count": audit_omitted,
            "current_authority_join_status": (audit.get("current_authority_join") or {}).get("status")
            if isinstance(audit.get("current_authority_join"), Mapping)
            else "not_required",
            "current_behavior_ledger_join_status": (audit.get("current_behavior_ledger_join") or {}).get("status")
            if isinstance(audit.get("current_behavior_ledger_join"), Mapping)
            else "not_required",
            "evidence_fingerprint": audit.get("evidence_fingerprint", ""),
        },
    }


# Friendly aliases for callers that use the shorter names in task plans.
discover_behavior_surface = discover_implementation_behavior_surfaces
audit_behavior_surface = audit_implementation_behavior_surface


__all__ = [
    "IMPLEMENTATION_SURFACE_AUDIT_SCHEMA",
    "IMPLEMENTATION_SURFACE_AUDIT_COMPACT_SCHEMA",
    "IMPLEMENTATION_SURFACE_CURRENTNESS_PROFILES",
    "IMPLEMENTATION_SURFACE_MAP_SCHEMA",
    "IMPLEMENTATION_SURFACE_SHARD_SCHEMA",
    "IMPLEMENTATION_SURFACE_SHARD_PLAN_SCHEMA",
    "IMPLEMENTATION_SURFACE_CURRENT_AUTHORITY_JOIN_SCHEMA",
    "IMPLEMENTATION_SURFACE_CURRENT_BEHAVIOR_LEDGER_JOIN_SCHEMA",
    "IMPLEMENTATION_SURFACE_CANDIDATE_REPORT_SCHEMA",
    "IMPLEMENTATION_SURFACE_DISPOSITION_GOVERNED",
    "IMPLEMENTATION_SURFACE_DISPOSITION_INTERNAL_PROVEN",
    "IMPLEMENTATION_SURFACE_DISPOSITION_RETIRED_PROVEN",
    "IMPLEMENTATION_SURFACE_DISPOSITION_NOT_APPLICABLE_PROVEN",
    "IMPLEMENTATION_SURFACE_DISPOSITION_BLOCKED_GAP",
    "IMPLEMENTATION_SURFACE_DISPOSITIONS",
    "IMPLEMENTATION_SURFACE_CLASSES",
    "IMPLEMENTATION_SURFACE_KINDS",
    "IMPLEMENTATION_SURFACE_COMPONENT_GROUP_MEMBER_KINDS",
    "IMPLEMENTATION_SURFACE_CANDIDATE_CLASSES",
    "PUBLIC_BEHAVIOR_CLAIM_BOUNDARY",
    "PUBLIC_BEHAVIOR_SURFACE_CLASSES",
    "PUBLIC_BEHAVIOR_SURFACE_GAP_SCHEMA",
    "PublicBehaviorSurfaceAuditError",
    "build_public_behavior_surface_gap_report",
    "discover_implementation_behavior_surfaces",
    "plan_implementation_surface_shards",
    "discover_implementation_surface_shard",
    "merge_implementation_surface_shards",
    "classify_implementation_surface_candidates",
    "validate_implementation_surface_candidate_report",
    "audit_implementation_behavior_surface",
    "compact_implementation_behavior_surface_audit",
    "discover_behavior_surface",
    "audit_behavior_surface",
]
