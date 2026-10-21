# Template text for the contract-exhaustion model kit.

from __future__ import annotations

CONTRACT_EXHAUSTION_MODEL_TEMPLATE = '''# FlowGuard model: every bad input of one function's finite contract is rejected (contract-exhaustion kit).
#
# Input universe: the bad cases review_contract_exhaustion generates from the declared boundary, plus the
# valid call.  Invariant: every case gets the verdict of the case table (bad cases rejected, the valid call
# accepted); the review must accept the plan (finite boundary, an oracle for every case).
# Known-bad: designs that accept every case or reject every case.
# Conformance (replay): each case runs against the real function; a case counts as rejected when the call
# raises or returns a rejection.  The report says how many cases were executed against the code.
# Fill in: replace REPLACE_ME with the module and function you protect, declare its arguments in VALID and
# the bad values in BAD, list this file in the owning component's models in .flowguard/map.json, then run:
# python -m flowguard map models contract_exhaustion

from flowguard import (ContractDimension, ContractExhaustionPlan, ContractOracle, case_table_explorer,
                       case_table_variants, contract_exhaustion_cases, execute_contract_cases)
from flowguard.map.facts import load_anchor

MODEL_ID = "contract_exhaustion"
IMPLEMENTED_BY = {"place": "REPLACE_ME/orders.py:place"}      # the function whose bad inputs must be rejected
# TESTED_BY = {"verdict_matches_case": ["tests/test_orders.py:test_place_rejects_bad_input"]}
VALID = {"order_id": "o1", "amount": 5}                      # one valid call; each bad case changes one argument
BAD = {"missing_required_field": None, "empty_value": "", "wrong_type": object()}


def plan():
    return ContractExhaustionPlan(
        "place-contract",
        dimensions=tuple(ContractDimension(name, "input", values=(value,), mutation_types=tuple(BAD))
                         for name, value in VALID.items()),
        oracles=(ContractOracle("oracle:reject-before-side-effect", expected_status="blocked"),),
        claim_scope="routine")


def cases():
    return contract_exhaustion_cases(plan(), accepted=("valid_call",))


def build_explorer():
    return case_table_explorer(cases())


def broken_variants():
    return case_table_variants(cases())


def build_input(case):
    if case.name == "valid_call":
        return dict(VALID)
    _, argument, mutation = case.name.split(":")
    return {**VALID, argument: BAD[mutation]}


def conformance():
    place = load_anchor(IMPLEMENTED_BY["place"])
    return execute_contract_cases(cases(), place, build_input, rejected=lambda result: result is None or result is False)
'''

__all__ = ["CONTRACT_EXHAUSTION_MODEL_TEMPLATE"]
