# Template text for the architecture-reduction model kit.

from __future__ import annotations

ARCHITECTURE_REDUCTION_MODEL_TEMPLATE = '''# FlowGuard model: code shrinks without changing behavior (architecture-reduction kit).
#
# State: the reduction plan reached by adding candidates (one per map lint finding you act on).
# Invariants: review_architecture_reduction accepts every plan reached, and an active candidate that removes,
# merges or collapses code names a symbol that nothing outside its own file imports or references (a static
# scan of the real code).
# Known-bad: removing validate, which the API still calls.
# Conformance (code facts): every anchor and every active candidate names real code, and the code the target
# plan removes is unreferenced. After the change, mark the candidate lifecycle_disposition="completed" (with
# completion_evidence_refs) and drop its anchor: its code must then be gone.
# While planning, IMPLEMENTED_BY names today's code; after the edit, update its locations and delete DESIGN_ONLY.
# Fill in: replace every REPLACE_ME path with yours, write one edit per candidate.
# Its components come from IMPLEMENTED_BY; add COMPONENTS or PARENT only to place it elsewhere.
# Then run: python -m flowguard map models architecture_reduction

from flowguard import (ArchitectureReductionCandidate, ArchitectureReductionPlan, ObservableArchitectureContract,
                       add_reduction_candidate, architecture_reduction_code_facts, architecture_reduction_explorer)

MODEL_ID = "architecture_reduction"
IMPLEMENTED_BY = {"Validate": "REPLACE_ME/orders.py:validate",        # the code the candidates name
                  "ValidateV2": "REPLACE_ME/orders.py:validate_v2"}
# DESIGN_ONLY = "<what is planned>"   # while the change is planned; delete after the edit
TESTED_BY = {"architecture_reduction_review_accepts": ["REPLACE_ME/test_orders.py:test_validate"]}
CONTRACT = ObservableArchitectureContract(
    source_model_id="orders", source_code_boundary_id="orders", public_entrypoints=("REPLACE_ME/orders.py:place_order",),
    observable_outputs=("order accepted or rejected",), validation_boundaries=("test_validate",),
    rationale="placing an order")


def plan():
    return ArchitectureReductionPlan("orders-cleanup", observable_contract=CONTRACT, rationale="map lint duplicate_code")


def candidate(candidate_id, anchor, candidate_type, action, rationale):
    return ArchitectureReductionCandidate(
        candidate_id=candidate_id, candidate_type=candidate_type, code_node_id=anchor, source_model_element="Validate",
        target_action=action, proof_status="safe_by_equivalence", required_next_route="", rationale=rationale,
        evidence_refs=TESTED_BY["architecture_reduction_review_accepts"])


def merge_validate_v2(plan):
    return add_reduction_candidate(plan, candidate("merge-validate-v2", IMPLEMENTED_BY["ValidateV2"], "merge_handlers",
                                                   "merge", "validate_v2 duplicates validate"))


def remove_validate(plan):
    return add_reduction_candidate(plan, candidate("remove-validate", IMPLEMENTED_BY["Validate"],
                                                   "remove_duplicate_validation", "remove", "looks unused"))


EDITS = {"merge_validate_v2": merge_validate_v2, "remove_validate": remove_validate}


def build_explorer():
    return architecture_reduction_explorer(plan, EDITS, explore=["merge_validate_v2"])


def broken_variants():
    return {"remove_validate_still_called": architecture_reduction_explorer(plan, EDITS, explore=["remove_validate"])}


def conformance():
    return architecture_reduction_code_facts(merge_validate_v2(plan()), anchors=IMPLEMENTED_BY, planned="DESIGN_ONLY" in globals())
'''

__all__ = ["ARCHITECTURE_REDUCTION_MODEL_TEMPLATE"]
