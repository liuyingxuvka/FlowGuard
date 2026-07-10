"""Deterministic native-integrated contracts for the FlowGuard skill suite.

The editable input is ``.skillguard/contract-source.json`` in each skill.
Generated SkillGuard records describe and gate FlowGuard-owned routes; they do
not create a second runtime controller and do not manufacture native evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .skill_suite import FLOWGUARD_SKILL_ROOT, validate_skill_suite


CONTRACT_SOURCE_SCHEMA = "flowguard.skill_contract_source.v1"
WORK_CONTRACT_SCHEMA = "skillguard.work_contract.v1"
CHECK_MANIFEST_SCHEMA = "skillguard.check_manifest.v1"
CONTRACT_SOURCE_FILE = ".skillguard/contract-source.json"
WORK_CONTRACT_FILE = ".skillguard/work-contract.json"
CHECK_MANIFEST_FILE = ".skillguard/check_manifest.json"
SHARED_CHECK_FILE = ".skillguard/check.py"
PROFILE_FILE = ".skillguard/skillguard_profile.json"
SKILL_CONTRACT_FILE = ".skillguard/skillguard_skill_contract.json"
EVIDENCE_RULES_FILE = ".skillguard/skillguard_evidence_rules.json"
CLOSURE_POLICY_FILE = ".skillguard/skillguard_closure_policy.json"
CONTROL_MANIFEST_FILE = ".skillguard/skillguard_manifest.json"
AI_JUDGMENT_FILE = ".skillguard/ai_judgments/current_ai_judgment.json"
EVIDENCE_MANIFEST_FILE = ".skillguard/evidence/current_evidence_manifest.json"
CURRENT_CHECK_REPORT_FILE = ".skillguard/reports/current_check_report.json"
CURRENT_CLOSURE_FILE = ".skillguard/reports/current_closure.json"
PROGRESS_LEDGER_FILE = ".skillguard/skillguard_progress_ledger.jsonl"
COMPILER_VERSION = "flowguard.skill_contract_compiler.v1"
PHASE_IDS = ("intake", "inventory", "execution", "checks", "closure")
PHASE_CHECKS = {
    "intake": ("check_route", "route"),
    "inventory": ("check_phase_order", "phase_order"),
    "execution": ("check_evidence", "evidence"),
    "checks": ("check_quality_floor", "quality_floor"),
    "closure": ("check_closure", "closure"),
}
OUTPUT_FIELDS = (
    "evidence",
    "failures",
    "blockers",
    "skipped_checks",
    "residual_risk",
    "claim_boundary",
    "typed_next_actions",
)
STRONG_KEYWORDS = (
    "must", "required", "shall", "do not", "never", "cannot", "block",
    "fail", "gate", "check", "test", "verify", "validate", "evidence",
    "closure", "output", "workflow", "route", "entrypoint", "native",
    "runtime", "release", "privacy", "必须", "禁止", "不要", "检查",
    "验证", "证据", "输出", "流程", "路线",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest().upper()


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "item"


def _identifier(value: str, *, limit: int = 64) -> str:
    return _slug(value).replace("-", "_")[:limit]


def _normalize(value: str, *, limit: int = 190) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", value)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -:\t")
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "."


def _requirement_slug(value: str, *, prefix: str, max_words: int = 8) -> str:
    words = re.findall(r"[A-Za-z0-9]+", value.lower())[:max_words]
    tail = "-".join(words) or _slug(value)[:48]
    return f"{prefix}.{tail or 'item'}"


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    fields: dict[str, str] = {}
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        fields[key.strip().lower()] = value
    return fields


def _heading_category(heading: str, body: str = "") -> str:
    haystack = f"{heading} {body}".lower()
    if "do not use" in haystack or "forbidden" in haystack or "shortcut" in haystack:
        return "non-use-boundary"
    if "use when" in haystack or "activation" in haystack or "entrypoint" in haystack:
        return "activation-boundary"
    if any(term in haystack for term in ("workflow", "mode", "route", "path")):
        return "workflow-route"
    if any(term in haystack for term in ("hard gate", "gate", "check", "test")):
        return "check-gate"
    if "evidence" in haystack or "fresh" in haystack:
        return "evidence"
    if "output" in haystack or "report" in haystack:
        return "output"
    if any(term in haystack for term in ("release", "publish", "version")):
        return "release"
    if any(term in haystack for term in ("privacy", "public", "secret")):
        return "public-boundary"
    if "closure" in haystack or "complete" in haystack:
        return "closure"
    return "target-rule"


def infer_source_requirements(skill_text: str) -> tuple[dict[str, Any], ...]:
    """Mirror the current SkillGuard target-lock requirement extraction."""

    requirements: dict[str, dict[str, Any]] = {}

    def add(requirement_id: str, category: str, summary: str, source_path: str = "SKILL.md") -> None:
        requirements.setdefault(
            requirement_id,
            {
                "requirement_id": requirement_id,
                "category": category,
                "summary": _normalize(summary),
                "source_path": source_path,
                "required": True,
            },
        )

    lower = skill_text.lower()
    if skill_text.strip():
        add("target.entrypoint.acceptance", "entrypoint", "The target skill entrypoint and hard gates must be represented by the runtime contract.")
    description = _frontmatter(skill_text).get("description", "")
    if description:
        add(_requirement_slug(description, prefix="target.description"), "entrypoint-description", f"The target skill description must be represented in the contract: {description}", "SKILL.md frontmatter")
    if "runtime contract mode" in lower or "runtime contract" in lower:
        add("skillguard.runtime_contract_mode", "runtime-contract", "Runtime contract work must enforce selected route, run record, phase evidence, checks, quality floors, and closure gates.")
    if "global router mode" in lower or "global router" in lower:
        add("skillguard.global_router_freshness", "global-router", "Global router work must enforce registry and managed prompt freshness before routing claims.")
    if "native route" in lower or "native check" in lower or "parallel route" in lower:
        add("skillguard.native_route_binding", "native-binding", "Native and hybrid contracts must bind the target skill's native route/check owner and must not create a parallel execution route.")
    if "hard gates" in lower or "required workflow" in lower:
        add("target.hard_gates", "quality-gate", "Declared hard gates and required workflow steps must be represented by checks and closure blockers.")
    if "deep contract mode" in lower or "target-specific" in lower or "coverage matrix" in lower:
        add("skillguard.deep_contract_mode", "deep-contract", "Deep contract work must extract target-specific rules and map them to checks, evidence, and closure blockers.")
    if "runtime lock" in lower or "target-local" in lower or "work-contract.json" in lower:
        add("skillguard.universal_target_lock", "runtime-lock", "Covered target skills must expose a target-local runtime lock before work starts and before closure.")

    active_heading = ""
    extracted = 0
    for line_number, raw in enumerate(skill_text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        heading_match = re.match(r"^(#{1,4})\s+(.+?)\s*$", stripped)
        if heading_match:
            active_heading = _normalize(heading_match.group(2), limit=90)
            heading_lower = active_heading.lower()
            if any(term in heading_lower for term in ("mode", "workflow", "route", "gate", "output", "evidence", "use when", "do not use")):
                category = _heading_category(active_heading)
                add(_requirement_slug(active_heading, prefix=f"target.{category}"), category, f"The target section '{active_heading}' must be represented by route, check, evidence, or closure coverage.", f"SKILL.md#L{line_number}")
            continue
        normalized = _normalize(stripped)
        if len(normalized) < 20:
            continue
        structured = bool(re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", raw))
        lowered = normalized.lower()
        if not structured and not any(keyword in lowered for keyword in STRONG_KEYWORDS):
            continue
        if active_heading.lower() in {"purpose", "context"} and not any(keyword in lowered for keyword in STRONG_KEYWORDS):
            continue
        category = _heading_category(active_heading, normalized)
        add(_requirement_slug(normalized, prefix=f"target.{category}"), category, normalized, f"SKILL.md#L{line_number}")
        extracted += 1
        if extracted >= 40:
            break
    return tuple(sorted(requirements.values(), key=lambda row: row["requirement_id"]))


def work_contract_hash(contract: Mapping[str, Any]) -> str:
    seed = dict(contract)
    seed["contract_hash"] = ""
    return _hash(seed)


def route_registry_hash() -> str:
    from .self_maintenance import default_flowguard_route_profiles
    from .route_topology import route_registry_hash as topology_registry_hash

    return topology_registry_hash(default_flowguard_route_profiles())


def load_contract_source(skill_dir: str | Path) -> dict[str, Any]:
    path = Path(skill_dir) / CONTRACT_SOURCE_FILE
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("contract source root must be an object")
    failures = validate_contract_source(value, Path(skill_dir))
    if failures:
        raise ValueError("; ".join(failures))
    return value


def validate_contract_source(source: Mapping[str, Any], skill_dir: Path | None = None) -> tuple[str, ...]:
    failures: list[str] = []
    allowed_fields = {
        "schema_version", "skill_id", "route_id", "route_role", "native_owner",
        "route_summary", "activation_keywords", "use_when", "do_not_use_when",
        "workflow", "native_checks", "source_requirements", "direct_references",
        "downstream_targets", "output_fields", "layout_profiles", "claim_boundary",
        "default_route",
    }
    for unknown in sorted(set(source) - allowed_fields):
        failures.append(f"unknown_contract_source_field:{unknown}")
    required_strings = ("skill_id", "route_id", "route_role", "native_owner", "route_summary", "claim_boundary")
    if source.get("schema_version") != CONTRACT_SOURCE_SCHEMA:
        failures.append("contract_source_schema_mismatch")
    for field_name in required_strings:
        if not isinstance(source.get(field_name), str) or not str(source.get(field_name)).strip():
            failures.append(f"missing_{field_name}")
    for field_name in ("activation_keywords", "use_when", "do_not_use_when", "workflow", "native_checks", "source_requirements", "output_fields"):
        if not isinstance(source.get(field_name), list) or not source.get(field_name):
            failures.append(f"missing_{field_name}")
    if source.get("route_role") not in {"kernel", "public_owner", "delegated_mode"}:
        failures.append("invalid_route_role")
    phases = [row.get("phase_id") for row in source.get("workflow", ()) if isinstance(row, Mapping)]
    if sorted(phases) != sorted(PHASE_IDS):
        failures.append("workflow_must_bind_five_phases")
    native_ids: set[str] = set()
    for row in source.get("native_checks", ()):
        if not isinstance(row, Mapping):
            failures.append("invalid_native_check")
            continue
        for key in ("binding_id", "native_check_id", "kind", "summary", "command", "evidence_source"):
            if not isinstance(row.get(key), str) or not str(row.get(key)).strip():
                failures.append(f"native_check_missing_{key}")
        binding = str(row.get("binding_id", ""))
        if binding in native_ids:
            failures.append("duplicate_native_check_binding")
        native_ids.add(binding)
    output_fields = {str(item) for item in source.get("output_fields", ())}
    missing_outputs = sorted(set(OUTPUT_FIELDS) - output_fields)
    if missing_outputs:
        failures.append("missing_output_fields:" + ",".join(missing_outputs))
    if skill_dir is not None and source.get("skill_id") != skill_dir.name:
        failures.append("skill_id_directory_mismatch")
    if skill_dir is not None:
        for reference in source.get("direct_references", ()):
            if not isinstance(reference, str) or not reference.strip():
                failures.append("invalid_direct_reference")
                continue
            resolved = (skill_dir / reference).resolve()
            try:
                resolved.relative_to(skill_dir.resolve())
            except ValueError:
                failures.append(f"direct_reference_escapes_skill:{reference}")
                continue
            if not resolved.is_file():
                failures.append(f"direct_reference_missing:{reference}")
    return tuple(dict.fromkeys(failures))


def contract_source_semantic_fingerprint(source: Mapping[str, Any]) -> str:
    """Fingerprint behavior-bearing source fields while ignoring identity labels."""

    return _hash(
        {
            "route_role": source.get("route_role"),
            "route_summary": source.get("route_summary"),
            "activation_keywords": source.get("activation_keywords"),
            "use_when": source.get("use_when"),
            "do_not_use_when": source.get("do_not_use_when"),
            "workflow": source.get("workflow"),
            "native_checks": [
                {
                    "kind": row.get("kind"),
                    "summary": row.get("summary"),
                    "command": row.get("command"),
                }
                for row in source.get("native_checks", ())
                if isinstance(row, Mapping)
            ],
            "source_requirements": [
                {"category": row.get("category"), "summary": row.get("summary")}
                for row in source.get("source_requirements", ())
                if isinstance(row, Mapping)
            ],
            "downstream_targets": source.get("downstream_targets"),
            "claim_boundary": source.get("claim_boundary"),
        }
    )


def validate_contract_source_route(skill_id: str, source: Mapping[str, Any]) -> tuple[str, ...]:
    from .self_maintenance import default_flowguard_route_profiles

    profiles = {profile.route_id: profile for profile in default_flowguard_route_profiles()}
    route_id = str(source.get("route_id", ""))
    profile = profiles.get(route_id)
    if profile is None:
        return (f"contract_source_route_missing:{route_id}",)
    failures: list[str] = []
    role = str(source.get("route_role", ""))
    expected_role = "kernel" if skill_id == "model-first-function-flow" else profile.route_role
    if role != expected_role:
        failures.append(f"contract_source_route_role_mismatch:{role}:{expected_role}")
    if profile.skill_name != skill_id:
        failures.append(f"contract_source_skill_owner_mismatch:{profile.skill_name}:{skill_id}")
    expected_owner = profile.canonical_owner_route or profile.route_id
    if str(source.get("native_owner", "")) != expected_owner:
        failures.append(
            f"contract_source_native_owner_mismatch:{source.get('native_owner', '')}:{expected_owner}"
        )
    return tuple(failures)


def _phase_for_category(category: str) -> str:
    value = category.lower()
    if "entry" in value or "activation" in value or "non-use" in value:
        return "intake"
    if "evidence" in value or "check" in value or "quality" in value:
        return "checks"
    if any(term in value for term in ("output", "closure", "release", "public-boundary")):
        return "closure"
    return "execution"


def _merged_requirements(skill_text: str, source: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = {row["requirement_id"]: dict(row) for row in infer_source_requirements(skill_text)}
    for item in source.get("source_requirements", ()):
        if not isinstance(item, Mapping):
            continue
        requirement_id = str(item.get("requirement_id", ""))
        rows[requirement_id] = {
            "requirement_id": requirement_id,
            "category": str(item.get("category", "target-rule")),
            "summary": str(item.get("summary", "")),
            "source_path": f"{CONTRACT_SOURCE_FILE}#source_requirements",
            "required": True,
        }
    return [rows[key] for key in sorted(rows)]


def compiler_input_hash(skill_text: str, source: Mapping[str, Any]) -> str:
    return _hash(
        {
            "compiler_version": COMPILER_VERSION,
            "skill_text": skill_text.replace("\r\n", "\n"),
            "contract_source": source,
            "route_registry_hash": route_registry_hash(),
        }
    )


def build_work_contract(skill_dir: str | Path, source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    skill_path = Path(skill_dir)
    source_data = dict(source) if source is not None else load_contract_source(skill_path)
    failures = validate_contract_source(source_data, skill_path)
    if failures:
        raise ValueError("; ".join(failures))
    skill_text = (skill_path / "SKILL.md").read_text(encoding="utf-8")
    skill_id = str(source_data["skill_id"])
    route_id = str(source_data["route_id"])
    native_owner = str(source_data["native_owner"])
    route_binding_id = f"{route_id}.native_route"
    native_checks = [dict(row) for row in source_data["native_checks"]]
    native_binding_ids = [str(row["binding_id"]) for row in native_checks]
    requirements = _merged_requirements(skill_text, source_data)
    workflow_by_phase = {str(row["phase_id"]): str(row["summary"]) for row in source_data["workflow"]}
    stage_by_phase = {phase: f"{_identifier(route_id, limit=40)}_{phase}" for phase in PHASE_IDS}
    evidence_by_phase = {phase: f"{_identifier(route_id, limit=40)}_{phase}_evidence" for phase in PHASE_IDS}
    local_check_by_phase = {phase: PHASE_CHECKS[phase][0] for phase in PHASE_IDS}

    target_rules: list[dict[str, Any]] = []
    obligations: list[dict[str, Any]] = []
    skill_checks: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    for index, requirement in enumerate(requirements, start=1):
        requirement_id = str(requirement["requirement_id"])
        token = f"r{index:03d}_{_identifier(requirement_id, limit=42)}"
        rule_id = f"{token}_rule"
        obligation_id = f"{token}_obligation"
        skill_check_id = f"{token}_check"
        blocker_id = f"{token}_blocker"
        phase = _phase_for_category(str(requirement["category"]))
        target_rules.append(
            {
                "rule_id": rule_id,
                "requirement_id": requirement_id,
                "category": str(requirement["category"]),
                "summary": str(requirement["summary"]),
                "source_path": str(requirement["source_path"]),
                "required": True,
            }
        )
        obligations.append(
            {
                "obligation_id": obligation_id,
                "requirement_ids": [requirement_id],
                "summary": f"Native FlowGuard coverage for {requirement_id}.",
                "required": True,
                "covered_by_checks": [local_check_by_phase[phase]],
                "native_check_binding_ids": native_binding_ids,
            }
        )
        skill_checks.append(
            {
                "check_id": skill_check_id,
                "obligation_ids": [obligation_id],
                "check_manifest_ids": [local_check_by_phase[phase]],
                "native_check_binding_ids": native_binding_ids,
                "required": True,
                "summary": f"Target-specific gate for {requirement_id}.",
            }
        )
        blockers.append(
            {
                "blocker_id": blocker_id,
                "obligation_ids": [obligation_id],
                "failure_class": str(requirement["category"]),
                "blocks_decisions": ["checked", "accepted"],
                "summary": f"Block checked/accepted closure when {requirement_id} lacks current native evidence.",
            }
        )
        gaps.append(
            {
                "gap_id": f"{token}_test_gap",
                "requirement_ids": [requirement_id],
                "summary": f"Native and structural check coverage for {requirement_id}.",
                "status": "complete",
                "planned_check_ids": [local_check_by_phase[phase], *[str(row["native_check_id"]) for row in native_checks]],
            }
        )
        coverage.append(
            {
                "row_id": f"{token}_coverage",
                "requirement_id": requirement_id,
                "rule_id": rule_id,
                "obligation_id": obligation_id,
                "route_id": route_id,
                "stage_id": stage_by_phase[phase],
                "check_ids": [local_check_by_phase[phase]],
                "native_check_binding_ids": native_binding_ids,
                "evidence_ids": [evidence_by_phase[phase]],
                "closure_blocker_id": blocker_id,
                "source_path": str(requirement["source_path"]),
                "required": True,
            }
        )

    check_scripts = [
        {
            "check_id": PHASE_CHECKS[phase][0],
            "phase_id": phase,
            "script_path": SHARED_CHECK_FILE,
            "command": f"python {SHARED_CHECK_FILE} --phase {phase}",
            "required": True,
            "failure_class": PHASE_CHECKS[phase][1],
        }
        for phase in PHASE_IDS
    ]
    phases = [
        {
            "phase_id": phase,
            "summary": workflow_by_phase[phase],
            "required_evidence": [evidence_by_phase[phase]],
            "required_checks": [local_check_by_phase[phase]],
            "allowed_next": [PHASE_IDS[index + 1]] if index + 1 < len(PHASE_IDS) else [],
        }
        for index, phase in enumerate(PHASE_IDS)
    ]
    contract: dict[str, Any] = {
        "schema_version": WORK_CONTRACT_SCHEMA,
        "skill_id": skill_id,
        "target_path": f".agents/skills/{skill_id}",
        "contract_version": f"{COMPILER_VERSION}+{compiler_input_hash(skill_text, source_data)[:16]}",
        "contract_hash": "",
        "integration_mode": "native-integrated",
        "native_route_owner": native_owner,
        "native_route_bindings": [
            {
                "binding_id": route_binding_id,
                "native_route_id": route_id,
                "source": "FlowGuard canonical route registry and target contract source",
                "required_before_closure": True,
            }
        ],
        "native_check_bindings": [
            {
                "binding_id": str(row["binding_id"]),
                "native_check_id": str(row["native_check_id"]),
                "evidence_source": str(row["evidence_source"]),
                "command": str(row["command"]),
                "required": True,
            }
            for row in native_checks
        ],
        "phase_native_bindings": [
            {
                "phase_id": phase,
                "native_route_binding_id": route_binding_id,
                "native_check_binding_ids": native_binding_ids,
                "evidence_source": f"{CONTRACT_SOURCE_FILE} and current native command receipts",
                "required": True,
            }
            for phase in PHASE_IDS
        ],
        "source_requirements": requirements,
        "target_rule_inventory": target_rules,
        "route_inventory": [
            {
                "route_id": route_id,
                "summary": str(source_data["route_summary"]),
                "source_path": CONTRACT_SOURCE_FILE,
                "required": True,
                "native_binding_id": route_binding_id,
            }
        ],
        "workflow_stage_inventory": [
            {
                "stage_id": stage_by_phase[phase],
                "route_id": route_id,
                "summary": workflow_by_phase[phase],
                "source_path": CONTRACT_SOURCE_FILE,
                "required": True,
            }
            for phase in PHASE_IDS
        ],
        "native_check_inventory": [
            {
                "check_id": str(row["native_check_id"]),
                "kind": str(row["kind"]),
                "summary": str(row["summary"]),
                "source_path": CONTRACT_SOURCE_FILE,
                "command": str(row["command"]),
                "required": True,
            }
            for row in native_checks
        ],
        "test_gap_plan": gaps,
        "coverage_matrix": coverage,
        "runtime_lock_policy": {
            "policy_id": f"{route_id}.target_local_runtime_lock",
            "summary": "The target-local contract, route, stage order, checks, evidence, and coverage matrix gate closure.",
            "applies_when": f"The {skill_id} skill is selected or delegated.",
            "target_local_contract_required": True,
            "route_selection_required": True,
            "stage_sequence_required": True,
            "checks_before_closure": True,
            "evidence_before_closure": True,
            "coverage_matrix_required": True,
            "global_skillguard_pregate_required": False,
        },
        "acceptance_obligations": obligations,
        "skill_specific_checks": skill_checks,
        "closure_blockers": blockers,
        "run_record_required": False,
        "not_parallel_route_proof": {
            "proof_id": f"{route_id}.native_owner_proof",
            "summary": "SkillGuard only validates the FlowGuard-owned route and cannot define an alternate successful execution path.",
            "native_route_binding_ids": [route_binding_id],
            "evidence_source": "Canonical route registry, contract source, and may_define_* false gates",
        },
        "cleanup_required": [],
        "skillguard_role": "native_contract_executor",
        "may_define_parallel_execution_route": False,
        "may_define_skillguard_runtime_route": False,
        "integration_claim_boundary": "SkillGuard gates the target-native FlowGuard route; it does not execute a parallel controller or replace native model/test evidence.",
        "routes": [
            {
                "route_id": route_id,
                "route_source": "native_binding",
                "summary": str(source_data["route_summary"]),
                "activation_keywords": [str(item) for item in source_data["activation_keywords"]],
                "do_not_use_when": [str(item) for item in source_data["do_not_use_when"]],
                "phase_order": list(PHASE_IDS),
                "default_route": bool(source_data.get("default_route", False)),
                "route_priority": 0,
            }
        ],
        "phases": phases,
        "required_evidence": [
            {
                "evidence_id": evidence_by_phase[phase],
                "phase_id": phase,
                "kind": f"{route_id}_{phase}_evidence",
                "source": "FlowGuard native command receipt or direct target artifact",
                "required": True,
            }
            for phase in PHASE_IDS
        ],
        "quality_floors": [
            {
                "floor_id": "no_prose_only_completion",
                "summary": "Prompt prose, progress, or generated records cannot replace native evidence.",
                "required_checks": ["check_evidence", "check_quality_floor"],
                "failure_effect": "block checked or accepted closure",
            },
            {
                "floor_id": "no_partial_broad_claim",
                "summary": "Missing, stale, skipped, scoped, progress-only, or pass-with-gaps evidence cannot support broad closure.",
                "required_checks": ["check_quality_floor", "check_closure"],
                "failure_effect": "block broad done/release/archive/publish claims",
            },
        ],
        "forbidden_shortcuts": [
            {"shortcut_id": "parallel_skillguard_route", "summary": "Do not create a SkillGuard-owned alternate execution route."},
            {"shortcut_id": "synthetic_native_pass", "summary": "Do not convert configured booleans, generated JSON, or progress into native pass evidence."},
            {"shortcut_id": "skip_to_closure", "summary": "Do not skip required stages, checks, receipts, or blockers."},
        ],
        "check_scripts": check_scripts,
        "closure_rules": [
            {
                "rule_id": f"{route_id}.accepted_requires_all_gates",
                "scope": "current target revision and declared route only",
                "allowed_decision": "accepted",
                "required_checks": [row["check_id"] for row in check_scripts],
                "required_evidence": [evidence_by_phase[phase] for phase in PHASE_IDS],
            }
        ],
        "stale_bindings": [
            {"binding_id": "skill_prompt", "path": "SKILL.md", "stales": ["work_contract", "check_manifest", "closure"]},
            {"binding_id": "contract_source", "path": CONTRACT_SOURCE_FILE, "stales": ["work_contract", "check_manifest", "closure"]},
            {"binding_id": "route_registry", "path": "flowguard/self_maintenance.py", "stales": ["route_binding", "work_contract", "closure"]},
        ],
        "claim_boundary": str(source_data["claim_boundary"]),
    }
    contract["contract_hash"] = work_contract_hash(contract)
    return contract


def build_check_manifest(skill_dir: str | Path, contract: Mapping[str, Any]) -> dict[str, Any]:
    skill_id = Path(skill_dir).name
    return {
        "schema_version": CHECK_MANIFEST_SCHEMA,
        "target_skill": f".codex/skills/{skill_id}",
        "contract_ref": f".codex/skills/{skill_id}/{WORK_CONTRACT_FILE}",
        "checks": [
            {
                "check_id": str(row["check_id"]),
                "phase_id": str(row["phase_id"]),
                "command": str(row["command"]),
                "required": True,
                "failure_class": str(row["failure_class"]),
                "inputs": ["SKILL.md", CONTRACT_SOURCE_FILE, WORK_CONTRACT_FILE, CHECK_MANIFEST_FILE],
            }
            for row in contract["check_scripts"]
        ],
        "output_schema": "skillguard.cli_result.v1",
        "freshness": {
            "watch": ["SKILL.md", CONTRACT_SOURCE_FILE, WORK_CONTRACT_FILE, CHECK_MANIFEST_FILE, SHARED_CHECK_FILE]
        },
        "claim_boundary": "This manifest checks target-local prompt/contract parity only. Native commands and immutable receipts remain separate required evidence.",
    }


def build_control_records(skill_dir: str | Path, source: Mapping[str, Any]) -> dict[str, str]:
    """Build conservative static control records required by ``check-skill``."""

    skill_id = Path(skill_dir).name
    route_id = str(source["route_id"])
    boundary = (
        "This record covers only the current skill entrypoint and local SkillGuard contract files. "
        "It does not prove runtime checker execution, fixture coverage, CLI checks, tests, suite automation, "
        "package publication, code-contract validation, release readiness, or future AI behavior without "
        "separate current evidence."
    )

    def common(target_type: str, target_path: str) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "target_path": target_path,
            "target_type": target_type,
            "status": "needs-review",
            "evidence": [],
            "checks": [],
            "failures": [],
            "blockers": [],
            "skipped_checks": [],
            "residual_risk": ["Native commands and immutable receipts are intentionally outside this static record."],
            "claim_boundary": boundary,
        }

    profile = common("skill", "../SKILL.md")
    profile.update(
        {
            "profile_version": COMPILER_VERSION,
            "purpose": f"Maintain target-specific native-integrated contract readiness for {skill_id}.",
            "control_root": ".skillguard",
        }
    )
    static_contract = common("skill_contract", "../SKILL.md")
    static_contract.update(
        {
            "contract_version": COMPILER_VERSION,
            "required_sections": [
                "Purpose", "Entrypoint Scope", "Local Material Routing", "Entrypoint Acceptance Map",
                "Use When", "Do Not Use When", "Required Workflow", "Hard Gates",
                "Output Requirements", "SkillGuard Maintenance",
            ],
            "routes": [route_id],
            "evidence": [
                {"evidence_id": "skill-entrypoint", "path": "../SKILL.md", "summary": "Current skill entrypoint."},
                {"evidence_id": "runtime-work-contract", "path": WORK_CONTRACT_FILE, "summary": "Generated native-integrated work contract."},
                {"evidence_id": "contract-source", "path": CONTRACT_SOURCE_FILE, "summary": "Editable target-specific contract source."},
            ],
        }
    )
    evidence_rules = common("evidence_rules", "..")
    evidence_rules.update(
        {
            "required_evidence": ["Current native command receipt", "Artifact fingerprints", "Check output", "Closure report"],
            "forbidden_closure_inputs": ["Chat-only claims", "Generated booleans", "Stale reports", "Progress-only evidence", "Skipped checks as pass"],
            "evidence": [{"evidence_id": "current-evidence-manifest", "path": EVIDENCE_MANIFEST_FILE, "summary": "Static evidence inventory; not a native pass receipt."}],
        }
    )
    closure_policy = common("closure_policy", "..")
    closure_policy.update(
        {
            "closure_states": ["open", "blocked", "closed_with_evidence", "not_run"],
            "hard_gates": [
                {"gate_id": "route-selected", "condition": "No canonical native route is selected.", "required_disposition": "open or blocked"},
                {"gate_id": "direct-evidence", "condition": "Required native evidence is absent or stale.", "required_disposition": "open or blocked"},
                {"gate_id": "checks-current", "condition": "Required checks were skipped, failed, or not run.", "required_disposition": "open or blocked"},
            ],
            "evidence": [{"evidence_id": "current-closure", "path": CURRENT_CLOSURE_FILE, "summary": "Conservative structural closure status."}],
        }
    )
    manifest = common("control_manifest", "..")
    manifest.update(
        {
            "artifacts": [
                {"path": "skillguard_profile.json", "required": True, "role": "Static profile"},
                {"path": "skillguard_skill_contract.json", "required": True, "role": "Static target contract"},
                {"path": "skillguard_evidence_rules.json", "required": True, "role": "Evidence rules"},
                {"path": "skillguard_closure_policy.json", "required": True, "role": "Closure policy"},
                {"path": "contract-source.json", "required": True, "role": "Editable semantic source"},
                {"path": "work-contract.json", "required": True, "role": "Generated deep work contract"},
                {"path": "check_manifest.json", "required": True, "role": "Generated check manifest"},
                {"path": "check.py", "required": True, "role": "Thin shared-check adapter"},
                {"path": "evidence/current_evidence_manifest.json", "required": True, "role": "Static evidence inventory"},
                {"path": "reports/current_check_report.json", "required": True, "role": "Structural check status"},
                {"path": "reports/current_closure.json", "required": True, "role": "Structural closure boundary"},
            ]
        }
    )
    evidence_manifest = common("evidence_manifest", "..")
    evidence_manifest.update(
        {
            "evidence": [
                {"evidence_id": "skill-entrypoint", "path": "../SKILL.md", "summary": "Current skill entrypoint."},
                {"evidence_id": "contract-source", "path": CONTRACT_SOURCE_FILE, "summary": "Target-specific semantic source."},
                {"evidence_id": "runtime-work-contract", "path": WORK_CONTRACT_FILE, "summary": "Generated work contract; not native execution proof."},
                {"evidence_id": "check-manifest", "path": CHECK_MANIFEST_FILE, "summary": "Generated check manifest."},
                {"evidence_id": "check-report", "path": CURRENT_CHECK_REPORT_FILE, "summary": "Structural check status."},
                {"evidence_id": "closure-record", "path": CURRENT_CLOSURE_FILE, "summary": "Structural closure boundary."},
            ]
        }
    )
    check_report = common("skill", "..")
    check_report.update(
        {
            "checker_version": COMPILER_VERSION,
            "checks": [
                {"check_id": "generated-contract-parity", "name": "Generated contract parity", "required": True, "status": "not_run", "summary": "Run the compiler in check mode for current parity."},
                {"check_id": "native-command-receipts", "name": "Native command receipts", "required": True, "status": "not_run", "summary": "The self-governance receipt gate executes native commands separately."},
            ],
            "evidence": [
                {"evidence_id": "skill-entrypoint", "fresh": True, "kind": "file", "source_path": "../SKILL.md", "summary": "Current skill entrypoint."},
                {"evidence_id": "current-evidence-manifest", "fresh": True, "kind": "json", "source_path": EVIDENCE_MANIFEST_FILE, "summary": "Static evidence inventory."},
            ],
        }
    )
    closure = common("skill", "..")
    closure.update(
        {
            "closure_decision": "needs-review",
            "closure_scope": f"{skill_id} structural contract files only",
            "decision_reason": "Native commands and immutable receipts have not been inferred from static records.",
            "evidence": [
                {"evidence_id": "check-report", "fresh": True, "kind": "json", "source_path": CURRENT_CHECK_REPORT_FILE, "summary": "Structural check status."},
                {"evidence_id": "current-evidence-manifest", "fresh": True, "kind": "json", "source_path": EVIDENCE_MANIFEST_FILE, "summary": "Static evidence inventory."},
            ],
        }
    )
    ai_judgment = common("ai_judgment", "..")
    ai_judgment.update(
        {
            "decision": "bounded_support_only",
            "confidence": {"level": "medium", "rationale": "Based on current prompt and generated structural records only."},
            "input_evidence": [
                {"evidence_id": "skill-entrypoint", "path": "../SKILL.md", "summary": "Current skill entrypoint."},
                {"evidence_id": "runtime-work-contract", "path": WORK_CONTRACT_FILE, "summary": "Generated work contract."},
            ],
            "findings": [
                {
                    "finding_id": "native-integrated-contract-present",
                    "claim": "The skill has a target-specific native-integrated structural contract.",
                    "severity": "informational",
                    "supporting_evidence": ["skill-entrypoint", "runtime-work-contract"],
                    "limits": ["This judgment is not a native command receipt and cannot close broad confidence."],
                }
            ],
            "uncertainty": [
                {"question": "Are current native receipts available?", "impact": "Broad closure remains unavailable.", "resolution_path": "Run the self-governance native receipt gate."}
            ],
            "human_review": {"required": True, "reason": "AI judgment cannot approve broad skill-governance claims by itself."},
        }
    )
    progress = common("skill", "..")
    progress.update(
        {
            "schema_version": "skillguard.installed_progress_ledger.v1",
            "event_id": f"{skill_id}-target-contract-generated",
            "event_time": "1970-01-01T00:00:00Z",
            "event_summary": "Deterministic target contract artifacts were generated; native checks remain separately required.",
        }
    )
    return {
        PROFILE_FILE: _json_text(profile),
        SKILL_CONTRACT_FILE: _json_text(static_contract),
        EVIDENCE_RULES_FILE: _json_text(evidence_rules),
        CLOSURE_POLICY_FILE: _json_text(closure_policy),
        CONTROL_MANIFEST_FILE: _json_text(manifest),
        AI_JUDGMENT_FILE: _json_text(ai_judgment),
        EVIDENCE_MANIFEST_FILE: _json_text(evidence_manifest),
        CURRENT_CHECK_REPORT_FILE: _json_text(check_report),
        CURRENT_CLOSURE_FILE: _json_text(closure),
        PROGRESS_LEDGER_FILE: _canonical_json(progress) + "\n",
    }


SHARED_CHECK_TEXT = '''"""Generated thin check adapter for a FlowGuard native-integrated skill."""
from flowguard.skill_contracts import member_check_cli

if __name__ == "__main__":
    raise SystemExit(member_check_cli())
'''


@dataclass(frozen=True)
class ContractCompileFinding:
    code: str
    message: str
    skill_id: str = ""
    file_path: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "skill_id": self.skill_id, "file_path": self.file_path}


@dataclass(frozen=True)
class ContractCompileReport:
    root: str
    mode: str
    member_ids: tuple[str, ...]
    findings: tuple[ContractCompileFinding, ...] = field(default_factory=tuple)
    written_files: tuple[str, ...] = field(default_factory=tuple)
    contract_hashes: Mapping[str, str] = field(default_factory=dict)
    compiler_version: str = COMPILER_VERSION
    route_registry_hash: str = ""

    @property
    def ok(self) -> bool:
        return not self.findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_skill_contract_compile_report",
            "ok": self.ok,
            "status": "pass" if self.ok else "blocked",
            "root": self.root,
            "mode": self.mode,
            "compiler_version": self.compiler_version,
            "route_registry_hash": self.route_registry_hash,
            "member_count": len(self.member_ids),
            "member_ids": list(self.member_ids),
            "contract_hashes": dict(self.contract_hashes),
            "written_files": list(self.written_files),
            "findings": [finding.to_dict() for finding in self.findings],
            "claim_boundary": "Compiler pass proves deterministic generated-record parity, not native command execution or parent closure.",
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)


def compile_skill_contract(skill_dir: str | Path, *, write: bool = False) -> tuple[dict[str, Any], dict[str, Any], tuple[ContractCompileFinding, ...], tuple[str, ...]]:
    skill_path = Path(skill_dir).resolve()
    findings: list[ContractCompileFinding] = []
    written: list[str] = []
    try:
        source = load_contract_source(skill_path)
        contract = build_work_contract(skill_path, source)
        manifest = build_check_manifest(skill_path, contract)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        findings.append(ContractCompileFinding("contract_source_invalid", str(exc), skill_path.name, str(skill_path / CONTRACT_SOURCE_FILE)))
        return {}, {}, tuple(findings), ()

    expected = {
        WORK_CONTRACT_FILE: _json_text(contract),
        CHECK_MANIFEST_FILE: _json_text(manifest),
        SHARED_CHECK_FILE: SHARED_CHECK_TEXT,
    }
    expected.update(build_control_records(skill_path, source))
    for relative, content in expected.items():
        path = skill_path / relative
        if write:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                path.write_text(content, encoding="utf-8", newline="\n")
                written.append(path.as_posix())
            continue
        if not path.is_file():
            findings.append(ContractCompileFinding("generated_file_missing", "generated contract artifact is missing", skill_path.name, path.as_posix()))
        elif path.read_text(encoding="utf-8") != content:
            findings.append(ContractCompileFinding("stale_generated_contract", "generated artifact differs from deterministic compiler output", skill_path.name, path.as_posix()))
    return contract, manifest, tuple(findings), tuple(written)


def compile_skill_suite(root: str | Path = ".", *, write: bool = False) -> ContractCompileReport:
    root_path = Path(root).resolve()
    inventory = validate_skill_suite(root_path, check_private_inventories=False)
    member_ids = inventory.declared_member_ids
    findings: list[ContractCompileFinding] = []
    written: list[str] = []
    hashes: dict[str, str] = {}
    fingerprints: dict[str, list[str]] = {}
    for skill_id in member_ids:
        skill_dir = root_path / FLOWGUARD_SKILL_ROOT / skill_id
        contract, _, member_findings, member_written = compile_skill_contract(skill_dir, write=write)
        findings.extend(member_findings)
        written.extend(member_written)
        if contract:
            hashes[skill_id] = str(contract["contract_hash"])
            try:
                source = load_contract_source(skill_dir)
                fingerprint = contract_source_semantic_fingerprint(source)
            except (OSError, ValueError, json.JSONDecodeError):
                pass
            else:
                for failure in validate_contract_source_route(skill_id, source):
                    findings.append(
                        ContractCompileFinding(
                            "contract_source_route_parity",
                            failure,
                            skill_id=skill_id,
                            file_path=(skill_dir / CONTRACT_SOURCE_FILE).as_posix(),
                        )
                    )
                fingerprints.setdefault(fingerprint, []).append(skill_id)
    for fingerprint, owners in sorted(fingerprints.items()):
        if len(owners) > 1:
            findings.append(
                ContractCompileFinding(
                    "generic_duplicate_contract",
                    "unrelated skills share the same target-specific semantic contract fingerprint",
                    skill_id=",".join(sorted(owners)),
                    file_path=fingerprint,
                )
            )
    return ContractCompileReport(
        root=str(root_path),
        mode="write" if write else "check",
        member_ids=member_ids,
        findings=tuple(findings),
        written_files=tuple(written),
        contract_hashes=hashes,
        route_registry_hash=route_registry_hash(),
    )


def _find_repo_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / FLOWGUARD_SKILL_ROOT).is_dir():
            return candidate
    return None


def member_check_cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="check one generated FlowGuard skill contract")
    parser.add_argument("--phase", choices=PHASE_IDS, required=True)
    args = parser.parse_args(argv)
    skill_dir = Path.cwd().resolve()
    root = _find_repo_root(skill_dir)
    if root is None:
        payload = {
            "schema_version": "skillguard.cli_result.v1",
            "decision": "block",
            "failures": ["repository root is unavailable; installed execution needs the suite runner and native receipts"],
            "blockers": ["missing_repository_context"],
            "skipped_checks": [args.phase],
            "residual_risk": [],
            "claim_boundary": "No contract or native confidence is claimed without repository context.",
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1
    _, _, findings, _ = compile_skill_contract(skill_dir, write=False)
    payload = {
        "schema_version": "skillguard.cli_result.v1",
        "decision": "pass" if not findings else "block",
        "phase": args.phase,
        "evidence": ["deterministic prompt/contract parity"] if not findings else [],
        "failures": [finding.to_dict() for finding in findings],
        "blockers": [finding.code for finding in findings],
        "skipped_checks": ["native commands are executed by the receipt/self-governance gate"],
        "residual_risk": ["This structural check does not execute the declared native commands."],
        "claim_boundary": "Pass covers generated contract parity for this skill and phase only.",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not findings else 1


__all__ = [
    "CHECK_MANIFEST_FILE",
    "CHECK_MANIFEST_SCHEMA",
    "COMPILER_VERSION",
    "CONTRACT_SOURCE_FILE",
    "CONTRACT_SOURCE_SCHEMA",
    "ContractCompileFinding",
    "ContractCompileReport",
    "OUTPUT_FIELDS",
    "PHASE_IDS",
    "SHARED_CHECK_FILE",
    "WORK_CONTRACT_FILE",
    "WORK_CONTRACT_SCHEMA",
    "build_check_manifest",
    "build_work_contract",
    "compile_skill_contract",
    "compile_skill_suite",
    "compiler_input_hash",
    "contract_source_semantic_fingerprint",
    "infer_source_requirements",
    "load_contract_source",
    "member_check_cli",
    "route_registry_hash",
    "validate_contract_source",
    "validate_contract_source_route",
    "work_contract_hash",
]
