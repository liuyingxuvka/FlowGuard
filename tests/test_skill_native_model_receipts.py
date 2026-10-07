"""Finite direct-current consumer tests; no model runner is executed.

Official native result/binding verification remains real. The already tested
model-parent resolver and full outer-owner observer are explicit fixture seams,
so these fixtures cannot count as real repository54 native validation.
"""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import hashlib
import json
import pytest

from flowguard import skill_native_checks as native
from flowguard.completion_run_manifest import COMPLETION_RUN_MANIFEST_SCHEMA
from flowguard.evidence_lifecycle import fingerprint_payload
from flowguard.evidence_receipts import (
    EvidenceReceipt, ReceiptVerificationContext, fingerprint_value,
    save_evidence_receipt, snapshot_bytes, verify_evidence_receipt,
)
from flowguard.model_regressions import (
    CurrentModelRegressionChildEvidence, CurrentModelRegressionParentEvidence,
    build_model_regression_execution_evidence,
)
from flowguard.native_case_mapping import NativeCaseMappingRegistry
from flowguard.native_case_protocol import (
    BAD_DIMENSIONS, GOOD_DIMENSIONS, NATIVE_CASE_RESULT_SCHEMA,
    NativeCaseBinding, NativeModelCaseResult, verify_native_case_bindings,
)


def fp(label):
    return "sha256:" + hashlib.sha256(label.encode()).hexdigest()


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def leaf(model_id):
    env = native._environment()
    snapshot = snapshot_bytes("source:" + model_id, model_id.encode(),
                              path_token="<WORKSPACE>/" + model_id + ".py",
                              obligation_ids=("model-regression:" + model_id,))
    receipt = EvidenceReceipt(
        receipt_id="receipt:fixture-model:" + model_id,
        subject_id="validation-owner:model:" + model_id,
        subject_kind="validation_owner", producer_id="validation-owner:model:" + model_id,
        producer_version="1", claim_scope="full", command=("python", "finite-model.py"),
        working_directory_token="<WORKSPACE>", started_at="2026-10-03T00:00:00Z",
        finished_at="2026-10-03T00:00:01Z", exit_code=0,
        environment_fingerprint=env.fingerprint, environment_metadata=env.metadata,
        contract_hash=fp("contract:" + model_id), check_manifest_hash=fp("checks:" + model_id),
        suite_map_hash=fp("suite"), input_snapshots=(snapshot,),
        proof_artifact_id="proof:" + model_id, proof_artifact_fingerprint=fp("proof:" + model_id),
        result_status="pass", result_fingerprint=fp("result:" + model_id),
        covered_obligations=("model-regression:" + model_id,),
        claim_boundary="Only the finite test-owned leaf fixture; no repository native, unit, product, or release qualification.")
    context = ReceiptVerificationContext(
        input_snapshots={snapshot.artifact_id: snapshot}, contract_hash=receipt.contract_hash,
        check_manifest_hash=receipt.check_manifest_hash, suite_map_hash=receipt.suite_map_hash,
        producer_id=receipt.producer_id, producer_version=receipt.producer_version,
        environment_fingerprint=receipt.environment_fingerprint,
        proof_artifact_fingerprint=receipt.proof_artifact_fingerprint,
        result_fingerprint=receipt.result_fingerprint, command=receipt.command,
        working_directory_token=receipt.working_directory_token,
        proof_artifact_id=receipt.proof_artifact_id,
        required_obligation_ids=receipt.covered_obligations, eligible_claim_scopes=("full",))
    return receipt, verify_evidence_receipt(receipt, context)


def fixture(root):
    store = root / "model-receipts"
    store.mkdir()
    paths = [root / ".flowguard/models/regression-manifest.json",
             root / "flowguard/skill_native_checks.py",
             root / "scripts/run_flowguard_skill_native_checks.py",
             root / native.SUITE_MAP_PATH]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    source = root / ".agents/skills/flowguard/.skillguard/contract-source.json"
    write(source, {"maintenance_unit_id": "unit:flowguard-suite", "member_skill_ids": ["flowguard"]})
    validation = root / "validation-receipts"
    validation.mkdir()
    manifest = {"schema_version": COMPLETION_RUN_MANIFEST_SCHEMA,
        "invocation": {"root": str(root), "maintenance_unit_id": "unit:flowguard-suite",
                       "model_receipt_dir": str(store), "receipt_dir": str(validation),
                       "completion_work_id": "work:finite"},
        "plan": {"maintenance_unit_id": "unit:flowguard-suite", "completion_work_id": "work:finite",
                 **{key: fp(key) for key in ("source_observation_fingerprint",
                    "toolchain_environment_fingerprint", "model_authority_fingerprint",
                    "owner_dag_fingerprint", "owner_plan_fingerprint")}}}
    manifest["manifest_fingerprint"] = fingerprint_payload(manifest)
    manifest_path = write(root / "completion-run-manifest.json", manifest)
    bindings, children = [], []
    mapping_fp = fp("finite-mapping")
    for model_id, kind in (("alpha", "good"), ("beta", "bad")):
        dimensions = GOOD_DIMENSIONS if kind == "good" else BAD_DIMENSIONS
        observed = "pass" if kind == "good" else "violation"
        failure_ids = () if kind == "good" else ("failure:protected",)
        binding = NativeCaseBinding(
            owner_id="model:" + model_id, blueprint_case_id="blueprint:" + model_id,
            blueprint_source_case_id="source:" + model_id, native_case_ids=("native:" + model_id,),
            case_kind=kind, evidence_scope="model_policy", covered_dimensions=dimensions,
            expected_status="pass", expected_observed_status=observed,
            protected_failure_ids=failure_ids, expected_finding_codes=failure_ids,
            mapping_fingerprint=mapping_fp)
        bindings.append(binding)
        raw_path = root / model_id / "raw.json"
        raw_path.parent.mkdir()
        raw_path.write_text("finite actual native result", encoding="utf-8")
        result = NativeModelCaseResult(
            owner_id=binding.owner_id, source_case_id=binding.native_case_ids[0],
            outcome="pass", observed_status=observed, observed_finding_codes=failure_ids,
            executed_dimensions=dimensions,
            oracle_results=tuple({"dimension": dimension, "oracle_member_id": "assert:" + dimension,
                                  "status": observed, "ok": True} for dimension in dimensions),
            result_artifact_fingerprint="sha256:" + hashlib.sha256(raw_path.read_bytes()).hexdigest(),
            input_fingerprint=fp(model_id + ":input"), model_fingerprint=fp(model_id + ":model"),
            code_fingerprint=fp(model_id + ":code"), test_fingerprint=fp(model_id + ":test"),
            oracle_fingerprint=fp(model_id + ":oracle"), toolchain_fingerprint=fp("toolchain"),
            environment_fingerprint=fp("environment"), raw_artifact_path="raw.json")
        artifact = write(raw_path.parent / "results.json",
                         {"schema_version": NATIVE_CASE_RESULT_SCHEMA, "results": [result.to_dict()]})
        receipt, verification = leaf(model_id)
        save_evidence_receipt(receipt, root, output_directory=store)
        children.append(CurrentModelRegressionChildEvidence(
            model_id=model_id, receipt_id=receipt.receipt_id, receipt_fingerprint=receipt.fingerprint,
            receipt=receipt, verification=verification,
            executed_case_ids=(result.source_case_id,), native_case_results=(result,),
            native_case_result_artifact_path=str(artifact),
            native_case_result_artifact_fingerprint="sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()))
    mapping_path = write(root / "mapping.json", {"finite": True})
    registry = NativeCaseMappingRegistry(mapping_fingerprint=mapping_fp,
        source_manifest_fingerprint=fp("manifest"), source_paths=("model.py",),
        bindings=tuple(bindings), path=str(mapping_path))
    parent_path = write(store / "parent.json", {"finite": True})
    parent = CurrentModelRegressionParentEvidence(
        manifest_fingerprint=fp("manifest"), parent_artifact_path=str(parent_path),
        parent_artifact_fingerprint=fp("parent-artifact"), parent_execution_receipt_id="receipt:parent",
        parent_execution_receipt_fingerprint=fp("parent"), children=tuple(children))
    # Baseline must satisfy the real typed leaf and native oracle/binding
    # contract before any negative test mutates one declared dimension.
    package = build_model_regression_execution_evidence(parent,
        native_case_bindings_by_owner=registry.bindings_by_owner,
        require_native_case_results=True)
    assert package.complete, package.to_dict()
    owner_path = write(root / "owner-plan.json", {"finite": True})
    dependency, dep_verification = leaf("outer05")
    args = dict(completion_run_manifest=manifest_path, model_receipt_dir=store,
                owner_plan_path=owner_path, validation_receipt_dir=validation)
    return SimpleNamespace(root=root, store=store, manifest=manifest, args=args,
        registry=registry, parent=parent, owner_path=owner_path,
        dependency=dependency, dep_verification=dep_verification)


class Observers:
    def __init__(self, fixture):
        self.fixture = fixture
        self.stack = None
    def __enter__(self):
        from contextlib import ExitStack
        f = self.fixture
        self.stack = ExitStack()
        for target, kw in (
            ("_full_dependency", {"return_value": (f.dependency, f.dep_verification, f.owner_path)}),
            ("load_native_case_mapping", {"return_value": f.registry}),
            ("select_entries", {"return_value": tuple(SimpleNamespace(model_id=x) for x in ("alpha", "beta"))}),
            ("load_current_model_authority_state", {"return_value": SimpleNamespace(
                snapshot=SimpleNamespace(model_instances=tuple(SimpleNamespace(logical_model_id=x) for x in ("alpha", "beta"))),
                head=SimpleNamespace(fingerprint=fp("head"), snapshot_fingerprint=fp("snapshot"), subject_revision="revision:fixture"))}),
            ("resolve_current_full_model_regression_parent", {"side_effect": lambda *a, **kw: f.parent}),
        ):
            self.stack.enter_context(patch.object(native, target, **kw))
        self.stack.enter_context(patch.object(native.ModelRegressionManifest, "load", return_value=object()))
        self.stack.enter_context(patch.object(NativeCaseMappingRegistry, "assert_current_manifest", return_value=fp("manifest")))
        self.stack.enter_context(patch("subprocess.run", side_effect=AssertionError("native consumer executed subprocess")))
        return self
    def __exit__(self, *args):
        return self.stack.__exit__(*args)


def test_two_real_native_oracle_bindings_consume_without_runner_and_roundtrip(tmp_path):
    f = fixture(tmp_path)
    with Observers(f):
        result = native.run_native_skill_check(tmp_path, "flowguard", output_directory=f.store, **f.args)
        context = native.build_current_native_receipt_context(result.receipt, tmp_path,
                                                              output_directory=f.store, **f.args)
        verified = verify_evidence_receipt(result.receipt, context)
    assert result.ok and verified.ok, verified.to_dict()
    assert len(result.receipt.required_child_receipts) == 2
    assert result.to_dict()["producer_invocations"] == 0
    assert result.runs == ()
    proof = json.loads(result.proof_path.read_text())
    assert proof["binding"]["models"][1]["native_verification"]["ok"]
    assert proof["binding"]["models"][1]["bindings"][0]["expected_observed_status"] == "violation"
    assert proof["binding"]["maintenance_unit_id"] == "unit:flowguard-suite"


@pytest.mark.parametrize("mutation", ["missing-leaf", "foreign-leaf", "bad-oracle", "missing-protected-finding"])
def test_missing_foreign_or_bad_native_evidence_blocks(tmp_path, mutation):
    f = fixture(tmp_path)
    if mutation == "missing-leaf":
        f.parent = replace(f.parent, children=f.parent.children[:1])
    elif mutation == "foreign-leaf":
        f.parent = replace(f.parent, children=(f.parent.children[0], replace(f.parent.children[1], model_id="foreign")))
    else:
        child = f.parent.children[1]
        row = child.native_case_results[0]
        if mutation == "bad-oracle":
            row = replace(row, oracle_results=tuple(dict(item, ok=False) for item in row.oracle_results))
        else:
            row = replace(row, observed_finding_codes=())
        path = Path(child.native_case_result_artifact_path)
        write(path, {"schema_version": NATIVE_CASE_RESULT_SCHEMA, "results": [row.to_dict()]})
        child = replace(child, native_case_results=(row,),
                        native_case_result_artifact_fingerprint="sha256:" + hashlib.sha256(path.read_bytes()).hexdigest())
        f.parent = replace(f.parent, children=(f.parent.children[0], child))
    with Observers(f), pytest.raises(ValueError, match="inventory_mismatch|oracle_or_binding_incomplete"):
        native.run_native_skill_check(tmp_path, "flowguard", output_directory=f.store, **f.args)
    assert not (f.store / "proofs").exists()


@pytest.mark.parametrize("field", ["maintenance_unit_id", "model_receipt_dir", "receipt_dir", "root"])
def test_validly_hashed_foreign_unit_or_store_still_blocks(tmp_path, field):
    f = fixture(tmp_path)
    changed = json.loads(json.dumps(f.manifest))
    changed["invocation"][field] = "unit:foreign" if field == "maintenance_unit_id" else str(tmp_path / "foreign")
    changed.pop("manifest_fingerprint")
    changed["manifest_fingerprint"] = fingerprint_payload(changed)
    write(f.args["completion_run_manifest"], changed)
    with Observers(f), pytest.raises(ValueError, match="foreign"):
        native.observe_current_native_models(tmp_path, **f.args)


def test_missing_actual_outer_context_is_not_unit_qualification(tmp_path):
    f = fixture(tmp_path)
    with pytest.raises(ValueError, match="same_unit_outer_context_not_proven"):
        native._full_dependency(tmp_path, f.manifest, None, None)


def test_missing_parent_and_input_drift_do_not_publish_native_pass(tmp_path):
    f = fixture(tmp_path)
    with Observers(f):
        with patch.object(native, "resolve_current_full_model_regression_parent",
                          side_effect=ValueError("current parent missing")), pytest.raises(ValueError, match="parent missing"):
            native.run_native_skill_check(tmp_path, "flowguard", output_directory=f.store, **f.args)
        result = native.run_native_skill_check(tmp_path, "flowguard", output_directory=f.store, **f.args)
        (tmp_path / "scripts/run_flowguard_skill_native_checks.py").write_text("changed code", encoding="utf-8")
        context = native.build_current_native_receipt_context(result.receipt, tmp_path,
                                                              output_directory=f.store, **f.args)
        assert not verify_evidence_receipt(result.receipt, context).ok


def test_changed_environment_and_tampered_proof_fail_currentness(tmp_path):
    f = fixture(tmp_path)
    with Observers(f):
        result = native.run_native_skill_check(tmp_path, "flowguard", output_directory=f.store, **f.args)
        from flowguard.evidence_receipts import build_environment_fingerprint
        with patch.object(native, "_environment", return_value=build_environment_fingerprint({"python_version": "foreign"})):
            context = native.build_current_native_receipt_context(result.receipt, tmp_path,
                                                                  output_directory=f.store, **f.args)
            assert not verify_evidence_receipt(result.receipt, context).ok
        proof = json.loads(result.proof_path.read_text())
        proof["binding"]["maintenance_unit_id"] = "unit:foreign"
        write(result.proof_path, proof)
        assert native.build_current_native_receipt_context(result.receipt, tmp_path,
                                                           output_directory=f.store, **f.args) is None


def test_retired_protocol_receipt_cannot_use_new_current_reader(tmp_path):
    receipt, _ = leaf("retired")
    receipt = replace(receipt, subject_id="flowguard", producer_id="flowguard.skill_native_checks",
                      metadata={"native_identity_version": "2"})
    with patch.object(native, "observe_current_native_models", side_effect=AssertionError("retired reader must reject before observation")):
        assert native.build_current_native_receipt_context(receipt, tmp_path) is None


def test_native_outer_owner_requires_exact_unit_and_work_projection():
    from flowguard.validation_ownership import ValidationOwnerContract
    invocation = {"maintenance_unit_id": "unit:flowguard-suite", "completion_work_id": "work:finite"}
    fingerprint = native._native_owner_unit_fingerprint(**invocation)
    contract = ValidationOwnerContract(owner_id="model_regressions_full",
        command=("python", "models.py"), input_patterns=("model.py",),
        obligation_ids=("validation:model_regressions_full",),
        projected_inputs=((native.NATIVE_OWNER_UNIT_COMPONENT, fingerprint),))
    native._require_native_owner_unit(contract, invocation)
    for foreign in ({**invocation, "maintenance_unit_id": "unit:foreign"},
                    {**invocation, "completion_work_id": "work:foreign"}):
        with pytest.raises(ValueError, match="completion_unit_projection_mismatch"):
            native._require_native_owner_unit(contract, foreign)
    with pytest.raises(ValueError, match="completion_unit_projection_mismatch"):
        native._require_native_owner_unit(replace(contract, projected_inputs=()), invocation)


def test_foreign_unit_outer_receipt_cannot_match_actual_current_owner(tmp_path):
    import sys
    from flowguard.validation_owner_execution import execute_validation_owner_command
    from flowguard.validation_ownership import ValidationOwnerContract, build_owner_current, build_owner_receipt_context
    (tmp_path / "model.py").write_text("current finite model", encoding="utf-8")
    ids = {"maintenance_unit_id": "unit:flowguard-suite", "completion_work_id": "work:finite"}
    contract = ValidationOwnerContract(owner_id="model_regressions_full",
        command=(sys.executable, "-c", "print('finite-owner-unit-fixture')"),
        input_patterns=("model.py",), obligation_ids=("validation:model_regressions_full",),
        projected_inputs=((native.NATIVE_OWNER_UNIT_COMPONENT, native._native_owner_unit_fingerprint(**ids)),))
    current = build_owner_current(tmp_path, contract, all_contracts=(contract,))
    store = tmp_path / "validation-receipts"
    # Execute only this finite print fixture, never a model/native/full runner.
    # The official supervisor and publisher own the actual terminal and proof.
    result = execute_validation_owner_command(current, tmp_path, store,
        all_contracts=(contract,), child_id="model_regressions_full",
        evidence_context={"fixture_scope": "exact native owner unit projection"},
        summary="Finite actual owner receipt unit fixture",
        claim_boundary="Only one finite print command; no native model qualification.")
    assert result.ok, result.blocker
    assert result.receipt is not None
    assert result.verification is not None and result.verification.ok
    assert result.supervised.ok and result.supervised.cleanup_confirmed
    proof = store / result.receipt.metadata["proof_relpath"]
    assert proof.is_file()
    actual_context = build_owner_receipt_context(current, result.receipt, store)
    assert actual_context is not None
    assert verify_evidence_receipt(result.receipt, actual_context).ok
    for foreign_ids in ({**ids, "maintenance_unit_id": "unit:foreign"},
                        {**ids, "completion_work_id": "work:foreign"}):
        foreign = replace(contract, projected_inputs=((native.NATIVE_OWNER_UNIT_COMPONENT,
            native._native_owner_unit_fingerprint(**foreign_ids)),))
        foreign_current = build_owner_current(tmp_path, foreign, all_contracts=(foreign,))
        assert current.owner_identity != foreign_current.owner_identity
        context = build_owner_receipt_context(foreign_current, result.receipt, store)
        assert context is not None
        verification = verify_evidence_receipt(result.receipt, context)
        assert not verification.ok
        assert "contract_hash_mismatch" in {item.code for item in verification.findings}
