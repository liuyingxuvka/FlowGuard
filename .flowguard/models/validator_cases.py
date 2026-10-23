"""Real finite generation and real execution, including configuration failures."""
from dataclasses import replace

from flowguard.kit import Feature, feature_conformance, feature_explorer, feature_variants
from flowguard.validator import (
    ContractDimension, ContractExhaustionPlan, ContractMutationCase, ContractOracle,
    contract_exhaustion_features, execute_contract_features,
)

MODEL_ID = "validator_cases"
PARENT = "validator"
IMPLEMENTED_BY = {
    "Features": "flowguard/validator.py:contract_exhaustion_features",
    "Execute": "flowguard/validator.py:execute_contract_features",
}
TESTED_BY = {
    "each_defect_rejected": [
        "tests/test_validator.py:test_executor_reports_the_unhandled_case_id",
        "tests/test_validator.py:test_unbounded_dimension_is_rejected",
        "tests/test_validator.py:test_case_without_oracle_is_rejected",
    ],
    "first_defect_reported": [
        "tests/test_validator.py:test_executor_reports_the_unhandled_case_id",
        "tests/test_validator.py:test_unbounded_dimension_is_rejected",
        "tests/test_validator.py:test_case_without_oracle_is_rejected",
    ],
}

VALID = {"order_id": "o1", "amount": 5}
BAD = {"missing_required_field": None, "empty_value": "", "wrong_type": "five"}
ESCAPED_CASE = "contract:order_id:empty_value"


def clean_fixture():
    return {
        "plan": ContractExhaustionPlan(
            "place-contract",
            dimensions=(
                ContractDimension("order_id", "input", values=("o1",),
                                  mutation_types=("missing_required_field", "empty_value")),
                ContractDimension("amount", "input", values=(5,), mutation_types=("wrong_type",)),
            ),
            oracles=(ContractOracle("oracle:reject", expected_status="blocked"),),
        ),
        "leak_empty": False,
    }


def _nonfinite(fixture):
    plan = fixture["plan"]
    dimensions = (replace(plan.dimensions[0], finite=False),) + plan.dimensions[1:]
    return {**fixture, "plan": replace(plan, dimensions=dimensions)}


def _missing_oracle(fixture):
    plan = fixture["plan"]
    case = ContractMutationCase("custom-case", dimension_id="custom.boundary",
                                mutation_type="project_specific_corruption")
    return {**fixture, "plan": replace(plan, seed_cases=plan.seed_cases + (case,))}


def _leak_empty(fixture):
    return {**fixture, "leak_empty": True}


# Generation checks finiteness before case reactions; real execution follows
# generation. Pair combinations must preserve that native error order.
FEATURES = (
    Feature("nonfinite_dimension", True, ("dimension_not_finite",), _nonfinite),
    Feature("missing_case_oracle", True, ("case_missing_oracle",), _missing_oracle),
    Feature("escaped_empty_case", True, ("unhandled:" + ESCAPED_CASE,), _leak_empty),
)


def build_explorer():
    return feature_explorer(FEATURES, codes="first")


def broken_variants():
    return feature_variants(FEATURES, codes="first")


def _mutate(arguments, case_id):
    _, argument, mutation = case_id.split(":")
    return {**arguments, argument: BAD[mutation]}


def _place(order_id, amount):
    if not isinstance(order_id, str) or not order_id:
        raise ValueError("order_id")
    if not isinstance(amount, int) or amount <= 0:
        return None
    return "placed"


def _review(fixture):
    try:
        features = contract_exhaustion_features(fixture["plan"], _mutate)
    except ValueError as error:
        # Only these exact native configuration boundaries are expected faults.
        # Any other error remains visible as an adapter failure.
        if str(error) == "dimension 'order_id' is not finite":
            return False, ("dimension_not_finite",)
        if str(error) == "case 'custom-case' has no oracle or expected reaction":
            return False, ("case_missing_oracle",)
        raise

    def place(order_id, amount):
        if fixture["leak_empty"] and order_id == "" and isinstance(amount, int) and amount > 0:
            return "placed"
        return _place(order_id, amount)

    report = execute_contract_features(features, place, VALID, rejected=lambda result: result is None)
    if report.errors or report.declared_only or report.executed != report.combinations:
        raise RuntimeError("real execution must complete without adapter errors: " + report.format_text())
    if report.ok:
        return True, ()
    if not report.violations:
        raise RuntimeError("real execution failed without an observed counterexample")
    first = report.violations[0]
    if first.rule_name != "each_defect_rejected" or not first.features:
        raise RuntimeError("unexpected first actual execution failure: " + first.format_text())
    # Keep the actual first finding and its actual case ids, without filtering
    # it through the expected feature vocabulary before choosing the first one.
    return False, tuple("unhandled:" + case_id for case_id in first.features)


def conformance():
    return feature_conformance(FEATURES, clean_fixture, _review, codes="first")
