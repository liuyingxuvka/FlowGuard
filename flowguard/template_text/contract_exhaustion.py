# Template text for the contract-exhaustion model kit.

from __future__ import annotations

CONTRACT_EXHAUSTION_MODEL_TEMPLATE = '''# FlowGuard model: every bad input of one function's finite contract is rejected (contract-exhaustion kit).
#
# Features: each bad case review_contract_exhaustion generates from the declared boundary is a rejecting
# feature that changes the valid call (VALID) to carry one bad value; the review must accept the plan
# (finite boundary, an oracle for every case).  The kit explores every bad case alone and every pair.
# Invariants (flowguard.kit): the valid call is accepted; any bad value is rejected.
# Known-bad: generated variants (one ignores a bad case) must fail.
# Conformance (replay): every combination runs against the real function; it counts as rejected when the
# call raises or returns a rejection.  The report says how many combinations were executed against the code.
# Fill in: replace REPLACE_ME with the module and function you protect, declare its arguments in VALID and
# the bad values in BAD.
# Its components come from IMPLEMENTED_BY; add COMPONENTS or PARENT only to place it elsewhere.
# Then run: python -m flowguard map models contract_exhaustion

from flowguard import (ContractDimension, ContractExhaustionPlan, ContractOracle, contract_exhaustion_features,
                       execute_contract_features, feature_explorer, feature_variants)
from flowguard.map.facts import load_anchor

MODEL_ID = "contract_exhaustion"
IMPLEMENTED_BY = {"place": "REPLACE_ME/orders.py:place"}      # the function whose bad inputs must be rejected
TESTED_BY = {"each_defect_rejected": ["REPLACE_ME/test_orders.py:test_place_rejects_bad_input"]}
VALID = {"order_id": "o1", "amount": 5}                      # one valid call; each bad case changes one argument
BAD = {"missing_required_field": None, "empty_value": "", "wrong_type": object()}


def plan():
    return ContractExhaustionPlan(
        "place-contract",
        dimensions=tuple(ContractDimension(name, "input", values=(value,), mutation_types=tuple(BAD))
                         for name, value in VALID.items()),
        oracles=(ContractOracle("oracle:reject-before-side-effect", expected_status="blocked"),),
        claim_scope="routine")


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

__all__ = ["CONTRACT_EXHAUSTION_MODEL_TEMPLATE"]
