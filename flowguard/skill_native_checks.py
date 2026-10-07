"""Direct-current consumption of FlowGuard model-owned native evidence.

Model regression owners alone execute native checks. This module independently
verifies their current parent, leaves, oracles, and the frozen full invocation.
It never reads SkillGuard command bindings or launches a model/check process.
"""
from __future__ import annotations

import json
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ._package_identity import flowguard_package_version as _package_version
from .completion_run_manifest import load_manifest
from .evidence_receipts import (
    ChildReceiptRequirement, ConsumedChildReceipt, EvidenceReceipt,
    INPUT_HASH_BOTH, ReceiptVerificationContext, build_environment_fingerprint,
    evidence_storage_root, fingerprint_value, list_evidence_receipts,
    save_evidence_receipt, snapshot_file, tokenize_command, tokenize_path,
    verify_evidence_receipt,
)
from .evidence_lifecycle import fingerprint_payload
from .validation_owner_execution import canonical_semantic_command
from .model_authority_store import load_current_model_authority_state
from .model_regressions import (
    ModelRegressionManifest, build_model_regression_execution_evidence,
    resolve_current_full_model_regression_parent, select_entries,
)
from .native_case_mapping import load_native_case_mapping
from .validation_ownership import (
    ValidationOwnerContract, _canonical_owner_command, build_owner_current,
    find_reusable_owner_receipt, ValidationOwnerPlan, build_validation_parent_current,
    resolve_input_manifest, manifest_fingerprint,
)

PRODUCER_ID = "flowguard.skill_native_model_consumer"
NATIVE_IDENTITY_VERSION = "3"
PROOF_SCHEMA = "flowguard.skill_native_model_evidence.v1"
UMBRELLA = "flowguard.skill_contract.flowguard.deep"
SUITE_MAP_PATH = Path(".skillguard/flowguard-suite/suite-map.json")


def _json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("native evidence input missing or symlink: " + path.name)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("native evidence input must be an object")
    return value


def _environment():
    return build_environment_fingerprint({
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "platform_system": platform.system(),
        "platform_machine": platform.machine(),
        "flowguard_version": _package_version(),
    })


NATIVE_OWNER_UNIT_COMPONENT = "native-model-owner:completion-unit"


def _native_owner_unit_fingerprint(maintenance_unit_id, completion_work_id):
    if any(not isinstance(value, str) or not value.strip()
           for value in (maintenance_unit_id, completion_work_id)):
        raise ValueError("native_owner_completion_unit_identity_missing")
    return fingerprint_payload({"schema": "flowguard.native_owner_completion_unit.v1",
        "maintenance_unit_id": maintenance_unit_id,
        "completion_work_id": completion_work_id})


def _require_native_owner_unit(contract, invocation):
    expected = _native_owner_unit_fingerprint(invocation.get("maintenance_unit_id"),
                                              invocation.get("completion_work_id"))
    actual = tuple(value for name, value in contract.projected_inputs
                   if name == NATIVE_OWNER_UNIT_COMPONENT)
    if actual != (expected,):
        raise ValueError("native_owner_completion_unit_projection_mismatch")


def _full_dependency(root, manifest, owner_plan_path, validation_receipt_dir):
    """Verify the actual05 terminal against the frozen current owner contract.

    The completion manifest is a plan, never terminal evidence. A standalone
    invocation lacking these actual outer artifacts cannot qualify the unit.
    """
    if owner_plan_path is None or validation_receipt_dir is None:
        raise ValueError("same_unit_outer_context_not_proven")
    plan_path = Path(owner_plan_path).resolve()
    plan = _json(plan_path)
    raw_contracts = plan.get("contracts", ())
    if not isinstance(raw_contracts, list) or not raw_contracts:
        raise ValueError("full_owner_plan_contracts_missing")
    contracts = tuple(ValidationOwnerContract.from_dict(row) for row in raw_contracts)
    by_id = {item.owner_id: item for item in contracts}
    if len(by_id) != len(contracts):
        raise ValueError("full_owner_plan_duplicate_owners")
    required_graph = {"model_regressions_full", "skill_native_checks"}
    if plan.get("claim_scope") == "release":
        required_graph.add("skill_self_governance")
    if not required_graph <= set(by_id):
        raise ValueError("full_native_owner_graph_missing")
    _require_native_owner_unit(by_id["model_regressions_full"], manifest["invocation"])
    if by_id["skill_native_checks"].dependency_owner_ids != ("model_regressions_full",):
        raise ValueError("native_consumer_dependency_not_exact")
    if "skill_self_governance" in by_id and by_id["skill_self_governance"].dependency_owner_ids != ("skill_native_checks",):
        raise ValueError("self_governance_dependency_not_exact")
    keys = ("schema_version", "owner_identities", "validation_input_manifest_fingerprint",
            "release_tree_manifest_fingerprint", "claim_scope")
    payload = {key: plan[key] for key in keys}
    payload["contracts"] = [dict(item.to_dict(), command=list(
        _canonical_owner_command(item.command, workspace_root=root))) for item in contracts]
    plan_fp = fingerprint_value(payload)
    if plan_fp != plan.get("plan_fingerprint") or plan_fp != manifest["plan"].get("owner_plan_fingerprint"):
        raise ValueError("full_owner_plan_manifest_mismatch")
    # Compare namespaces through their official projection algorithms.
    # This is one declared Source observation, not a second full planner or
    # model execution; the frozen parent projection performs no Git scan.
    patterns = tuple(plan.get("observation_patterns", ()))
    expected_patterns = tuple(dict.fromkeys(pattern for item in contracts
                                            for pattern in item.input_patterns if pattern))
    if patterns != expected_patterns:
        raise ValueError("full_source_observation_selectors_mismatch")
    repository_inputs = resolve_input_manifest(root, patterns)
    if list(repository_inputs) != plan.get("repository_input_manifest"):
        raise ValueError("full_source_observation_inputs_changed")
    source_fp = fingerprint_value({
        "schema": "flowguard.validation_owner_source_observation.v1",
        "observation_patterns": list(patterns),
        "repository_input_manifest_fingerprint": manifest_fingerprint(repository_inputs),
        "owner_identities": dict(sorted(plan["owner_identities"].items())),
    })
    frozen_plan = ValidationOwnerPlan(
        contracts=contracts, rows=(), owner_currents={}, reusable_receipts={},
        validation_input_manifest=tuple(plan["validation_input_manifest"]),
        validation_input_manifest_fingerprint=plan["validation_input_manifest_fingerprint"],
        release_tree_manifest=tuple(plan["release_tree_manifest"]),
        release_tree_manifest_fingerprint=plan["release_tree_manifest_fingerprint"],
        plan_fingerprint=plan_fp, claim_scope=plan["claim_scope"])
    parent_current = build_validation_parent_current(root, frozen_plan,
        frozen_validation_manifest=frozen_plan.validation_input_manifest,
        frozen_release_tree_manifest=frozen_plan.release_tree_manifest)
    comparisons = {
        "source_observation_fingerprint": source_fp,
        "toolchain_environment_fingerprint": parent_current.environment_fingerprint,
        "model_authority_fingerprint": fingerprint_payload({"parent_identity": parent_current.parent_identity}),
        "owner_dag_fingerprint": plan_fp,
        "release_tree_fingerprint": frozen_plan.release_tree_manifest_fingerprint,
    }
    if any(manifest["plan"].get(key) != value for key, value in comparisons.items()):
        raise ValueError("completion_manifest_current_projection_mismatch")
    commands = manifest["plan"].get("child_semantic_commands")
    if (not isinstance(commands, list) or len(commands) != len(by_id)
            or any(not isinstance(row, dict) or set(row) != {"child_id", "command"}
                   or not isinstance(row["command"], list) for row in commands)
            or len({row["child_id"] for row in commands}) != len(commands)
            or {row["child_id"] for row in commands} != set(by_id)):
        raise ValueError("completion_manifest_current_command_inventory_mismatch")
    for row in commands:
        contract = by_id[row["child_id"]]
        left = _canonical_owner_command(canonical_semantic_command(row["command"],
            resource_options=contract.resource_argv_options), workspace_root=root)
        right = _canonical_owner_command(contract.command, workspace_root=root)
        if left != right:
            raise ValueError("completion_manifest_current_commands_mismatch")
    current = build_owner_current(root, by_id["model_regressions_full"], all_contracts=contracts)
    if current.owner_identity != plan["owner_identities"].get("model_regressions_full"):
        raise ValueError("full_native_owner_inputs_changed")
    receipts = list_evidence_receipts(root, output_directory=validation_receipt_dir,
                                     subject_ids=("validation-owner:model_regressions_full",))
    receipt, verification = find_reusable_owner_receipt(
        current, root, validation_receipt_dir, receipt_inventory=receipts)
    if receipt is None or verification is None or not verification.ok:
        raise ValueError("same_unit_native_owner_terminal_not_proven")
    return receipt, verification, plan_path


@dataclass(frozen=True)
class NativeModelObservation:
    binding: Mapping[str, Any]
    snapshots: tuple[Any, ...]
    children: tuple[EvidenceReceipt, ...]
    child_verifications: Mapping[str, Any]
    environment: Any


def observe_current_native_models(repository_root, *, completion_run_manifest,
                                  model_receipt_dir=None, owner_plan_path=None,
                                  validation_receipt_dir=None) -> NativeModelObservation:
    """Read and independently verify exact current model and outer evidence."""
    root = Path(repository_root).resolve()
    if completion_run_manifest is None:
        raise ValueError("completion_run_manifest_required")
    manifest_path = Path(completion_run_manifest).resolve()
    manifest = load_manifest(manifest_path)
    invocation, plan = manifest["invocation"], manifest["plan"]
    model_store = (Path(model_receipt_dir).resolve() if model_receipt_dir is not None
                   else root / ".flowguard/evidence/model-owner-receipts")
    if Path(invocation.get("root", "")).resolve() != root:
        raise ValueError("completion_manifest_foreign_root")
    if Path(invocation.get("model_receipt_dir", "")).resolve() != model_store:
        raise ValueError("completion_manifest_foreign_model_store")
    if validation_receipt_dir is None or Path(invocation.get("receipt_dir", "")).resolve() != Path(validation_receipt_dir).resolve():
        raise ValueError("completion_manifest_foreign_validation_store")
    source = _json(root / ".agents/skills/flowguard/.skillguard/contract-source.json")
    unit = source.get("maintenance_unit_id")
    if (not unit or invocation.get("maintenance_unit_id") != unit
            or plan.get("maintenance_unit_id") != unit
            or invocation.get("completion_work_id") != plan.get("completion_work_id")
            or source.get("member_skill_ids") != ["flowguard"]):
        raise ValueError("completion_manifest_foreign_maintenance_unit")
    for key in ("source_observation_fingerprint", "toolchain_environment_fingerprint",
                "model_authority_fingerprint", "owner_dag_fingerprint", "owner_plan_fingerprint"):
        value = plan.get(key)
        if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
            raise ValueError("completion_manifest_identity_missing:" + key)
    dependency, dependency_verification, owner_path = _full_dependency(
        root, manifest, owner_plan_path, validation_receipt_dir)
    registry = load_native_case_mapping(root)
    registry.assert_current_manifest(root)
    entries = select_entries(ModelRegressionManifest.load(root), tier="full")
    expected = tuple(sorted(entry.model_id for entry in entries))
    if not expected or len(expected) != len(set(expected)):
        raise ValueError("current_native_model_inventory_invalid")
    state = load_current_model_authority_state(root, reverify_current_sources=True)
    authority_ids = {item.logical_model_id for item in state.snapshot.model_instances}
    if set(expected) != authority_ids:
        raise ValueError("current_authority_native_model_inventory_mismatch")
    owner_ids = {"model:" + model_id for model_id in expected}
    if set(registry.bindings_by_owner) != owner_ids:
        raise ValueError("current_native_registry_owner_inventory_mismatch")
    parent = resolve_current_full_model_regression_parent(root, receipt_dir=model_store)
    child_ids = [item.model_id for item in parent.children]
    if sorted(child_ids) != list(expected) or len(set(child_ids)) != len(child_ids):
        raise ValueError("current_native_parent_leaf_inventory_mismatch")
    package = build_model_regression_execution_evidence(
        parent, native_case_bindings_by_owner=registry.bindings_by_owner,
        require_native_case_results=True)
    if not package.complete or {item.owner_id for item in package.owners} != owner_ids:
        raise ValueError("current_native_oracle_or_binding_incomplete")
    children = []
    verifications = {}
    rows = []
    for child in sorted(parent.children, key=lambda row: row.model_id):
        if child.receipt is None or child.verification is None or not child.verification.ok:
            raise ValueError("current_native_leaf_receipt_unverified:" + child.model_id)
        children.append(child.receipt)
        verifications[child.receipt_id] = child.verification
        owner = package.owner("model:" + child.model_id)
        rows.append({"model_id": child.model_id, "receipt_id": child.receipt_id,
                     "receipt_fingerprint": child.receipt_fingerprint,
                     "native_case_ids": list(owner.executed_case_ids),
                     "blueprint_case_ids": list(owner.executed_behavior_case_ids),
                     "bindings": [row.to_dict() for row in owner.native_case_bindings],
                     "native_verification": owner.native_case_verification.to_dict(),
                     "binding_verification": owner.native_case_binding_verification.to_dict()})
    binding = {
        "maintenance_unit_id": unit, "member_ids": ["flowguard"],
        "completion_manifest_fingerprint": manifest["manifest_fingerprint"],
        "completion_work_id": plan["completion_work_id"],
        "source_observation_fingerprint": plan["source_observation_fingerprint"],
        "toolchain_environment_fingerprint": plan["toolchain_environment_fingerprint"],
        "owner_plan_fingerprint": plan["owner_plan_fingerprint"],
        "owner_dag_fingerprint": plan["owner_dag_fingerprint"],
        "outer_native_receipt_id": dependency.receipt_id,
        "outer_native_receipt_fingerprint": dependency.fingerprint,
        "authority_head_fingerprint": state.head.fingerprint,
        "authority_snapshot_fingerprint": state.head.snapshot_fingerprint,
        "authority_revision": state.head.subject_revision,
        "manifest_fingerprint": parent.manifest_fingerprint,
        "mapping_fingerprint": registry.mapping_fingerprint,
        "parent_artifact_fingerprint": parent.parent_artifact_fingerprint,
        "parent_execution_receipt_id": parent.parent_execution_receipt_id,
        "parent_execution_receipt_fingerprint": parent.parent_execution_receipt_fingerprint,
        "model_ids": list(expected), "models": rows,
        "claim_boundary": "Exact current model-policy or implementation scopes stay as authored in each native binding; no blanket product or pending normative promise proof.",
    }
    paths = {
        "completion-manifest": manifest_path, "full-owner-plan": owner_path,
        "native-model-manifest": root / ".flowguard/models/regression-manifest.json",
        "native-model-mapping": Path(registry.path),
        "native-model-parent": Path(parent.parent_artifact_path),
        "native-consumer-code": Path(__file__),
        "native-consumer-cli": root / "scripts/run_flowguard_skill_native_checks.py",
        "native-member-contract": root / ".agents/skills/flowguard/.skillguard/contract-source.json",
        "native-suite-map": root / SUITE_MAP_PATH,
    }
    snapshots = tuple(snapshot_file("input:" + name, path, workspace_root=root,
        hash_policy=INPUT_HASH_BOTH, obligation_ids=(UMBRELLA,))
        for name, path in sorted(paths.items()))
    return NativeModelObservation(binding, snapshots, tuple(children), verifications, _environment())


@dataclass(frozen=True)
class NativeSkillReceiptResult:
    skill_id: str
    receipt: EvidenceReceipt
    proof_path: Path
    runs: tuple = ()

    @property
    def ok(self):
        return self.receipt.result_status == "pass" and self.receipt.exit_code == 0

    def to_dict(self):
        return {"skill_id": self.skill_id, "ok": self.ok,
                "status": self.receipt.result_status, "receipt_id": self.receipt.receipt_id,
                "receipt_fingerprint": self.receipt.fingerprint,
                "proof_path_token": self.receipt.metadata["proof_artifact_path_token"],
                "runs": [], "producer_invocations": 0, "blockers": list(self.receipt.blockers)}


def _proof(observation):
    return {"schema_version": PROOF_SCHEMA, "identity_version": NATIVE_IDENTITY_VERSION,
            "binding": dict(observation.binding), "result_status": "pass", "exit_code": 0,
            "producer_invocations": 0}


def _command(root):
    return tokenize_command(("python", "scripts/run_flowguard_skill_native_checks.py",
                             "--member", "flowguard"), workspace_root=root)


def run_native_skill_check(repository_root, skill_id, *, output_directory=None,
                           completion_run_manifest=None, model_receipt_dir=None,
                           owner_plan_path=None, validation_receipt_dir=None):
    """Publish a native-evidence consumer receipt; never execute native checks."""
    if skill_id != "flowguard":
        raise ValueError("unregistered_native_evidence_member")
    root = Path(repository_root).resolve()
    observation = observe_current_native_models(root,
        completion_run_manifest=completion_run_manifest, model_receipt_dir=model_receipt_dir,
        owner_plan_path=owner_plan_path, validation_receipt_dir=validation_receipt_dir)
    proof = _proof(observation)
    proof_fp = fingerprint_value(proof)
    store = evidence_storage_root(root, output_directory=model_receipt_dir)
    if evidence_storage_root(root, output_directory=output_directory) != store:
        raise ValueError("native_consumer_requires_canonical_model_store")
    proof_path = store / "proofs" / "flowguard" / (proof_fp.split(":", 1)[1] + ".json")
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(proof, sort_keys=True, indent=2) + "\n"
    if proof_path.exists():
        if proof_path.read_text(encoding="utf-8") != encoded:
            raise ValueError("immutable_native_consumer_proof_collision")
    else:
        with proof_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
    now = datetime.now(timezone.utc).isoformat()
    receipt = EvidenceReceipt(
        receipt_id="receipt:flowguard-native-models:" + fingerprint_value({"proof": proof_fp, "observed_at": now}).split(":", 1)[1][:24],
        subject_id=skill_id, subject_kind="flowguard_skill_native_model_consumer",
        producer_id=PRODUCER_ID, producer_version=_package_version(), claim_scope="full",
        command=_command(root), working_directory_token="<WORKSPACE>",
        started_at=now, finished_at=now, exit_code=0,
        environment_fingerprint=observation.environment.fingerprint,
        environment_metadata=observation.environment.metadata,
        contract_hash=fingerprint_value(observation.binding),
        check_manifest_hash=observation.binding["mapping_fingerprint"],
        suite_map_hash=next(item.semantic_sha256 for item in observation.snapshots if item.artifact_id == "input:native-suite-map"),
        input_snapshots=observation.snapshots, proof_artifact_id="proof:native-skill:flowguard",
        proof_artifact_fingerprint=proof_fp, result_status="pass", result_fingerprint=proof_fp,
        covered_obligations=(UMBRELLA,),
        required_child_receipts=tuple(ChildReceiptRequirement(
            receipt_id=item.receipt_id, subject_id=item.subject_id,
            obligation_ids=item.covered_obligations, eligible_claim_scopes=(item.claim_scope,),
            expected_receipt_fingerprint=item.fingerprint) for item in observation.children),
        consumed_child_receipts=tuple(ConsumedChildReceipt(item.receipt_id, item.fingerprint)
                                     for item in observation.children),
        claim_boundary=observation.binding["claim_boundary"],
        metadata={"native_identity_version": NATIVE_IDENTITY_VERSION,
                  "proof_artifact_path_token": tokenize_path(proof_path, workspace_root=root),
                  "proof_filename": proof_path.name,
                  "maintenance_unit_id": observation.binding["maintenance_unit_id"],
                  "producer_invocations": 0})
    save_evidence_receipt(receipt, root, output_directory=model_receipt_dir)
    return NativeSkillReceiptResult(skill_id, receipt, proof_path)


def build_current_native_receipt_context(receipt, repository_root, *,
        completion_run_manifest=None, model_receipt_dir=None, owner_plan_path=None,
        validation_receipt_dir=None, output_directory=None):
    """Rebuild current native bindings and outer evidence; reject old protocols."""
    if (receipt.producer_id != PRODUCER_ID or receipt.subject_id != "flowguard"
            or receipt.subject_kind != "flowguard_skill_native_model_consumer"
            or receipt.metadata.get("native_identity_version") != NATIVE_IDENTITY_VERSION):
        return None
    root = Path(repository_root).resolve()
    try:
        observation = observe_current_native_models(root,
            completion_run_manifest=completion_run_manifest, model_receipt_dir=model_receipt_dir,
            owner_plan_path=owner_plan_path, validation_receipt_dir=validation_receipt_dir)
        expected = _proof(observation)
        fp = fingerprint_value(expected)
        filename = fp.split(":", 1)[1] + ".json"
        if receipt.metadata.get("proof_filename") != filename:
            return None
        if evidence_storage_root(root, output_directory=output_directory) != evidence_storage_root(root, output_directory=model_receipt_dir):
            return None
        path = evidence_storage_root(root, output_directory=model_receipt_dir) / "proofs/flowguard" / filename
        if _json(path) != expected:
            return None
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return ReceiptVerificationContext(
        input_snapshots={item.artifact_id: item for item in observation.snapshots},
        contract_hash=fingerprint_value(observation.binding),
        check_manifest_hash=observation.binding["mapping_fingerprint"],
        suite_map_hash=next(item.semantic_sha256 for item in observation.snapshots if item.artifact_id == "input:native-suite-map"),
        producer_id=PRODUCER_ID, producer_version=_package_version(),
        environment_fingerprint=observation.environment.fingerprint,
        proof_artifact_fingerprint=fp, result_fingerprint=fp, command=_command(root),
        working_directory_token="<WORKSPACE>", proof_artifact_id="proof:native-skill:flowguard",
        required_obligation_ids=(UMBRELLA,), eligible_claim_scopes=("full",),
        child_receipts={item.receipt_id: item for item in observation.children},
        child_verification_results=observation.child_verifications,
        latest_child_receipt_ids={item.subject_id: item.receipt_id for item in observation.children},
        receipt_store_repository_root=str(root),
        receipt_store_output_directory=str(Path(model_receipt_dir).resolve()),
        receipt_store_receipt_ids=(receipt.receipt_id,) + tuple(item.receipt_id for item in observation.children),
        receipt_identity_version=NATIVE_IDENTITY_VERSION)


__all__ = ["NativeModelObservation", "NativeSkillReceiptResult", "PRODUCER_ID",
           "observe_current_native_models", "build_current_native_receipt_context",
           "run_native_skill_check"]
