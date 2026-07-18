"""Current-only FlowGuard skill contract parity reader.

SkillGuard's installed current compiler is the sole writer for maintained skill
contracts.  This module deliberately does not compile an alternate format and
does not retain former V1 readers.  It gives FlowGuard's suite checks a small,
portable way to verify the three current authority files and reject residual
former control surfaces before the official SkillGuard checks run.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .skill_suite import FLOWGUARD_SKILL_ROOT, validate_skill_suite


CONTRACT_SOURCE_SCHEMA = "skillguard.contract_source.v2"
CONTRACT_SOURCE_V2_SCHEMA = CONTRACT_SOURCE_SCHEMA
COMPILED_CONTRACT_SCHEMA = "skillguard.compiled_contract.v2"
CHECK_MANIFEST_SCHEMA = "skillguard.check_manifest.v2"
CONTRACT_SOURCE_FILE = ".skillguard/contract-source.json"
COMPILED_CONTRACT_FILE = ".skillguard/compiled-contract.json"
CHECK_MANIFEST_FILE = ".skillguard/check-manifest.json"
COMPILER_VERSION = "flowguard.current_skillguard_parity_reader.v1"

_SHA256_RE = re.compile(r"^[A-F0-9]{64}$")
_CURRENT_SOURCE_FIELDS = frozenset(
    {
        "artifacts",
        "checks",
        "claim_boundary",
        "closure_profiles",
        "confirmed",
        "consumer_projection",
        "content_impact_policy",
        "content_role_overrides",
        "depth_profile",
        "default_route_id",
        "implementation_paths",
        "integration_mode",
        "judgment_rubrics",
        "maintenance_unit_id",
        "may_define_parallel_execution_route",
        "may_define_skillguard_runtime_route",
        "member_skill_ids",
        "model_id",
        "model_path",
        "native_check_bindings",
        "native_route_bindings",
        "native_route_owner",
        "portfolio_capability_contracts",
        "portfolio_target_edges",
        "projection_consumers",
        "release_eligible",
        "repository_role",
        "route_branch_closure_required",
        "schema_version",
        "skill_id",
        "step_bindings",
    }
)
_CURRENT_AUTHORITY_FILES = frozenset(
    {"contract-source.json", "compiled-contract.json", "check-manifest.json"}
)
_FORMER_AUTHORITY_NAMES = frozenset(
    {
        "ai_judgments",
        "check_manifest.json",
        "check.py",
        "checks",
        "evidence",
        "reports",
        "skillguard_closure_policy.json",
        "skillguard_evidence_rules.json",
        "skillguard_manifest.json",
        "skillguard_profile.json",
        "skillguard_progress_ledger.jsonl",
        "skillguard_skill_contract.json",
        "work-contract.json",
    }
)
_FULL_ADMISSION_REASONS = frozenset(
    {
        "explicit_final_gate",
        "explicit_release_gate",
        "impact_policy_or_compiler_changed",
        "shared_validation_runtime_changed",
        "all_owner_component_changed",
    }
)
_CLOSURE_PROFILE_ORDER = ("enforced",)
_CONSUMER_PROJECTION = {
    "projection_id": "projection:consumer-distribution",
    "prohibited_path_prefixes": [".skillguard/"],
    "prohibited_prompt_tokens": ["SkillGuard", ".skillguard", "skillguard.py"],
    "release_manifest_path": "consumer-release.json",
}
_DEPTH_PROFILE_FIELDS = frozenset(
    {
        "schema_version",
        "profile_id",
        "target_skill_id",
        "integration_mode",
        "native_owner_id",
        "native_route_ids",
        "native_check_ids",
        "native_route_absent_confirmed",
        "skillguard_adds_domain_route",
        "enforcement_level",
        "required_closure_profiles",
        "provider_runtime",
        "claim_boundary",
    }
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest().upper()


def _file_hash(path: Path) -> str:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    else:
        data = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(data).hexdigest().upper()


def route_registry_hash() -> str:
    from .self_maintenance import default_flowguard_route_profiles

    rows = [profile.to_dict() for profile in default_flowguard_route_profiles()]
    return _hash(rows)


def load_contract_source(skill_dir: str | Path) -> dict[str, Any]:
    skill_path = Path(skill_dir)
    path = skill_path / CONTRACT_SOURCE_FILE
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("contract source root must be an object")
    failures = validate_contract_source(value, skill_path)
    if failures:
        raise ValueError("; ".join(failures))
    return value


def validate_contract_source(
    source: Mapping[str, Any], skill_dir: Path | None = None
) -> tuple[str, ...]:
    """Validate the current binding shape without accepting a legacy dialect."""

    failures: list[str] = []
    unknown = sorted(set(source) - _CURRENT_SOURCE_FIELDS)
    failures.extend(f"unknown_contract_source_field:{name}" for name in unknown)
    if source.get("schema_version") != CONTRACT_SOURCE_SCHEMA:
        failures.append("contract_source_schema_mismatch")
    for field_name in (
        "skill_id",
        "model_id",
        "model_path",
        "claim_boundary",
        "native_route_owner",
        "default_route_id",
    ):
        if not isinstance(source.get(field_name), str) or not str(source[field_name]).strip():
            failures.append(f"missing_{field_name}")
    if source.get("confirmed") is not True:
        failures.append("contract_source_not_confirmed")
    if source.get("release_eligible") is not False:
        failures.append("contract_source_release_eligibility_must_be_false")
    if source.get("integration_mode") != "native-integrated":
        failures.append("contract_source_not_native_integrated")
    if source.get("may_define_parallel_execution_route") is not False:
        failures.append("parallel_execution_route_forbidden")
    if source.get("may_define_skillguard_runtime_route") is not False:
        failures.append("skillguard_runtime_route_forbidden")
    skill_id = str(source.get("skill_id", ""))
    maintenance_unit_id = str(source.get("maintenance_unit_id", ""))
    if source.get("repository_role") != "skill_maintainer_source":
        failures.append("contract_source_not_author_source")
    if maintenance_unit_id != f"unit:{skill_id}":
        failures.append("maintenance_unit_identity_mismatch")
    if source.get("member_skill_ids") != [skill_id]:
        failures.append("member_skill_inventory_mismatch")
    if source.get("consumer_projection") != _CONSUMER_PROJECTION:
        failures.append("consumer_projection_mismatch")
    for field_name in (
        "implementation_paths",
        "step_bindings",
        "checks",
        "artifacts",
        "closure_profiles",
        "judgment_rubrics",
        "native_route_bindings",
        "native_check_bindings",
    ):
        if not isinstance(source.get(field_name), list):
            failures.append(f"invalid_{field_name}")
    if not source.get("implementation_paths"):
        failures.append("missing_implementation_paths")
    if not source.get("native_route_bindings"):
        failures.append("missing_native_route_bindings")
    if not source.get("native_check_bindings"):
        failures.append("missing_native_check_bindings")

    policy = source.get("content_impact_policy")
    if not isinstance(policy, Mapping):
        failures.append("missing_content_impact_policy")
    else:
        if policy.get("policy_id") != "skillguard.content_impact_policy.current":
            failures.append("content_impact_policy_id_mismatch")
        if policy.get("owner_receipt_root_ref") != {
            "path_token": "owner_evidence_root",
            "relative_path": "check-executions",
        }:
            failures.append("content_impact_owner_root_mismatch")
        if policy.get("unknown_mapping_disposition") != "block":
            failures.append("content_impact_unknown_mapping_must_block")
        if set(policy.get("full_admission_reason_codes", ())) != _FULL_ADMISSION_REASONS:
            failures.append("content_impact_full_admission_reasons_mismatch")

    profiles = source.get("closure_profiles", ())
    profile_ids = tuple(
        str(row.get("profile_id", "")) for row in profiles if isinstance(row, Mapping)
    )
    if profile_ids != _CLOSURE_PROFILE_ORDER:
        failures.append("closure_profiles_incomplete_or_out_of_order")

    depth = source.get("depth_profile")
    if not isinstance(depth, Mapping):
        failures.append("missing_depth_profile")
    else:
        failures.extend(
            f"unknown_depth_profile_field:{name}"
            for name in sorted(set(depth) - _DEPTH_PROFILE_FIELDS)
        )
        if depth.get("schema_version") != "skillguard.depth_profile.v2":
            failures.append("depth_profile_schema_mismatch")
        if depth.get("target_skill_id") != source.get("skill_id"):
            failures.append("depth_profile_target_mismatch")
        if depth.get("integration_mode") != "native-integrated":
            failures.append("depth_profile_not_native_integrated")
        if depth.get("native_owner_id") != source.get("native_route_owner"):
            failures.append("depth_profile_owner_mismatch")
        if depth.get("skillguard_adds_domain_route") is not False:
            failures.append("depth_profile_parallel_route_forbidden")
        if depth.get("enforcement_level") != "enforced":
            failures.append("depth_profile_enforcement_invalid")
        if not isinstance(depth.get("native_route_ids"), list) or not depth.get("native_route_ids"):
            failures.append("depth_profile_routes_missing")
        if not isinstance(depth.get("native_check_ids"), list) or not depth.get("native_check_ids"):
            failures.append("depth_profile_checks_missing")
        if depth.get("required_closure_profiles") != ["enforced"]:
            failures.append("depth_profile_closure_profile_invalid")

        source_check_ids = {
            str(check.get("check_id", ""))
            for check in source.get("checks", ())
            if isinstance(check, Mapping)
        }
        depth_check_ids = depth.get("native_check_ids", ())
        if isinstance(depth_check_ids, list) and set(depth_check_ids) != source_check_ids:
            failures.append("depth_profile_check_inventory_mismatch")

        source_route_ids = {
            str(binding.get("route_id", ""))
            for binding in source.get("native_route_bindings", ())
            if isinstance(binding, Mapping)
        }
        depth_route_ids = depth.get("native_route_ids", ())
        if isinstance(depth_route_ids, list) and set(depth_route_ids) != source_route_ids:
            failures.append("depth_profile_route_inventory_mismatch")

        provider = depth.get("provider_runtime")
        if not isinstance(provider, Mapping):
            failures.append("depth_profile_provider_runtime_missing")
        else:
            if provider.get("provider_id") != "skillguard-local-provider":
                failures.append("depth_profile_provider_id_mismatch")
            if provider.get("required_runtime_contract_id") != (
                "skillguard-declared-check-supervision-current"
            ):
                failures.append("depth_profile_runtime_contract_mismatch")
            if provider.get("required_enrollment_status") != "enrolled":
                failures.append("depth_profile_provider_not_enrolled")
            capabilities = provider.get("required_capability_ids")
            if not isinstance(capabilities, list) or not capabilities:
                failures.append("depth_profile_provider_capabilities_missing")
            readiness_ids = provider.get("readiness_check_ids")
            if not isinstance(readiness_ids, list) or not readiness_ids:
                failures.append("depth_profile_provider_readiness_missing")
            elif not set(readiness_ids).issubset(source_check_ids):
                failures.append("depth_profile_provider_readiness_unknown")

    for index, check in enumerate(source.get("checks", ())):
        if not isinstance(check, Mapping):
            failures.append(f"invalid_check:{index}")
            continue
        for field_name in (
            "check_id",
            "semantic_check_id",
            "maintenance_unit_id",
            "member_skill_id",
            "evidence_subject_id",
            "execution_owner_id",
            "evidence_domain_id",
        ):
            if not isinstance(check.get(field_name), str) or not check[field_name]:
                failures.append(f"check_missing_{field_name}:{index}")
        if check.get("maintenance_unit_id") != maintenance_unit_id:
            failures.append(f"check_maintenance_unit_mismatch:{index}")
        if check.get("member_skill_id") != skill_id:
            failures.append(f"check_member_skill_mismatch:{index}")
        if not isinstance(check.get("input_selectors"), list) or not check.get("input_selectors"):
            failures.append(f"check_input_selectors_missing:{index}")

    if skill_dir is not None:
        if source.get("skill_id") != skill_dir.name:
            failures.append("skill_id_directory_mismatch")
        repository_root = skill_dir.resolve().parents[2]
        model_path = repository_root / str(source.get("model_path", ""))
        if not model_path.is_file():
            failures.append("model_path_missing")
        if not (skill_dir / "SKILL.md").is_file():
            failures.append("skill_entrypoint_missing")
    return tuple(dict.fromkeys(failures))


def contract_source_semantic_fingerprint(source: Mapping[str, Any]) -> str:
    return _hash(
        {
            "default_route_id": source.get("default_route_id"),
            "native_route_owner": source.get("native_route_owner"),
            "native_route_bindings": source.get("native_route_bindings"),
            "native_check_bindings": source.get("native_check_bindings"),
            "step_bindings": source.get("step_bindings"),
            "checks": source.get("checks"),
            "closure_profiles": source.get("closure_profiles"),
            "depth_profile": source.get("depth_profile"),
            "claim_boundary": source.get("claim_boundary"),
        }
    )


def validate_contract_source_route(
    skill_id: str, source: Mapping[str, Any]
) -> tuple[str, ...]:
    from .self_maintenance import default_flowguard_route_profiles

    profiles = {profile.route_id: profile for profile in default_flowguard_route_profiles()}
    route_id = str(source.get("default_route_id", "")).removeprefix("route:")
    profile = profiles.get(route_id)
    if profile is None:
        return (f"contract_source_route_missing:{route_id}",)
    failures: list[str] = []
    if profile.skill_name != skill_id:
        failures.append(f"contract_source_skill_owner_mismatch:{profile.skill_name}:{skill_id}")
    expected_owner = profile.canonical_owner_route or profile.route_id
    if str(source.get("native_route_owner", "")) != expected_owner:
        failures.append(
            f"contract_source_native_owner_mismatch:{source.get('native_route_owner', '')}:{expected_owner}"
        )
    return tuple(failures)


@dataclass(frozen=True)
class ContractCompileFinding:
    code: str
    message: str
    skill_id: str = ""
    file_path: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "skill_id": self.skill_id,
            "file_path": self.file_path,
        }


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
            "artifact_type": "flowguard_current_skill_contract_parity_report",
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
            "claim_boundary": (
                "Pass proves current source/compiled/manifest identity binding and zero former authority residuals. "
                "The official SkillGuard compiler/check-depth remains the schema, parity, and depth authority."
            ),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)


def _load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path.name}")
    return value


def compile_skill_contract(
    skill_dir: str | Path, *, write: bool = False
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    tuple[ContractCompileFinding, ...],
    tuple[str, ...],
]:
    """Read and verify one current contract; never write an alternate authority."""

    skill_path = Path(skill_dir).resolve()
    findings: list[ContractCompileFinding] = []
    if write:
        findings.append(
            ContractCompileFinding(
                "official_current_compiler_required",
                "FlowGuard is a parity reader; use the installed current SkillGuard compiler to generate authorities.",
                skill_path.name,
                str(skill_path / CONTRACT_SOURCE_FILE),
            )
        )
        return {}, {}, tuple(findings), ()
    try:
        source = load_contract_source(skill_path)
        compiled_path = skill_path / COMPILED_CONTRACT_FILE
        manifest_path = skill_path / CHECK_MANIFEST_FILE
        compiled = _load_json_object(compiled_path)
        manifest = _load_json_object(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        findings.append(
            ContractCompileFinding(
                "current_contract_unavailable",
                str(exc),
                skill_path.name,
                str(skill_path / ".skillguard"),
            )
        )
        return {}, {}, tuple(findings), ()

    if compiled.get("schema_version") != COMPILED_CONTRACT_SCHEMA:
        findings.append(ContractCompileFinding("compiled_contract_schema_mismatch", COMPILED_CONTRACT_SCHEMA, skill_path.name, str(compiled_path)))
    if manifest.get("schema_version") != CHECK_MANIFEST_SCHEMA:
        findings.append(ContractCompileFinding("check_manifest_schema_mismatch", CHECK_MANIFEST_SCHEMA, skill_path.name, str(manifest_path)))
    for field_name in (
        "skill_id",
        "model_id",
        "model_path",
        "claim_boundary",
        "repository_role",
        "maintenance_unit_id",
        "member_skill_ids",
        "consumer_projection",
    ):
        if compiled.get(field_name) != source.get(field_name):
            findings.append(ContractCompileFinding("source_projection_mismatch", field_name, skill_path.name, str(compiled_path)))
    for field_name in (
        "skill_id",
        "model_id",
        "maintenance_unit_id",
        "member_skill_ids",
        "consumer_projection",
    ):
        if manifest.get(field_name) != source.get(field_name):
            findings.append(ContractCompileFinding("manifest_identity_mismatch", field_name, skill_path.name, str(manifest_path)))
    if manifest.get("contract_hash") != compiled.get("contract_hash"):
        findings.append(ContractCompileFinding("manifest_contract_hash_mismatch", "contract_hash", skill_path.name, str(manifest_path)))
    contract_hash = str(compiled.get("contract_hash", ""))
    manifest_hash = str(manifest.get("manifest_hash", ""))
    if _SHA256_RE.fullmatch(contract_hash) is None:
        findings.append(ContractCompileFinding("compiled_contract_hash_invalid", contract_hash, skill_path.name, str(compiled_path)))
    if _SHA256_RE.fullmatch(manifest_hash) is None:
        findings.append(ContractCompileFinding("check_manifest_hash_invalid", manifest_hash, skill_path.name, str(manifest_path)))

    fingerprints = compiled.get("source_fingerprints")
    manifest_fingerprints = manifest.get("source_fingerprints")
    if not isinstance(fingerprints, Mapping) or fingerprints != manifest_fingerprints:
        findings.append(ContractCompileFinding("source_fingerprint_projection_mismatch", "compiled/manifest", skill_path.name, str(manifest_path)))
    else:
        expected_binding = _file_hash(skill_path / CONTRACT_SOURCE_FILE)
        expected_entrypoint = _file_hash(skill_path / "SKILL.md")
        if fingerprints.get("binding") != expected_binding:
            findings.append(ContractCompileFinding("binding_fingerprint_stale", expected_binding, skill_path.name, str(compiled_path)))
        if fingerprints.get("entrypoint") != expected_entrypoint:
            findings.append(ContractCompileFinding("entrypoint_fingerprint_stale", expected_entrypoint, skill_path.name, str(compiled_path)))

    authority_root = skill_path / ".skillguard"
    residuals = sorted(name for name in _FORMER_AUTHORITY_NAMES if (authority_root / name).exists())
    unexpected_root_files = sorted(
        child.name
        for child in authority_root.iterdir()
        if child.is_file() and child.name not in _CURRENT_AUTHORITY_FILES
    )
    for residual in sorted(set(residuals + unexpected_root_files)):
        findings.append(ContractCompileFinding("former_runtime_authority_residual", residual, skill_path.name, str(authority_root / residual)))
    return compiled, manifest, tuple(findings), ()


def compile_skill_suite(root: str | Path = ".", *, write: bool = False) -> ContractCompileReport:
    root_path = Path(root).resolve()
    inventory = validate_skill_suite(root_path, check_private_inventories=False)
    member_ids = inventory.declared_member_ids
    findings: list[ContractCompileFinding] = []
    hashes: dict[str, str] = {}
    fingerprints: dict[str, list[str]] = {}
    for skill_id in member_ids:
        skill_dir = root_path / FLOWGUARD_SKILL_ROOT / skill_id
        contract, _, member_findings, _ = compile_skill_contract(skill_dir, write=write)
        findings.extend(member_findings)
        if contract:
            hashes[skill_id] = str(contract.get("contract_hash", ""))
            try:
                source = load_contract_source(skill_dir)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            for failure in validate_contract_source_route(skill_id, source):
                findings.append(ContractCompileFinding("contract_source_route_parity", failure, skill_id, str(skill_dir / CONTRACT_SOURCE_FILE)))
            fingerprints.setdefault(contract_source_semantic_fingerprint(source), []).append(skill_id)
    for fingerprint, owners in sorted(fingerprints.items()):
        if len(owners) > 1:
            findings.append(ContractCompileFinding("generic_duplicate_contract", "unrelated skills share one semantic contract", ",".join(sorted(owners)), fingerprint))
    return ContractCompileReport(
        root=str(root_path),
        mode="unsupported-write" if write else "check",
        member_ids=member_ids,
        findings=tuple(findings),
        contract_hashes=hashes,
        route_registry_hash=route_registry_hash(),
    )


__all__ = [
    "CHECK_MANIFEST_FILE",
    "CHECK_MANIFEST_SCHEMA",
    "COMPILED_CONTRACT_FILE",
    "COMPILED_CONTRACT_SCHEMA",
    "CONTRACT_SOURCE_FILE",
    "CONTRACT_SOURCE_SCHEMA",
    "CONTRACT_SOURCE_V2_SCHEMA",
    "ContractCompileFinding",
    "ContractCompileReport",
    "compile_skill_contract",
    "compile_skill_suite",
    "contract_source_semantic_fingerprint",
    "load_contract_source",
    "route_registry_hash",
    "validate_contract_source",
    "validate_contract_source_route",
]
