"""A validator generates every declared bad case and runs each one on the function it guards."""
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
        "tests/test_validator.py:test_named_bad_case_uses_the_reject_oracle",
        "tests/test_validator.py:test_crash_on_bad_input_is_not_a_rejection",
    ],
    "clean_input_accepted": ["tests/test_validator.py:test_named_bad_case_uses_the_reject_oracle"],
    "benign_features_neutral": ["tests/test_validator.py:test_named_bad_case_uses_the_reject_oracle"],
    "first_defect_reported": [
        "tests/test_validator.py:test_executor_reports_the_unhandled_case_id",
        "tests/test_validator.py:test_unbounded_dimension_is_rejected",
        "tests/test_validator.py:test_case_without_oracle_is_rejected",
    ],
}

VALID = {"order_id": "o1", "amount": 5}
BAD = {"missing_required_field": None, "empty_value": "", "wrong_type": "five", "too_long": "x" * 81}
ESCAPED_CASE = "contract:order_id:empty_value"
CRASH_CASE = "contract:amount:wrong_type"


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
        "crash_wrong_type": False,
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


def _named_bad_case(fixture):
    """A business-named bad case outside the built-in vocabulary: it must be generated and rejected."""
    plan = fixture["plan"]
    first = plan.dimensions[0]
    dimensions = (replace(first, mutation_types=first.mutation_types + ("too_long",)),) + plan.dimensions[1:]
    return {**fixture, "plan": replace(plan, dimensions=dimensions)}


def _crash(fixture):
    return {**fixture, "crash_wrong_type": True}


# Generation checks finiteness before case reactions; real execution follows
# generation. Pair combinations must preserve that native error order.
FEATURES = (
    Feature("nonfinite_dimension", True, ("dimension_not_finite",), _nonfinite),
    Feature("missing_case_oracle", True, ("case_missing_oracle",), _missing_oracle),
    Feature("escaped_empty_case", True, ("unhandled:" + ESCAPED_CASE,), _leak_empty),
    # The function raises AttributeError (not ValueError/TypeError) on a bad amount: a crash, not a rejection.
    Feature("crash_on_bad_input", True, ("crashed:" + CRASH_CASE,), _crash),
    Feature("named_bad_case", False, (), _named_bad_case),
)


def build_explorer():
    return feature_explorer(FEATURES, codes="first")


def broken_variants():
    return feature_variants(FEATURES, codes="first")


def _mutate(arguments, case_id):
    _, argument, mutation = case_id.split(":")
    return {**arguments, argument: BAD[mutation]}


def _place(order_id, amount):
    if not isinstance(order_id, str) or not order_id or len(order_id) > 80:
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
        if fixture["crash_wrong_type"] and isinstance(amount, str):
            return amount.as_integer_ratio()      # AttributeError: a crash on this bad input
        return _place(order_id, amount)

    report = execute_contract_features(features, place, VALID, rejected=lambda result: result is None)
    crashes = [v for v in report.violations if v.rule_name == "adapter_exception" and "AttributeError" in v.message]
    if report.declared_only or len(crashes) != report.errors:
        raise RuntimeError("real execution must complete without other adapter errors: " + report.format_text())
    if report.ok:
        return True, ()
    if not report.counterexamples and crashes:
        first = min(crashes, key=lambda v: len(v.features))
        return False, tuple("crashed:" + case_id for case_id in first.features)
    if not report.counterexamples:
        raise RuntimeError("real execution failed without an observed counterexample")
    first = report.counterexamples[0]
    if first.rule_name != "each_defect_rejected" or not first.features:
        raise RuntimeError("unexpected first actual execution failure: " + first.format_text())
    # Keep the actual first finding and its actual case ids, without filtering
    # it through the expected feature vocabulary before choosing the first one.
    return False, tuple("unhandled:" + case_id for case_id in first.features)


def conformance():
    return feature_conformance(FEATURES, clean_fixture, _review, codes="first")
