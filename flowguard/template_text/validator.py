# Template text for a finite input validator built from the ordinary feature kit.

from __future__ import annotations

VALIDATOR_MODEL_TEMPLATE = '''# FlowGuard node kind validator: a function's finite input boundary; every bad case must be rejected.
# Features are generated bad cases with stable case ids; the kit executes allowed singles and pairs
# against the real function, including the clean input. Declare real code and test anchors below.
# An accepted bad case id names the input the function failed to reject; reproduce that case and fix it.
# Rejection labels do not establish side-effect ordering; test the actual function's effects when needed.
# Fill REPLACE_ME, VALID and BAD, bind real tests, then run: python -m flowguard map models validator
# BAD keys may name any bad case: built-in names keep their default reaction, any other name must be rejected.
# The function rejects with ValueError or TypeError; any other exception is a crash (pass rejects=(...) if needed).

from flowguard.validator import (
    ContractDimension, ContractExhaustionPlan, ContractOracle, contract_exhaustion_features, execute_contract_features,
)
from flowguard.kit import feature_explorer, feature_variants
from flowguard.map.facts import load_anchor

MODEL_ID = "validator"
IMPLEMENTED_BY = {"place": "REPLACE_ME/orders.py:place"}      # the function whose bad inputs must be rejected
TESTED_BY = {"each_defect_rejected": ["REPLACE_ME/test_orders.py:test_place_rejects_bad_input"]}
VALID = {"order_id": "o1", "amount": 5}                      # one valid call; each bad case changes one argument
BAD = {"missing_required_field": None, "empty_value": "", "wrong_type": object(), "too_long": "x" * 81}


def plan():
    return ContractExhaustionPlan(
        "place-contract",
        dimensions=tuple(ContractDimension(name, "input", values=(value,), mutation_types=tuple(BAD))
                         for name, value in VALID.items()),
        oracles=(ContractOracle("oracle:reject-before-side-effect", expected_status="blocked"),))


def mutate(arguments, case_id):                              # case id contract:<argument>:<mutation>
    _, argument, mutation = case_id.split(":")
    return {**arguments, argument: BAD[mutation]}


def features():
    return contract_exhaustion_features(plan(), mutate)


def build_explorer():
    return feature_explorer(features())


def broken_variants():
    return feature_variants(features())


def conformance():
    place = load_anchor(IMPLEMENTED_BY["place"])
    return execute_contract_features(features(), place, VALID, rejected=lambda result: result is None or result is False)
'''

__all__ = ["VALIDATOR_MODEL_TEMPLATE"]
