"""Finite validator generation and execution against real functions."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from flowguard.templates import validator_template_files, write_template_files
from flowguard.validator import (
    CONTRACT_MUTATION_CONFLICTING_IDENTITY,
    CONTRACT_MUTATION_OLD_SCHEMA_VERSION,
    CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
    ContractAxis,
    ContractDimension,
    ContractExhaustionPlan,
    ContractInteractionGroup,
    ContractMutationCase,
    ContractOracle,
    contract_exhaustion_features,
    execute_contract_features,
    generate_contract_cases,
)


def _place(order_id, amount):
    if not isinstance(order_id, str) or not order_id:
        raise ValueError("order_id")
    if not isinstance(amount, int) or amount <= 0:
        return None
    return "placed"


_PLAN = ContractExhaustionPlan(
    "place-contract",
    dimensions=(ContractDimension("order_id", "input", values=("o1",), mutation_types=("missing_required_field", "empty_value")),
                ContractDimension("amount", "input", values=(5,), mutation_types=("wrong_type",))),
    oracles=(ContractOracle("oracle:reject", expected_status="blocked"),))
_BAD = {"missing_required_field": None, "empty_value": "", "wrong_type": "five"}


def _mutate(arguments, case_id):
    _, argument, mutation = case_id.split(":")
    return {**arguments, argument: _BAD[mutation]}


def _clean_execution():
    features = contract_exhaustion_features(_PLAN, _mutate)
    report = execute_contract_features(features, _place, {"order_id": "o1", "amount": 5},
                                       rejected=lambda result: result is None)
    assert report.ok and report.executed == 7, report.format_text()
    return features


def test_required_field_dimension_generates_stable_cases():
    plan = ContractExhaustionPlan("field-contract", dimensions=(ContractDimension("packet.kind", "field"),))
    cases = generate_contract_cases(plan)
    assert tuple(case.case_id for case in cases) == (
        "contract:packet.kind:missing_required_field", "contract:packet.kind:empty_value",
        "contract:packet.kind:wrong_type")
    assert tuple(case.case_id for case in generate_contract_cases(plan)) == tuple(case.case_id for case in cases)
    assert all(case.expected_status == CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT for case in cases)


def test_omitted_family_member_keeps_the_missing_member_case():
    plan = ContractExhaustionPlan("owner-inventory", model_id="router",
                                 expected_family_member_ids=("ui", "cli"),
                                 materialized_family_member_ids=("ui",))
    cases = generate_contract_cases(plan)
    assert tuple(case.case_id for case in cases) == ("contract:omitted_family_member:cli",)
    assert cases[0].mutation_type == "omitted_family_member" and cases[0].member_id == "cli"


def _cartesian_plan(*, limit=100000):
    return ContractExhaustionPlan(
        "model-cartesian", model_id="packet-router",
        axes=(ContractAxis("packet_status", values=("missing", "wrong_type")),
              ContractAxis("evidence_path", values=("missing_file", "old_packet_dir"))),
        interaction_groups=(ContractInteractionGroup("packet-evidence-contract",
                                                     axis_ids=("packet_status", "evidence_path")),),
        cartesian_case_limit=limit)


def test_model_local_cartesian_group_generates_the_complete_product():
    cases = generate_contract_cases(_cartesian_plan())
    assert len(cases) == 4
    assert tuple(case.case_id for case in cases) == tuple(
        f"cartesian:packet-router:packet-evidence-contract:{index}" for index in range(1, 5))
    assert all(case.mutation_type == "cartesian_combination" and case.model_id == "packet-router" for case in cases)
    assert [case.input_delta["axis_values"] for case in cases] == [
        {"packet_status": "missing", "evidence_path": "missing_file"},
        {"packet_status": "missing", "evidence_path": "old_packet_dir"},
        {"packet_status": "wrong_type", "evidence_path": "missing_file"},
        {"packet_status": "wrong_type", "evidence_path": "old_packet_dir"}]
    assert all(set(case.input_delta["axis_cases"]) == {"packet_status", "evidence_path"} for case in cases)
    assert all(case.input_delta["dimension_ids"] == [] for case in cases)


def test_model_local_cartesian_group_rejects_an_exceeded_limit():
    plan = ContractExhaustionPlan(
        "model-cartesian-limit", model_id="packet-router",
        axes=(ContractAxis("status", values=("a", "b", "c")),
              ContractAxis("evidence", values=("x", "y"))),
        interaction_groups=(ContractInteractionGroup("too-wide", axis_ids=("status", "evidence")),),
        cartesian_case_limit=5)
    with pytest.raises(ValueError, match="too-wide"):
        generate_contract_cases(plan)


def test_model_local_cartesian_group_rejects_a_foreign_axis():
    plan = ContractExhaustionPlan(
        "foreign-axis", model_id="parent",
        axes=(ContractAxis("parent_state", model_id="parent", values=("cold", "hot")),
              ContractAxis("child_state", model_id="child", values=("cold", "hot"))),
        interaction_groups=(ContractInteractionGroup("parent-local", model_id="parent",
                                                     axis_ids=("parent_state", "child_state")),))
    with pytest.raises(ValueError, match="child_state"):
        generate_contract_cases(plan)


def test_unknown_oracle_is_rejected():
    plan = ContractExhaustionPlan(
        "unknown-oracle", seed_cases=(ContractMutationCase(
            "packet-missing-kind", dimension_id="packet.kind", mutation_type="missing_required_field",
            oracle_id="not-declared"),),
        oracles=(ContractOracle("declared", CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT),))
    with pytest.raises(ValueError, match="packet-missing-kind") as caught:
        contract_exhaustion_features(plan, _mutate)
    assert "not-declared" in str(caught.value)


def test_case_without_oracle_is_rejected():
    _clean_execution()
    plan = ContractExhaustionPlan("missing-oracle", seed_cases=(ContractMutationCase(
        "custom-case", dimension_id="custom.boundary", mutation_type="project_specific_corruption"),))
    with pytest.raises(ValueError, match="custom-case"):
        contract_exhaustion_features(plan, _mutate)


def test_unbounded_dimension_is_rejected():
    _clean_execution()
    plan = ContractExhaustionPlan("unbounded", dimensions=(ContractDimension("free_text", "input", finite=False),))
    with pytest.raises(ValueError, match="free_text"):
        contract_exhaustion_features(plan, _mutate)


def test_empty_plan_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        contract_exhaustion_features(ContractExhaustionPlan("empty"), _mutate)


def test_executor_reports_the_unhandled_case_id():
    features = contract_exhaustion_features(_PLAN, _mutate)
    assert [(feature.name, feature.rejects) for feature in features] == [
        ("contract:order_id:missing_required_field", True), ("contract:order_id:empty_value", True),
        ("contract:amount:wrong_type", True)]
    valid = {"order_id": "o1", "amount": 5}
    report = execute_contract_features(features, _place, valid, rejected=lambda result: result is None)
    assert report.ok and report.executed == 7, report.format_text()      # valid call, 3 bad cases, 3 pairs
    lax = execute_contract_features(features, lambda order_id, amount: "placed", valid)
    assert not lax.ok and lax.format_text().startswith(
        "executed against code: 7 of 7 feature combinations; declared only: 0; errors: 0; counterexamples: 6")
    assert lax.violations[0].format_text() == (
        "- each_defect_rejected: contract:order_id:missing_required_field: expected rejected, observed accepted")
    amount_only = execute_contract_features(features, lambda order_id, amount: None if amount != 5 else "placed",
                                            valid, rejected=lambda result: result is None)
    assert [v.features for v in amount_only.violations] == [      # only the order_id defects get through
        ("contract:order_id:missing_required_field",), ("contract:order_id:empty_value",),
        ("contract:order_id:missing_required_field", "contract:order_id:empty_value")]


def _check_new_mutation_rejects_before_fixture_effect(mutation, bad_value):
    for dimension_type in ("input", "payload"):
        effects = []
        valid_value = {"schema_version": 1, "id": "o1", "canonical_id": "o1"}
        plan = ContractExhaustionPlan(f"{dimension_type}-boundary", dimensions=(
            ContractDimension("value", dimension_type, values=(valid_value,)),))
        cases = generate_contract_cases(plan)
        case = next(case for case in cases if case.mutation_type == mutation)
        assert case.case_id == f"contract:value:{mutation}"
        assert case.expected_status == CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT

        def mutate(arguments, case_id):
            assert case_id == case.case_id
            return {**arguments, "value": bad_value}

        def save(value):
            if value["schema_version"] != 1:
                raise ValueError("schema_version")
            if value["id"] != value["canonical_id"]:
                raise ValueError("identity")
            effects.append(value["id"])
            return "saved"

        features = tuple(feature for feature in contract_exhaustion_features(plan, mutate)
                         if feature.name == case.case_id)
        assert len(features) == 1
        report = execute_contract_features(features, save, {"value": valid_value})
        assert report.ok and report.executed == 2, report.format_text()
        assert effects == ["o1"]


def test_old_schema_version_is_generated_and_rejected_before_fixture_effect():
    _check_new_mutation_rejects_before_fixture_effect(
        CONTRACT_MUTATION_OLD_SCHEMA_VERSION, {"schema_version": 0, "id": "o1", "canonical_id": "o1"})


def test_conflicting_identity_is_generated_and_rejected_before_fixture_effect():
    _check_new_mutation_rejects_before_fixture_effect(
        CONTRACT_MUTATION_CONFLICTING_IDENTITY, {"schema_version": 1, "id": "o1", "canonical_id": "other"})


def test_validator_template_reports_the_unhandled_case_id(tmp_path):
    files = validator_template_files()
    shop = tmp_path / "shop"
    shop.mkdir()
    (shop / "orders.py").write_text(
        "def place(order_id, amount):\n"
        "    if not isinstance(order_id, str) or not isinstance(amount, int):\n"
        "        raise ValueError('bad input')\n"
        "    return 'placed'\n", encoding="utf-8")
    (shop / "test_orders.py").write_text(
        "import pytest\nfrom shop.orders import place\n\n"
        "def test_place_rejects_bad_input():\n"
        "    assert place('o1', 5) == 'placed'\n"
        "    with pytest.raises(ValueError):\n        place(None, 5)\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    write_template_files(tmp_path, files)
    for file in files:
        path = tmp_path / file.path
        path.write_text(path.read_text(encoding="utf-8").replace("REPLACE_ME", "shop"), encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1]) + os.pathsep + env.get("PYTHONPATH", "")

    def run_map(*args):
        return subprocess.run([sys.executable, "-m", "flowguard", "map", *args], cwd=tmp_path,
                              env=env, text=True, capture_output=True, check=False)

    scanned = run_map("scan")
    assert scanned.returncode == 0, scanned.stdout + scanned.stderr
    path = tmp_path / ".flowguard/map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["components"][0]["models"] = [files[0].path]
    path.write_text(json.dumps(data), encoding="utf-8")
    result = run_map("models", "validator")
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "FAIL  validator" in output
    assert "contract:order_id:empty_value" in output
    assert "expected rejected, observed accepted" in output


def _title_cases(limit):
    plan = ContractExhaustionPlan("title-contract", dimensions=(
        ContractDimension("title", "input", values=("ok",), mutation_types=("too_long", "blank")),))
    bad = {"too_long": "x" * 81, "blank": "   "}

    def mutate(arguments, case_id):
        return {**arguments, "title": bad[case_id.split(":")[2]]}

    def save(title):
        if not title.strip() or len(title) > limit:
            raise ValueError("title")
        return "saved"
    return plan, mutate, save


def test_named_bad_case_uses_the_reject_oracle():
    plan, mutate, save = _title_cases(80)
    cases = generate_contract_cases(plan)
    assert [(case.case_id, case.expected_status) for case in cases] == [
        ("contract:title:too_long", CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT),
        ("contract:title:blank", CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT)]
    features = contract_exhaustion_features(plan, mutate)
    assert execute_contract_features(features, save, {"title": "ok"}).ok
    plan, mutate, lax = _title_cases(800)
    report = execute_contract_features(contract_exhaustion_features(plan, mutate), lax, {"title": "ok"})
    assert not report.ok and "contract:title:too_long: expected rejected, observed accepted" in report.format_text()


def test_crash_on_bad_input_is_not_a_rejection():
    plan, mutate, _ = _title_cases(80)

    def save(title):
        if not title.strip():
            raise AttributeError("blank title has no words")      # a crash, not a rejection
        if len(title) > 80:
            raise ValueError("title")
        return "saved"
    features = contract_exhaustion_features(plan, mutate)
    report = execute_contract_features(features, save, {"title": "ok"})
    text = report.format_text()
    assert not report.ok and "adapter_exception" in text and "AttributeError" in text, text
    assert "- adapter_exception: contract:title:blank: expected rejected, observed error (AttributeError: " in text
    assert execute_contract_features(features, save, {"title": "ok"}, rejects=(ValueError, AttributeError)).ok
