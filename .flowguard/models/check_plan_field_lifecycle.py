"""Executable model: the fields of a FlowGuard check plan keep a closed lifecycle.

FlowGuardCheckPlan carried an ``assumption_card`` field into reports, exports and summaries until
FG-56 removed it.  This is the field-lifecycle kit applied to FlowGuard itself:
  * state: the field-lifecycle plan of FlowGuardCheckPlan, reached by named edits;
  * invariant: review_field_lifecycle accepts every plan the edits reach;
  * known-bad: dropping the field without a closing disposition;
  * conformance (code facts): ``assumption_card`` has no reference left in the six modules that
    carried it, and the kept ``invariants`` field is still declared on the plan.
"""

from flowguard import (FIELD_DISPOSITION_DELETED, FIELD_IMPACT_STATE, FIELD_LIFECYCLE_DEPRECATED, FIELD_ROLE_METADATA,
                       FIELD_ROLE_STATE, FieldLifecyclePlan, FieldLifecycleRow, FieldProjection,
                       field_lifecycle_code_facts, field_lifecycle_explorer, replace_field_row)

MODEL_ID = "check_plan_field_lifecycle"
COMPONENTS = ["engine-runner", "field-lifecycle"]
IMPLEMENTED_BY = {"CheckPlan": "flowguard/plan.py:FlowGuardCheckPlan",
                  "Review": "flowguard/field_lifecycle.py:review_field_lifecycle"}
TESTED_BY = {"field_lifecycle_review_accepts": [
    "tests/test_field_lifecycle.py:test_old_field_unknown_disposition_blocks",
    "tests/test_field_lifecycle.py:test_field_lifecycle_code_facts_compare_the_plan_with_the_code"]}
OWNED_FILES = ["flowguard/explorer.py", "flowguard/report.py", "flowguard/plan.py", "flowguard/runner.py",
               "flowguard/export.py", "flowguard/summary_report.py"]


def plan() -> FieldLifecyclePlan:
    return FieldLifecyclePlan("check-plan-fields", discovered_field_ids=("field:invariants", "field:assumption_card"), fields=(
        FieldLifecycleRow("field:invariants", role=FIELD_ROLE_STATE, behavior_impacts=(FIELD_IMPACT_STATE,),
                          locations=("flowguard/plan.py:invariants",), reader_ids=("flowguard.runner",),
                          writer_ids=("flowguard.plan",),
                          projection=FieldProjection("projection:invariants", "field:invariants",
                                                     model_obligation_id="obligation:invariants_are_checked",
                                                     code_contract_id="contract:run_model_first_checks")),
        FieldLifecycleRow("field:assumption_card", role=FIELD_ROLE_METADATA, locations=("flowguard/plan.py:assumption_card",),
                          scoped_out_reason="an optional note attached to reports; it never changed a verdict"),
    ))


EDITS = {
    "remove_assumption_card": lambda p: replace_field_row(
        p, "field:assumption_card", lifecycle=FIELD_LIFECYCLE_DEPRECATED, disposition=FIELD_DISPOSITION_DELETED,
        disposition_evidence_refs=("FG-56",)),
    "drop_assumption_card_without_disposition": lambda p: replace_field_row(
        p, "field:assumption_card", lifecycle=FIELD_LIFECYCLE_DEPRECATED),
}


def build_explorer():
    return field_lifecycle_explorer(plan, EDITS, explore=["remove_assumption_card"])


def broken_variants():
    return {"drop_without_disposition":
            field_lifecycle_explorer(plan, EDITS, explore=["drop_assumption_card_without_disposition"])}


def conformance():
    return field_lifecycle_code_facts(EDITS["remove_assumption_card"](plan()), OWNED_FILES, anchors=IMPLEMENTED_BY)
