# Template text for the behavior-commitment model kit.

from __future__ import annotations

BEHAVIOR_COMMITMENT_MODEL_TEMPLATE = '''# FlowGuard model: external promises, their code and tests, and one primary path per promise
# (behavior-commitment kit).
#
# State: the promise ledger (.flowguard/behavior/inventory/ledger.json, the one place promises are kept) and the
# primary-path plan of the path-sensitive promise, reached by adding or retiring commitments and paths.
# Invariants: review_behavior_commitment_ledger (with the project root, so entrypoint and test anchors exist),
# review_primary_path_authority, and a static scan of the real tests: each test file of a commitment imports or
# calls one of its entrypoints, and each entrypoint is imported or called by one of its test files.
# Known-bad: the v1 API returns its own success when submit_order fails; v1 is promised as an entrypoint but no
# test of the commitment calls it.
# Conformance (code facts): entrypoints and tests exist and touch each other, the primary entrypoint exists and
# the v1 facade calls it. After the change, save the target ledger:
# write_behavior_commitment_ledger(LEDGER, add_v1_api(plan()).ledger)
# Fill in: replace every REPLACE_ME path here and in the ledger with yours, model your promises, list this file in
# the owning component's models in .flowguard/map.json, then run: python -m flowguard map models behavior_commitment

from dataclasses import replace
from pathlib import Path

from flowguard import (PPA_AUTHORITY_EXTERNAL_FACADE, PPA_BEHAVIOR_DELEGATE_TO_PRIMARY,
                       PPA_CANDIDATE_COMPATIBILITY_FACADE, PPA_DISPOSITION_PRESERVE_FACADE, PPA_TRIGGER_PRIMARY_FAILURE,
                       BehaviorPlan, BehaviorSourceSurface, FallbackPathCandidate, PrimaryPathAuthorityPlan,
                       PrimaryPathContract, add_commitment, add_path, behavior_commitment_code_facts,
                       behavior_commitment_explorer, load_behavior_commitment_ledger)

MODEL_ID = "behavior_commitment"
IMPLEMENTED_BY = {"SubmitOrder": "REPLACE_ME/orders.py:submit_order",    # the primary path that keeps the promise
                  "SubmitV1": "REPLACE_ME/orders_v1.py:submit"}         # the old API that must delegate to it
TESTED_BY = {"commitment_tests_touch_entrypoints": ["REPLACE_ME/test_orders.py:test_submit_order"]}
LEDGER = Path(__file__).resolve().parents[2] / ".flowguard" / "behavior" / "inventory" / "ledger.json"
COMMITMENT, INTENT, PRIMARY = "commitment:submit-order", "intent:submit-order", "submit_order"


def plan():
    # Before the change: the ledger promises POST /orders; submit_order is its one primary path.
    primary = PrimaryPathContract(PRIMARY, business_intent="submit order", business_intent_id=INTENT,
                                  behavior_commitment_id=COMMITMENT, primary_entrypoint_id=IMPLEMENTED_BY["SubmitOrder"],
                                  owner_model_id=MODEL_ID, owner_code_contract_id=IMPLEMENTED_BY["SubmitOrder"],
                                  expected_terminal="order stored or visible error")
    return BehaviorPlan(load_behavior_commitment_ledger(LEDGER), PrimaryPathAuthorityPlan(PRIMARY, primary_paths=(primary,)))


V1_SURFACE = BehaviorSourceSurface("surface:orders-v1", surface_kind="api", label="POST /v1/orders",
                                   source_ref=IMPLEMENTED_BY["SubmitV1"], freshness_state="current",
                                   delegates_to_primary_path=True, primary_path_id=PRIMARY)
V1_FACADE = FallbackPathCandidate(
    IMPLEMENTED_BY["SubmitV1"], fallback_for_path_id=PRIMARY, business_intent="submit order", business_intent_id=INTENT,
    behavior_commitment_id=COMMITMENT, source_surface_id="surface:orders-v1", delegates_to_path_id=PRIMARY,
    candidate_surface=PPA_CANDIDATE_COMPATIBILITY_FACADE, candidate_behavior=PPA_BEHAVIOR_DELEGATE_TO_PRIMARY,
    classification=PPA_AUTHORITY_EXTERNAL_FACADE, disposition=PPA_DISPOSITION_PRESERVE_FACADE,
    evidence_refs=("code fact: submit calls submit_order",), compatibility_intent="old clients keep POST /v1/orders")


def add_v1_api(plan):
    # The change: the old v1 API maps to the same promise and delegates to the primary path.
    return add_path(add_commitment(plan, COMMITMENT, V1_SURFACE), V1_FACADE)


def v1_falls_back_on_failure(plan):
    return add_path(add_v1_api(plan), replace(V1_FACADE, candidate_trigger=PPA_TRIGGER_PRIMARY_FAILURE,
                                              returns_success_after_primary_failure=True))


def v1_promised_without_its_test(plan):
    plan = add_v1_api(plan)
    submit = next(c for c in plan.ledger.commitments if c.commitment_id == COMMITMENT)
    return add_commitment(plan, replace(submit, entrypoints=submit.entrypoints + (IMPLEMENTED_BY["SubmitV1"],)))


EDITS = {"add_v1_api": add_v1_api, "v1_falls_back_on_failure": v1_falls_back_on_failure,
         "v1_promised_without_its_test": v1_promised_without_its_test}


def build_explorer():
    return behavior_commitment_explorer(plan, EDITS, explore=["add_v1_api"])


def broken_variants():
    return {name: behavior_commitment_explorer(plan, EDITS, explore=[name])
            for name in ("v1_falls_back_on_failure", "v1_promised_without_its_test")}


def conformance():
    return behavior_commitment_code_facts(add_v1_api(plan()), anchors=IMPLEMENTED_BY)
'''

BEHAVIOR_COMMITMENT_LEDGER_TEMPLATE = '''{
  "artifact_type": "flowguard_behavior_commitment_ledger",
  "format_version": "1",
  "ledger": {
    "change_mode": "change_behavior",
    "claim_scope": "routine",
    "commitments": [
      {
        "actor": "API client",
        "actor_kind": "external_system",
        "behavior_plane": "product_runtime",
        "business_intent_id": "intent:submit-order",
        "canonical_relation_ids": [],
        "child_model_ids": [],
        "commitment_id": "commitment:submit-order",
        "commitment_kind": "public_api",
        "entrypoints": [
          "REPLACE_ME/orders.py:submit_order"
        ],
        "excluded_behavior_ids": [],
        "expected_result": "the order is stored or a visible error is returned",
        "expected_terminal": "order stored or visible error",
        "external_differences": [],
        "failure_boundary": "fail closed with the error",
        "in_scope": true,
        "label": "submit an order",
        "lookup_binding": {
          "error_signatures": [],
          "metadata": {},
          "path_patterns": [],
          "task_terms": [],
          "tool_ids": [],
          "workflow_families": []
        },
        "metadata": {},
        "miss_origin_state": "no_miss",
        "model_sync_state": "owner_model_current",
        "owner": "",
        "preconditions": [],
        "primary_owner_model_id": "behavior_commitment",
        "rationale": "the order API promise",
        "relation_obligation_ids": [],
        "relations": [],
        "replacement_state": "active",
        "scoped_out_reason": "",
        "side_effects": [],
        "similarity_obligation_ids": [],
        "similarity_relation_ids": [],
        "source_refs": [],
        "source_surface_ids": [
          "surface:orders-api"
        ],
        "state_writes": [],
        "supporting_model_ids": [],
        "surface_delegation_only": false,
        "tests": [
          "REPLACE_ME/test_orders.py:test_submit_order"
        ],
        "trigger": "POST /orders",
        "validation_boundary": "the tests named in tests",
        "variant_of_business_intent_id": ""
      }
    ],
    "current_revision": "initial",
    "expected_business_intent_ids": [],
    "expected_commitment_ids": [],
    "expected_source_surface_ids": [],
    "independent_behavior_inventory": null,
    "ledger_id": "orders",
    "metadata": {},
    "owner": "orders team",
    "project_boundary": "the order API",
    "rationale": "one promise per order intent, kept by one primary path",
    "require_complete_behavior_inventory": false,
    "require_complete_source_inventory": false,
    "source_inventory_evidence_ids": [],
    "source_inventory_fingerprint": "",
    "source_inventory_revision": "",
    "source_surfaces": [
      {
        "business_intent_ids": [
          "intent:submit-order"
        ],
        "canonical_relation_ids": [],
        "commitment_ids": [
          "commitment:submit-order"
        ],
        "content_fingerprint": "",
        "coverage_disposition": "modeled",
        "declared_semantics_fingerprint": "",
        "delegated_owner_inventory_id": "",
        "delegates_to_primary_path": false,
        "delegation_relation_type": "",
        "discovery_evidence_ids": [],
        "freshness_state": "current",
        "in_scope": true,
        "inventory_revision": "",
        "label": "POST /orders",
        "metadata": {},
        "native_artifact_id": "",
        "native_evidence_ids": [],
        "owner": "",
        "primary_path_id": "submit_order",
        "rationale": "",
        "relation_obligation_ids": [],
        "scoped_out_reason": "",
        "similarity_obligation_ids": [],
        "similarity_relation_ids": [],
        "source_authority_role": "normative",
        "source_classification": "external_normative_contract",
        "source_ref": "REPLACE_ME/orders.py:submit_order",
        "source_system_id": "",
        "surface_id": "surface:orders-api",
        "surface_kind": "api",
        "validation_boundary": ""
      }
    ],
    "subject_lane": "normative_target",
    "validation_boundary": "the tests each commitment names"
  },
  "schema_version": "1.0"
}
'''

__all__ = ["BEHAVIOR_COMMITMENT_LEDGER_TEMPLATE", "BEHAVIOR_COMMITMENT_MODEL_TEMPLATE"]
