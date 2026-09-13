from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from flowguard.native_case_protocol import (
    BAD_DIMENSIONS,
    GOOD_DIMENSIONS,
    NativeCaseBinding,
    NativeCaseProtocolError,
    NativeModelCaseContract,
    NativeModelCaseResult,
    boundary_case_id,
    load_native_model_case_results,
    qualified_case_id,
    verify_native_model_cases,
)
from flowguard.native_case_mapping import (
    NATIVE_CASE_MAPPING_SCHEMA,
    NativeCaseMappingError,
    NativeCaseMappingRegistry,
    compute_native_case_mapping_fingerprint,
    load_native_case_mapping,
)
from flowguard.source_identity import source_file_fingerprint


def _fp(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _good_contract(owner: str = "model:alpha", case: str = "case:good") -> NativeModelCaseContract:
    return NativeModelCaseContract(
        owner_id=owner,
        source_case_id=case,
        case_kind="good",
        callable_ref="model.alpha.good",
        result_selector="report.case_results[case:good]",
        expected_status="pass",
        covered_dimensions=GOOD_DIMENSIONS,
        oracle_member_ids=tuple(f"oracle:{item}" for item in GOOD_DIMENSIONS),
        evidence_scope="model_policy",
        input_contract_fingerprint=_fp("input"),
        oracle_content_fingerprint=_fp("oracle"),
    )


def _result(contract: NativeModelCaseContract, *, dimensions=None, finding_codes=()):
    dimensions = tuple(dimensions or contract.covered_dimensions)
    return NativeModelCaseResult(
        owner_id=contract.owner_id,
        source_case_id=contract.source_case_id,
        outcome=contract.expected_status,
        observed_status=contract.expected_status,
        observed_finding_codes=tuple(finding_codes),
        executed_dimensions=dimensions,
        oracle_results=tuple(
            {
                "dimension": dimension,
                "oracle_member_id": f"oracle:{dimension}",
                "status": "pass",
                "ok": True,
            }
            for dimension in dimensions
        ),
        result_artifact_fingerprint=_fp("raw"),
        input_fingerprint=_fp("input"),
        model_fingerprint=_fp("model"),
        code_fingerprint=_fp("code"),
        test_fingerprint=_fp("test"),
        oracle_fingerprint=_fp("oracle"),
        toolchain_fingerprint=_fp("toolchain"),
        environment_fingerprint=_fp("environment"),
        raw_artifact_path="raw.json",
    )


def test_boundary_id_is_stable_when_runner_content_changes():
    assert boundary_case_id("model:alpha") == "boundary:alpha"
    assert boundary_case_id("model:alpha") == boundary_case_id("model:alpha")


def test_native_source_case_maps_to_one_exact_blueprint_case():
    contract = _good_contract()
    result = _result(contract)
    report = verify_native_model_cases((contract,), (result,))
    assert report.ok
    assert report.leaf_case_ids == ("model:alpha:case:good",)


def test_unasserted_dimension_remains_not_run():
    contract = _good_contract()
    result = _result(contract, dimensions=GOOD_DIMENSIONS[:-1])
    report = verify_native_model_cases((contract,), (result,))
    assert not report.ok
    assert "model:alpha:case:good:completion" in report.unasserted_dimensions


def test_missing_foreign_and_duplicate_case_blocks():
    contract = _good_contract()
    first = _result(contract)
    foreign_payload = first.to_dict()
    foreign_payload.pop("schema_version", None)
    foreign_payload["source_case_id"] = "foreign"
    foreign = NativeModelCaseResult(**foreign_payload)
    report = verify_native_model_cases((contract,), (first, first, foreign))
    assert not report.ok
    assert report.duplicate_case_ids
    assert report.foreign_case_ids == ("model:alpha:foreign",)


def test_aggregate_proof_cannot_substitute_for_children():
    child = _good_contract(case="case:child")
    aggregate = NativeModelCaseContract(
        owner_id="model:alpha",
        source_case_id="case:aggregate",
        case_kind="aggregate",
        callable_ref="model.alpha.suite",
        result_selector="report.aggregate",
        expected_status="pass",
        evidence_scope="model_policy",
        required_child_case_ids=("case:child",),
    )
    aggregate_result = NativeModelCaseResult(
        owner_id="model:alpha",
        source_case_id="case:aggregate",
        outcome="pass",
        observed_status="pass",
        result_artifact_fingerprint=_fp("raw"),
        input_fingerprint=_fp("input"),
        model_fingerprint=_fp("model"),
        code_fingerprint=_fp("code"),
        test_fingerprint=_fp("test"),
        oracle_fingerprint=_fp("oracle"),
        toolchain_fingerprint=_fp("toolchain"),
        environment_fingerprint=_fp("environment"),
        raw_artifact_path="raw.json",
        child_case_ids=("case:child",),
    )
    report = verify_native_model_cases((child, aggregate), (aggregate_result,))
    assert not report.ok
    assert report.missing_case_ids == ("model:alpha:case:child",)
    assert any(item.startswith("aggregate_child_result_missing") for item in report.findings)


def test_model_policy_pass_does_not_become_implementation_pass():
    contract = _good_contract()
    report = verify_native_model_cases((contract,), (_result(contract),))
    assert report.ok
    assert report.model_policy_pass
    assert not report.implementation_boundary_pass


def test_wrong_error_class_is_not_successful_known_bad_case():
    contract = NativeModelCaseContract(
        owner_id="model:alpha",
        source_case_id="case:bad",
        case_kind="bad",
        protected_failure_ids=("failure:expected",),
        callable_ref="model.alpha.bad",
        result_selector="report.bad",
        expected_status="rejected",
        expected_finding_codes=("failure:expected",),
        covered_dimensions=BAD_DIMENSIONS,
        oracle_member_ids=tuple(f"oracle:{item}" for item in BAD_DIMENSIONS),
        evidence_scope="model_policy",
        input_contract_fingerprint=_fp("input"),
        oracle_content_fingerprint=_fp("oracle"),
    )
    result = _result(contract, finding_codes=("failure:other",))
    report = verify_native_model_cases((contract,), (result,))
    assert not report.ok
    assert any(item.startswith("finding_code_missing") for item in report.findings)


def test_contract_rejects_incomplete_dimensions_and_boundary_alias():
    with pytest.raises(NativeCaseProtocolError, match="dimensions must be exact"):
        NativeModelCaseContract(
            owner_id="model:alpha",
            source_case_id="case:good",
            case_kind="good",
            callable_ref="model.alpha.good",
            result_selector="report.good",
            expected_status="pass",
            covered_dimensions=GOOD_DIMENSIONS[:-1],
            oracle_member_ids=("oracle:input",),
            evidence_scope="model_policy",
        )
    with pytest.raises(NativeCaseProtocolError, match="stable"):
        NativeModelCaseContract(
            owner_id="model:alpha",
            source_case_id="case:boundary:alpha:runner-v2",
            case_kind="boundary",
            callable_ref="model.alpha.boundary",
            result_selector="report.boundary",
            expected_status="pass",
            covered_dimensions=("input", "error", "decision", "retry", "timeout", "completion"),
            oracle_member_ids=("oracle:boundary",),
            evidence_scope="model_policy",
        )


def test_current_result_envelope_round_trips_row_schema(tmp_path):
    contract = _good_contract()
    result = _result(contract)
    path = tmp_path / "native-case-results.json"
    path.write_text(
        json.dumps(
            {"schema_version": "flowguard.native_model_case_result.v1", "results": [result.to_dict()]}
        ),
        encoding="utf-8",
    )

    loaded = load_native_model_case_results(path)

    assert loaded == (result,)


def test_oracle_members_and_contract_fingerprints_are_exact():
    contract = _good_contract()
    result = _result(contract)
    wrong_oracle_payload = result.to_dict()
    wrong_oracle_payload.pop("schema_version", None)
    wrong_oracle_payload["oracle_results"] = [
        {
            "dimension": dimension,
            "oracle_member_id": f"oracle:wrong:{dimension}",
            "status": "pass",
            "ok": True,
        }
        for dimension in contract.covered_dimensions
    ]
    wrong_oracle = NativeModelCaseResult(
        **wrong_oracle_payload
    )
    report = verify_native_model_cases((contract,), (wrong_oracle,))
    assert not report.ok
    assert any(item.startswith("oracle_member_mismatch") for item in report.findings)

    changed_input_payload = result.to_dict()
    changed_input_payload.pop("schema_version", None)
    changed_input_payload["input_fingerprint"] = _fp("different-input")
    changed_input = NativeModelCaseResult(**changed_input_payload)
    report = verify_native_model_cases((contract,), (changed_input,))
    assert not report.ok
    assert any(
        item.startswith("input_contract_fingerprint_mismatch")
        for item in report.findings
    )


def test_qualified_aggregate_consumes_cross_owner_child_result():
    child = _good_contract(owner="owner:child", case="case:child")
    aggregate = NativeModelCaseContract(
        owner_id="owner:parent",
        source_case_id="case:aggregate",
        case_kind="aggregate",
        callable_ref="model.parent.aggregate",
        result_selector="report.aggregate",
        expected_status="pass",
        evidence_scope="model_policy",
        required_child_case_ids=(qualified_case_id(child.owner_id, child.source_case_id),),
    )
    aggregate_result = NativeModelCaseResult(
        owner_id=aggregate.owner_id,
        source_case_id=aggregate.source_case_id,
        outcome="pass",
        observed_status="pass",
        result_artifact_fingerprint=_fp("aggregate-raw"),
        input_fingerprint=_fp("input"),
        model_fingerprint=_fp("model"),
        code_fingerprint=_fp("code"),
        test_fingerprint=_fp("test"),
        oracle_fingerprint=_fp("oracle"),
        toolchain_fingerprint=_fp("toolchain"),
        environment_fingerprint=_fp("environment"),
        raw_artifact_path="aggregate.raw.json",
        child_case_ids=aggregate.required_child_case_ids,
    )
    report = verify_native_model_cases(
        (aggregate,),
        (aggregate_result,),
        available_case_keys=(qualified_case_id(child.owner_id, child.source_case_id),),
    )
    assert report.ok, report.findings


def _binding(
    *,
    owner: str = "model:alpha",
    blueprint: str = "behavior-case:surface:good:source",
    native: tuple[str, ...] = ("native:good",),
    mapping_fingerprint: str = "",
) -> NativeCaseBinding:
    return NativeCaseBinding(
        owner_id=owner,
        blueprint_case_id=blueprint,
        blueprint_source_case_id="source",
        native_case_ids=native,
        case_kind="good",
        evidence_scope="model_policy",
        covered_dimensions=GOOD_DIMENSIONS,
        expected_status="pass",
        mapping_fingerprint=mapping_fingerprint,
    )


def test_binding_projection_requires_concrete_aggregate_children():
    from flowguard.native_case_protocol import verify_native_case_bindings

    aggregate = NativeCaseBinding(
        owner_id="model:alpha",
        blueprint_case_id="behavior-case:surface:good:suite",
        blueprint_source_case_id="suite",
        native_case_ids=("native:suite",),
        case_kind="good",
        evidence_scope="model_policy",
        covered_dimensions=GOOD_DIMENSIONS,
        expected_status="pass",
        required_child_case_ids=("model:alpha::native:child",),
    )
    result = _result(
        _good_contract(owner="model:alpha", case="native:suite")
    )
    payload = result.to_dict()
    payload.pop("schema_version", None)
    payload["source_case_id"] = "native:suite"
    payload["child_case_ids"] = ["model:alpha::native:child"]
    aggregate_result = NativeModelCaseResult(**payload)
    report = verify_native_case_bindings((aggregate,), (aggregate_result,))
    assert not report.ok
    assert any("binding_child_result_missing" in item for item in report.findings)


def test_mapping_registry_round_trips_and_rejects_stale_fingerprint(tmp_path):
    source_fp = _fp("manifest")
    skeleton = _binding()
    mapping_fp = compute_native_case_mapping_fingerprint(
        source_manifest_fingerprint=source_fp,
        source_paths=("MAPPING_SCENARIO.md",),
        bindings=(skeleton,),
    )
    row = _binding(mapping_fingerprint=mapping_fp)
    registry = NativeCaseMappingRegistry(
        mapping_fingerprint=mapping_fp,
        source_manifest_fingerprint=source_fp,
        source_paths=("MAPPING_SCENARIO.md",),
        bindings=(row,),
    )
    path = tmp_path / "native-case-mapping.json"
    path.write_text(json.dumps(registry.to_dict()), encoding="utf-8")
    loaded = load_native_case_mapping(path)
    assert loaded.mapping_fingerprint == mapping_fp
    assert loaded.bindings_by_owner["model:alpha"] == (row,)

    stale = registry.to_dict()
    stale["mapping_fingerprint"] = _fp("stale")
    with pytest.raises(NativeCaseMappingError, match="fingerprint"):
        NativeCaseMappingRegistry.from_payload(stale)


def test_mapping_reuses_one_current_native_row_for_two_compatible_obligations():
    first = _binding(blueprint="behavior-case:surface:good:first")
    second = _binding(blueprint="behavior-case:surface:good:repair-preservation")
    mapping_fp = compute_native_case_mapping_fingerprint(
        source_manifest_fingerprint=_fp("manifest"),
        source_paths=("MAPPING_BENCHMARK.md",),
        bindings=(first, second),
    )
    first = _binding(
        blueprint="behavior-case:surface:good:first",
        mapping_fingerprint=mapping_fp,
    )
    second = _binding(
        blueprint="behavior-case:surface:good:repair-preservation",
        mapping_fingerprint=mapping_fp,
    )
    registry = NativeCaseMappingRegistry(
        mapping_fingerprint=mapping_fp,
        source_manifest_fingerprint=_fp("manifest"),
        source_paths=("MAPPING_BENCHMARK.md",),
        bindings=(first, second),
    )
    result = _result(_good_contract(case="native:good"))
    payload = result.to_dict()
    payload.pop("schema_version", None)
    payload["source_case_id"] = "native:good"
    result = NativeModelCaseResult(**payload)

    from flowguard.native_case_protocol import verify_native_case_bindings

    report = verify_native_case_bindings(
        registry.bindings,
        (result,),
        mapping_fingerprint=mapping_fp,
    )
    assert report.ok, report.findings
    assert set(report.projected_case_ids) == {
        "behavior-case:surface:good:first",
        "behavior-case:surface:good:repair-preservation",
    }


def test_mapping_registry_rejects_unknown_fields(tmp_path):
    path = tmp_path / "native-case-mapping.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": NATIVE_CASE_MAPPING_SCHEMA,
                "mapping_fingerprint": _fp("map"),
                "source_manifest_fingerprint": _fp("manifest"),
                "source_paths": [],
                "bindings": [],
                "unexpected": True,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(NativeCaseMappingError, match="unknown fields"):
        load_native_case_mapping(path)


def test_mapping_registry_rejects_stale_current_manifest(tmp_path):
    manifest = tmp_path / ".flowguard" / "models" / "regression-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"schema_version":"flowguard.model_regression_manifest.v4","models":[]}', encoding="utf-8")
    source_fp = source_file_fingerprint(manifest)
    binding = _binding()
    mapping_fp = compute_native_case_mapping_fingerprint(
        source_manifest_fingerprint=source_fp,
        source_paths=(".flowguard/models/regression-manifest.json",),
        bindings=(binding,),
    )
    binding = _binding(mapping_fingerprint=mapping_fp)
    registry = NativeCaseMappingRegistry(
        mapping_fingerprint=mapping_fp,
        source_manifest_fingerprint=source_fp,
        source_paths=(".flowguard/models/regression-manifest.json",),
        bindings=(binding,),
    )
    assert registry.assert_current_manifest(tmp_path) == source_fp

    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(NativeCaseMappingError, match="source manifest fingerprint is stale"):
        registry.assert_current_manifest(tmp_path)
