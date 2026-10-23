"""Template text for the UI journey model kind."""

from __future__ import annotations

UI_JOURNEY_MODEL_TEMPLATE = '''# FlowGuard model kind: ui-journey, states and controls explored as real journeys.
#
# State: the UI state reached; input: a control the user activates.
# Invariants: the structural reviewer accepts the model; reached states are declared;
# enabled controls have a transition; non-terminal states let the user go on.
# Known-bad: an unknown state, an unclosable dialog and a control with no transition.
# Conformance checks source facts: control ids occur in UI_FILES and handler anchors exist.
# It does not render or click the UI; exercise real interactions in the bound UI tests.
# Replace every REPLACE_ME path with your UI source, handlers and tests; adapt the model.
# Components come from IMPLEMENTED_BY; add COMPONENTS or PARENT only for placement.
# Then run: python -m flowguard map models ui_journey

from dataclasses import replace

from flowguard.ui_flow import (UIControl, UIInteractionModel, UIStateNode, UITransition,
                               ui_flow_code_facts, ui_journey_explorer)

MODEL_ID = "ui_journey"
IMPLEMENTED_BY = {"show": "REPLACE_ME/app.js:showDetails", "hide": "REPLACE_ME/app.js:hideDetails"}
UI_FILES = ["REPLACE_ME/index.html", "REPLACE_ME/app.js"]
TESTED_BY = {"reached_state_is_declared": ["REPLACE_ME/test_ui.py:test_details_open_and_close"]}


def interaction_model() -> UIInteractionModel:
    return UIInteractionModel(
        "details-panel", initial_state_id="closed",
        states=(
            UIStateNode("closed", visible_controls=("show",), enabled_controls=("show",),
                        hidden_controls=("hide",)),
            UIStateNode("open", role="dialog", visible_controls=("hide",), enabled_controls=("hide",),
                        hidden_controls=("show",)),
        ),
        controls=(UIControl("show", label="Show details", function_key="show-details"),
                  UIControl("hide", label="Hide details", function_key="hide-details")),
        transitions=(
            UITransition("click_show", "show", "closed", "open", pure_ui=True,
                         function_block="show-details", output="details visible"),
            UITransition("click_hide", "hide", "open", "closed", pure_ui=True,
                         function_block="hide-details", output="details hidden"),
        ),
    )


def build_explorer():
    return ui_journey_explorer(interaction_model())


def broken_variants():
    model = interaction_model()
    unknown = replace(model, transitions=(replace(model.transitions[0], target_state_id="unknown"),
                                         model.transitions[1]))
    cannot_close = replace(model, transitions=(model.transitions[0],
                                              replace(model.transitions[1], target_state_id="open")))
    no_hide_transition = replace(model, transitions=(model.transitions[0],))
    return {
        "show_opens_an_unknown_state": ui_journey_explorer(unknown),
        "details_dialog_cannot_close": ui_journey_explorer(cannot_close),
        "hide_has_no_transition": ui_journey_explorer(no_hide_transition),
    }


def conformance():
    return ui_flow_code_facts(interaction_model(), UI_FILES, anchors=IMPLEMENTED_BY)
'''

__all__ = ["UI_JOURNEY_MODEL_TEMPLATE"]
