"""UI journey rules checked against the real reviewer and real explored journeys.

The clean model opens and closes details and recovers from a reachable failure.
Every singleton and pair of faults is reviewed and explored afresh.  Neither an
unrelated exploration failure nor a discarded journey report supplies evidence.
"""
from dataclasses import replace

from flowguard.kit import Feature, feature_conformance, feature_explorer, feature_variants
from flowguard.ui_flow import (
    UIControl, UIInteractionModel, UIStateNode, UITransition,
    review_ui_interaction_model, ui_journey_explorer,
)

MODEL_ID = "ui_journey_rules"
PARENT = "ui-journey"
IMPLEMENTED_BY = {
    "Review": "flowguard/ui_flow.py:review_ui_interaction_model",
    "Journeys": "flowguard/ui_flow.py:ui_journey_explorer",
}
TESTED_BY = {
    "each_defect_rejected": [
        "tests/test_ui_flow.py:test_ui_journey_rejects_an_unknown_state",
        "tests/test_ui_flow.py:test_enabled_control_without_transition_is_rejected",
        "tests/test_ui_flow.py:test_dialog_cannot_close_requires_a_real_exit",
        "tests/test_ui_flow.py:test_failure_without_recovery_is_rejected",
        "tests/test_ui_flow.py:test_declared_state_must_be_reachable",
    ],
    "first_defect_reported": [
        "tests/test_ui_flow.py:test_ui_journey_rejects_an_unknown_state",
        "tests/test_ui_flow.py:test_enabled_control_without_transition_is_rejected",
        "tests/test_ui_flow.py:test_dialog_cannot_close_requires_a_real_exit",
        "tests/test_ui_flow.py:test_failure_without_recovery_is_rejected",
        "tests/test_ui_flow.py:test_declared_state_must_be_reachable",
    ],
}


def clean_model():
    return UIInteractionModel(
        "details-and-recovery", initial_state_id="closed",
        states=(
            UIStateNode("closed", visible_controls=("show", "fail"), enabled_controls=("show", "fail")),
            UIStateNode("open", role="dialog", visible_controls=("hide",), enabled_controls=("hide",)),
            UIStateNode("failure", failure=True, visible_controls=("recover",),
                        enabled_controls=("recover",), recovery_controls=("recover",)),
        ),
        controls=(
            UIControl("show", label="Show details", function_key="show"),
            UIControl("hide", label="Hide details", function_key="hide"),
            UIControl("fail", label="Try operation", function_key="fail"),
            UIControl("recover", label="Try again", function_key="recover"),
        ),
        transitions=(
            UITransition("show_details", "show", "closed", "open", function_block="show"),
            UITransition("hide_details", "hide", "open", "closed", function_block="hide"),
            UITransition("operation_failed", "fail", "closed", "failure", function_block="fail"),
            UITransition("recover_operation", "recover", "failure", "closed", function_block="recover"),
        ),
    )


def _without_failure_recovery(model):
    # The original rule accepts an outgoing recovery even without a named
    # recovery control.  Remove both, rather than inventing a stronger rule.
    return replace(
        model,
        states=tuple(replace(state, recovery_controls=()) if state.state_id == "failure" else state
                     for state in model.states),
        transitions=tuple(transition for transition in model.transitions if transition.source_state_id != "failure"),
    )


def _without_enabled_transition(model):
    return replace(
        model,
        states=tuple(replace(state, visible_controls=state.visible_controls + ("export",),
                             enabled_controls=state.enabled_controls + ("export",))
                     if state.state_id == "closed" else state for state in model.states),
        controls=model.controls + (UIControl("export", label="Export", function_key="export"),),
    )


def _unknown_target(model):
    return replace(model, transitions=tuple(replace(transition, target_state_id="ghost")
                                           if transition.event_id == "show_details" else transition
                                           for transition in model.transitions))


def _dialog_self_loop(model):
    return replace(model, transitions=tuple(replace(transition, target_state_id="open")
                                           if transition.event_id == "hide_details" else transition
                                           for transition in model.transitions))


def _unreachable_state(model):
    return replace(model, states=model.states + (UIStateNode("orphan", terminal=True),))


# This is the real reviewer's first-finding order, including the two new
# structural checks appended after transition validation.  Pair tests preserve it.
FEATURES = (
    Feature("failure_without_recovery", True, ("missing_failure_recovery",), _without_failure_recovery),
    Feature("enabled_control_without_transition", True, ("unmodeled_control_event",), _without_enabled_transition),
    Feature("unknown_transition_target", True, ("transition_target_state_not_registered",), _unknown_target),
    Feature("dialog_cannot_close", True, ("dialog_cannot_close",), _dialog_self_loop),
    Feature("unreachable_state", True, ("state_unreachable",), _unreachable_state),
)


def build_explorer():
    return feature_explorer(FEATURES, codes="first")


def broken_variants():
    return feature_variants(FEATURES, codes="first")


def _review(model):
    review = review_ui_interaction_model(model)
    journeys = ui_journey_explorer(model, max_steps=2).explore()
    if not journeys.exploration_complete or journeys.exception_branches:
        raise RuntimeError("UI journey exploration must complete without exceptions")
    if review.ok != journeys.ok:
        raise RuntimeError("the actual UI review and actual journey verdict disagree")
    if not review.ok and not any(violation.invariant_name == "ui_review_accepts" for violation in journeys.violations):
        raise RuntimeError("the journey did not enforce the real interaction review")
    codes = tuple(finding.code for finding in review.findings)
    return review.ok and journeys.ok, codes[:1]


def conformance():
    return feature_conformance(FEATURES, clean_model, _review, codes="first")
