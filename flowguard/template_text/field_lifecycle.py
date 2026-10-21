# Template text for the field-lifecycle model kit.

from __future__ import annotations

FIELD_LIFECYCLE_MODEL_TEMPLATE = '''# FlowGuard model: the lifecycle of the fields a change touches (field-lifecycle kit).
#
# State: the field-lifecycle plan reached by named edits (introduce a field, retire an old one).
# Invariant: review_field_lifecycle accepts every plan the edits can reach.
# Known-bad: the old field is dropped without a closing disposition.
# Conformance (code facts): the target plan matches the real code - a deleted field has no reference
# left in OWNED_FILES, its replacement is present, and every declared location still holds its field.
# Fill in: replace every REPLACE_ME path and the example fields with yours, list this file in the
# owning component's models in .flowguard/map.json, then run: python -m flowguard map models field_lifecycle

from flowguard import (FIELD_DISPOSITION_DELETED, FIELD_IMPACT_ROUTING, FIELD_LIFECYCLE_REPLACED, FIELD_ROLE_ROUTING,
                       FieldLifecyclePlan, FieldLifecycleRow, FieldProjection, add_field_row,
                       field_lifecycle_code_facts, field_lifecycle_explorer, replace_field_row)

MODEL_ID = "field_lifecycle"
IMPLEMENTED_BY = {"Order": "REPLACE_ME/orders.py:Order"}     # the code that reads and writes these fields
OWNED_FILES = ["REPLACE_ME/orders.py"]                      # files searched for the field names
TESTED_BY = {"field_lifecycle_review_accepts": ["REPLACE_ME/test_orders.py:test_old_mode_is_rejected"]}


def _routing(field_id, name, **extra):
    return FieldLifecycleRow(field_id, field_name=name, role=FIELD_ROLE_ROUTING, behavior_impacts=(FIELD_IMPACT_ROUTING,),
                             projection=FieldProjection(f"projection:{name}", field_id,
                                                        model_obligation_id=f"obligation:{name}_routes_order",
                                                        code_contract_id=f"contract:{name}_router"), **extra)


def _has(plan, field_id):
    return any(row.field_id == field_id for row in plan.fields)


def plan():
    # Before the change: orders are routed by old_mode.
    return FieldLifecyclePlan("order-fields", discovered_field_ids=("field:old_mode",),
                              fields=(_routing("field:old_mode", "old_mode", locations=("REPLACE_ME/orders.py:old_mode",)),))


def introduce_mode(plan):
    if _has(plan, "field:mode"):
        return plan
    return add_field_row(plan, _routing("field:mode", "mode", locations=("REPLACE_ME/orders.py:mode",)))


def retire_old_mode(plan):
    # The old field is retired only once its replacement exists, and always with a closing disposition.
    if not _has(plan, "field:mode"):
        return plan
    return replace_field_row(plan, "field:old_mode", lifecycle=FIELD_LIFECYCLE_REPLACED, replacement_field_id="field:mode",
                             disposition=FIELD_DISPOSITION_DELETED, disposition_evidence_refs=("test:old_mode_rejected",))


def drop_old_mode_without_disposition(plan):
    return replace_field_row(plan, "field:old_mode", lifecycle=FIELD_LIFECYCLE_REPLACED, replacement_field_id="field:mode")


EDITS = {"introduce_mode": introduce_mode, "retire_old_mode": retire_old_mode,
         "drop_old_mode_without_disposition": drop_old_mode_without_disposition}


def build_explorer():
    return field_lifecycle_explorer(plan, EDITS, explore=["introduce_mode", "retire_old_mode"])


def broken_variants():
    return {"drop_old_mode_without_disposition":
            field_lifecycle_explorer(plan, EDITS, explore=["drop_old_mode_without_disposition"])}


def conformance():
    target = retire_old_mode(introduce_mode(plan()))
    return field_lifecycle_code_facts(target, OWNED_FILES, anchors=IMPLEMENTED_BY)
'''

__all__ = ["FIELD_LIFECYCLE_MODEL_TEMPLATE"]
