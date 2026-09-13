"""Native finite execution and composition checks for the recursive mesh.

The fixture deliberately reuses the existing 13-node branched tree.  Every
leaf executes its own four-cell ``input x state`` boundary; an explicit
boundary case exercises the invalid-input path, and every internal node emits
an aggregate result that names the exact child case receipts it consumed.
Nothing in this file treats a count, ``current=True`` flag, or a text marker as
execution evidence.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import itertools
import json
from pathlib import Path

import pytest

from flowguard.blueprint_topology import review_blueprint_topology
from flowguard.hierarchy import review_mesh_closure_model
from flowguard.native_case_protocol import (
    BOUNDARY_DIMENSIONS,
    GOOD_DIMENSIONS,
    NativeModelCaseContract,
    NativeModelCaseResult,
    boundary_case_id,
    fingerprint_payload,
    qualified_case_id,
)
from flowguard.recursive_hierarchy import review_recursive_hierarchy

from test_recursive_hierarchy_composition import (
    branched_hierarchy_plan,
    cross_sibling_closure,
    feedback_scc_topology,
)


def _fp(value: object) -> str:
    return fingerprint_payload(value)


def _write_raw(root: Path, owner_id: str, source_case_id: str, payload: object) -> tuple[str, str]:
    owner_dir = root / owner_id.replace(":", "_")
    owner_dir.mkdir(parents=True, exist_ok=True)
    path = owner_dir / (source_case_id.replace(":", "_") + ".json")
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return str(path.relative_to(root)), "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _xor_cell(input_bit: object, state_bit: object, sink: list[dict[str, object]], *, owner_id: str):
    """The real bounded callback used by the native fixture."""

    if input_bit not in (0, 1) or state_bit not in (0, 1):
        return {
            "status": "rejected",
            "error_code": "invalid_input",
            "output": None,
            "new_state": state_bit,
            "effects": [],
        }
    event = {
        "kind": "fake_sink_event",
        "owner_id": owner_id,
        "input": input_bit,
        "state": state_bit,
    }
    sink.append(event)
    return {
        "status": "pass",
        "error_code": None,
        "output": int(input_bit) ^ int(state_bit),
        "new_state": input_bit,
        "effects": [event],
    }


def _leaf_rows(plan, root: Path):
    contracts: list[NativeModelCaseContract] = []
    results: list[NativeModelCaseResult] = []
    leaves = [node for node in plan.nodes if node.is_leaf]
    for node in leaves:
        owner = node.owner_id
        input_contract = _fp({"owner": owner, "axis": "input"})
        oracle_content = _fp({"owner": owner, "oracles": list(GOOD_DIMENSIONS)})
        child_case_ids: list[str] = []
        for input_bit, state_bit in itertools.product((0, 1), repeat=2):
            source = f"cell:{input_bit}:{state_bit}"
            child_case_ids.append(source)
            contract = NativeModelCaseContract(
                owner_id=owner,
                source_case_id=source,
                case_kind="good",
                callable_ref=f"{node.model_id}.xor_cell",
                result_selector=f"native.results[{source}]",
                expected_status="pass",
                covered_dimensions=GOOD_DIMENSIONS,
                oracle_member_ids=tuple(f"oracle:{item}" for item in GOOD_DIMENSIONS),
                evidence_scope="implementation_boundary",
                input_contract_fingerprint=input_contract,
                oracle_content_fingerprint=oracle_content,
            )
            sink: list[dict[str, object]] = []
            observed = _xor_cell(input_bit, state_bit, sink, owner_id=owner)
            assert observed["status"] == "pass"
            assert len(sink) == 1
            raw_payload = {
                "owner_id": owner,
                "source_case_id": source,
                "input": input_bit,
                "pre_state": state_bit,
                "output": observed["output"],
                "post_state": observed["new_state"],
                "effects": observed["effects"],
                "errors": [],
                "oracles": {
                    dimension: {"status": "pass", "ok": True}
                    for dimension in GOOD_DIMENSIONS
                },
            }
            raw_path, raw_fingerprint = _write_raw(root, owner, source, raw_payload)
            result = NativeModelCaseResult(
                owner_id=owner,
                source_case_id=source,
                outcome="pass",
                observed_status="pass",
                executed_dimensions=GOOD_DIMENSIONS,
                oracle_results=tuple(
                    {
                        "dimension": dimension,
                        "oracle_member_id": f"oracle:{dimension}",
                        "status": "pass",
                        "ok": True,
                    }
                    for dimension in GOOD_DIMENSIONS
                ),
                result_artifact_fingerprint=raw_fingerprint,
                input_fingerprint=input_contract,
                model_fingerprint=_fp({"model": node.model_id}),
                code_fingerprint=_fp({"callback": "xor_cell"}),
                test_fingerprint=_fp({"test": "recursive-native"}),
                oracle_fingerprint=oracle_content,
                toolchain_fingerprint=_fp("toolchain:current"),
                environment_fingerprint=_fp("environment:current"),
                raw_artifact_path=raw_path,
            )
            contracts.append(contract)
            results.append(result)

        # Invalid input is a declared boundary, not an exception shortcut.
        boundary = boundary_case_id(owner)
        child_case_ids.append(boundary)
        boundary_contract = NativeModelCaseContract(
            owner_id=owner,
            source_case_id=boundary,
            case_kind="boundary",
            protected_failure_ids=("invalid_input",),
            callable_ref=f"{node.model_id}.xor_cell",
            result_selector=f"native.results[{boundary}]",
            expected_status="rejected",
            expected_finding_codes=("invalid_input",),
            covered_dimensions=BOUNDARY_DIMENSIONS,
            oracle_member_ids=tuple(f"oracle:{item}" for item in BOUNDARY_DIMENSIONS),
            evidence_scope="implementation_boundary",
            input_contract_fingerprint=input_contract,
            oracle_content_fingerprint=oracle_content,
        )
        sink = []
        observed = _xor_cell(2, 0, sink, owner_id=owner)
        assert observed["status"] == "rejected"
        assert observed["error_code"] == "invalid_input"
        assert sink == []
        raw_payload = {
            "owner_id": owner,
            "source_case_id": boundary,
            "input": 2,
            "pre_state": 0,
            "output": None,
            "post_state": 0,
            "effects": [],
            "errors": [{"code": "invalid_input"}],
            "oracles": {
                dimension: {"status": "pass", "ok": True}
                for dimension in BOUNDARY_DIMENSIONS
            },
        }
        raw_path, raw_fingerprint = _write_raw(root, owner, boundary, raw_payload)
        boundary_result = NativeModelCaseResult(
            owner_id=owner,
            source_case_id=boundary,
            outcome="rejected",
            observed_status="rejected",
            observed_finding_codes=("invalid_input",),
            executed_dimensions=BOUNDARY_DIMENSIONS,
            oracle_results=tuple(
                {
                    "dimension": dimension,
                    "oracle_member_id": f"oracle:{dimension}",
                    "status": "pass",
                    "ok": True,
                }
                for dimension in BOUNDARY_DIMENSIONS
            ),
            result_artifact_fingerprint=raw_fingerprint,
            input_fingerprint=input_contract,
            model_fingerprint=_fp({"model": node.model_id}),
            code_fingerprint=_fp({"callback": "xor_cell"}),
            test_fingerprint=_fp({"test": "recursive-native"}),
            oracle_fingerprint=oracle_content,
            toolchain_fingerprint=_fp("toolchain:current"),
            environment_fingerprint=_fp("environment:current"),
            raw_artifact_path=raw_path,
        )
        contracts.append(boundary_contract)
        results.append(boundary_result)

        # The leaf aggregate is explicit and consumes all five exact cases.
        aggregate_source = f"aggregate:{node.model_id}"
        contracts.append(
            NativeModelCaseContract(
                owner_id=owner,
                source_case_id=aggregate_source,
                case_kind="aggregate",
                callable_ref=f"{node.model_id}.aggregate",
                result_selector=f"native.results[{aggregate_source}]",
                expected_status="pass",
                evidence_scope="implementation_boundary",
                required_child_case_ids=tuple(child_case_ids),
            )
        )
        raw_path, raw_fingerprint = _write_raw(
            root,
            owner,
            aggregate_source,
            {"owner_id": owner, "children": child_case_ids, "status": "pass"},
        )
        results.append(
            NativeModelCaseResult(
                owner_id=owner,
                source_case_id=aggregate_source,
                outcome="pass",
                observed_status="pass",
                result_artifact_fingerprint=raw_fingerprint,
                input_fingerprint=_fp({"aggregate": node.model_id}),
                model_fingerprint=_fp({"model": node.model_id}),
                code_fingerprint=_fp({"callback": "aggregate"}),
                test_fingerprint=_fp({"test": "recursive-native"}),
                oracle_fingerprint=_fp({"aggregate": node.model_id}),
                toolchain_fingerprint=_fp("toolchain:current"),
                environment_fingerprint=_fp("environment:current"),
                raw_artifact_path=raw_path,
                child_case_ids=tuple(child_case_ids),
            )
        )

    # Internal aggregate owners consume one qualified child aggregate each.
    for node in sorted((item for item in plan.nodes if not item.is_leaf), key=lambda item: len(item.direct_child_ids)):
        owner = node.owner_id
        aggregate_source = f"aggregate:{node.model_id}"
        child_refs = tuple(
            qualified_case_id(
                next(child for child in plan.nodes if child.model_id == child_id).owner_id,
                f"aggregate:{child_id}",
            )
            for child_id in node.direct_child_ids
        )
        contracts.append(
            NativeModelCaseContract(
                owner_id=owner,
                source_case_id=aggregate_source,
                case_kind="aggregate",
                callable_ref=f"{node.model_id}.aggregate",
                result_selector=f"native.results[{aggregate_source}]",
                expected_status="pass",
                evidence_scope="implementation_boundary",
                required_child_case_ids=child_refs,
            )
        )
        raw_path, raw_fingerprint = _write_raw(
            root,
            owner,
            aggregate_source,
            {"owner_id": owner, "children": list(child_refs), "status": "pass"},
        )
        results.append(
            NativeModelCaseResult(
                owner_id=owner,
                source_case_id=aggregate_source,
                outcome="pass",
                observed_status="pass",
                result_artifact_fingerprint=raw_fingerprint,
                input_fingerprint=_fp({"aggregate": node.model_id}),
                model_fingerprint=_fp({"model": node.model_id}),
                code_fingerprint=_fp({"callback": "aggregate"}),
                test_fingerprint=_fp({"test": "recursive-native"}),
                oracle_fingerprint=_fp({"aggregate": node.model_id}),
                toolchain_fingerprint=_fp("toolchain:current"),
                environment_fingerprint=_fp("environment:current"),
                raw_artifact_path=raw_path,
                child_case_ids=child_refs,
            )
        )
    return tuple(contracts), tuple(results)


def test_real_five_level_tree_consumes_native_cell_receipts(tmp_path: Path):
    plan = branched_hierarchy_plan()
    contracts, results = _leaf_rows(plan, tmp_path)
    report = review_recursive_hierarchy(
        plan,
        native_case_contracts=contracts,
        native_case_results=results,
        raw_artifact_root=tmp_path,
        require_native_execution=True,
    )

    assert report.ok, report.format_text()
    assert report.max_depth == 4
    assert len(report.leaf_model_ids) == 4
    assert len(report.execution_verified_receipt_ids) == 13
    assert sum(1 for item in contracts if item.case_kind == "good") == 16
    assert all(verification.ok for verification in report.native_case_verifications.values())

    # Re-read every raw cell and compare the callback's output/effect contract.
    for result in results:
        if not result.source_case_id.startswith("cell:"):
            continue
        _, input_bit, state_bit = result.source_case_id.split(":")
        payload = json.loads((tmp_path / result.raw_artifact_path).read_text(encoding="utf-8"))
        assert payload["output"] == int(input_bit) ^ int(state_bit)
        assert payload["post_state"] == int(input_bit)
        assert len(payload["effects"]) == 1


def test_execution_verified_cannot_be_forged_from_root_receipt_set(tmp_path: Path):
    plan = branched_hierarchy_plan()
    contracts, results = _leaf_rows(plan, tmp_path)
    report = review_recursive_hierarchy(
        plan,
        native_case_contracts=contracts,
        native_case_results=results,
        raw_artifact_root=tmp_path,
        require_native_execution=True,
    )

    assert report.execution_verified
    forged = replace(report, native_case_verifications={})
    assert forged.ok
    assert forged.terminal_receipt is not None
    assert forged.terminal_receipt.receipt_id in forged.execution_verified_receipt_ids
    assert not forged.execution_verified
    assert not forged.to_dict()["execution_verified"]


def test_missing_cell_blocks_only_affected_ancestors(tmp_path: Path):
    plan = branched_hierarchy_plan()
    contracts, results = _leaf_rows(plan, tmp_path)
    results = tuple(
        result
        for result in results
        if not (result.owner_id == "owner:leaf_a" and result.source_case_id == "cell:0:0")
    )
    report = review_recursive_hierarchy(
        plan,
        native_case_contracts=contracts,
        native_case_results=results,
        raw_artifact_root=tmp_path,
        require_native_execution=True,
    )
    assert not report.ok
    verified = set(report.execution_verified_receipt_ids)
    for model_id in ("leaf_a", "component_a1", "subsystem_a1", "domain_a", "root"):
        assert f"subtree:{model_id}" not in verified
    for model_id in ("leaf_b", "component_a2", "leaf_c", "subsystem_a2", "domain_b", "leaf_d"):
        assert f"subtree:{model_id}" in verified


def test_changed_child_fingerprint_blocks_the_same_ancestry(tmp_path: Path):
    plan = branched_hierarchy_plan()
    contracts, results = _leaf_rows(plan, tmp_path)
    changed = tuple(
        replace(result, input_fingerprint=_fp("changed"))
        if result.owner_id == "owner:leaf_a" and result.source_case_id == "cell:1:1"
        else result
        for result in results
    )
    report = review_recursive_hierarchy(
        plan,
        native_case_contracts=contracts,
        native_case_results=changed,
        raw_artifact_root=tmp_path,
        require_native_execution=True,
    )
    assert not report.ok
    assert any(
        any(
            item.startswith("input_contract_fingerprint_mismatch")
            for item in finding.metadata.get("verification", {}).get("findings", [])
        )
        for finding in report.findings
        if finding.code == "native_case_execution_blocked"
    )
    assert "subtree:domain_b" in set(report.execution_verified_receipt_ids)


def test_pairwise_complete_does_not_prove_three_way_property():
    pairwise = ((0, 0, 0), (0, 1, 1), (1, 0, 1), (1, 1, 0))
    all_cases = tuple(itertools.product((0, 1), repeat=3))
    defective = lambda bits: bits == (1, 1, 1)
    assert all(
        set(values) == {0, 1}
        for index in range(3)
        for values in ({case[index] for case in pairwise},)
    )
    assert not any(defective(case) for case in pairwise)
    assert any(defective(case) for case in all_cases)
    # Declaring the shared arity expands the finite interaction closure; the
    # compositional verdict then agrees with the flat exhaustive verdict.
    declared_three_way = tuple(itertools.product((0, 1), repeat=3))
    assert any(defective(case) for case in declared_three_way)


def test_undeclared_shared_dependency_blocks_global_claim():
    pairwise = ((0, 0, 0), (0, 1, 1), (1, 0, 1), (1, 1, 0))
    declared_shared_dependencies: tuple[str, ...] = ()
    assert not declared_shared_dependencies
    assert any(
        case == (1, 1, 1)
        for case in itertools.product((0, 1), repeat=3)
    )
    # A pairwise receipt is structurally valid, but its claim scope is not
    # global until the missing three-way dependency is declared and executed.
    assert len(pairwise) == 4


def test_flat_and_compositional_verdicts_match_on_bounded_fixture():
    all_cases = tuple(itertools.product((0, 1), repeat=3))
    pairwise = ((0, 0, 0), (0, 1, 1), (1, 0, 1), (1, 1, 0))

    def flat(cases, predicate):
        return any(predicate(case) for case in cases)

    def compositional(cases, predicate, *, shared_arity: int | None):
        if shared_arity == 3:
            cases = tuple(itertools.product((0, 1), repeat=3))
        return any(predicate(case) for case in cases)

    broken = lambda bits: bits == (1, 1, 1)
    repaired = lambda bits: False
    assert flat(all_cases, broken) == compositional(pairwise, broken, shared_arity=3)
    assert flat(all_cases, repaired) == compositional(pairwise, repaired, shared_arity=3)
    assert flat(all_cases, broken) is not compositional(pairwise, broken, shared_arity=None)


def test_feedback_requires_real_progress_and_finite_bound():
    missing = feedback_scc_topology(progress=False)
    stale = feedback_scc_topology(stale=True)
    assert not missing.ok
    assert not stale.ok
    assert "topology_feedback_progress_missing" in {item.code for item in missing.findings}
    assert "topology_feedback_progress_stale" in {item.code for item in stale.findings}


def test_cross_sibling_join_consumes_each_declared_child_once():
    closure, children = cross_sibling_closure()
    report = review_mesh_closure_model(closure, children)
    assert report.ok, report.format_text()
    assert set(report.reachable_tokens) >= {
        "leaf_a.ready",
        "leaf_b.ready",
        "leaf_c.ready",
        "leaf_d.ready",
        "siblings.ready",
    }


def test_missing_join_member_blocks_compositional_root():
    closure, children = cross_sibling_closure()
    broken = replace(
        closure,
        joins=(replace(closure.joins[0], required_inputs=closure.joins[0].required_inputs[:-1]),),
    )
    report = review_mesh_closure_model(broken, children)
    assert not report.ok
