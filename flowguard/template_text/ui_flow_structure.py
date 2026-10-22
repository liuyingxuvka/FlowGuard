"""Template text for FlowGuard ui flow structure route."""

from __future__ import annotations

UI_FLOW_STRUCTURE_MODEL_TEMPLATE = '''# FlowGuard model: UI journeys over states and controls (ui-flow kit).
#
# State: the UI state a journey reached; input: one control the user activates.
# Invariants: review_ui_interaction_model accepts the model; every reached state is declared; an enabled
# control always leads somewhere; a non-terminal state always lets the user go on.
# Known-bad: "show" opens a state that does not exist.
# Conformance (code facts): every declared control id is present in UI_FILES and every handler anchor exists.
# Fill in: replace every REPLACE_ME path with your UI files and handlers, model your states, controls and
# transitions.
# Its components come from IMPLEMENTED_BY; add COMPONENTS or PARENT only to place it elsewhere.
# Then run: python -m flowguard map models ui_flow_structure

from dataclasses import replace

from flowguard import (UIControl, UIInteractionModel, UIStateNode, UITransition, ui_flow_code_facts,
                       ui_journey_explorer)

MODEL_ID = "ui_flow_structure"
IMPLEMENTED_BY = {"show": "REPLACE_ME/app.js:showDetails", "hide": "REPLACE_ME/app.js:hideDetails"}   # handlers
UI_FILES = ["REPLACE_ME/index.html", "REPLACE_ME/app.js"]                                              # UI source
TESTED_BY = {"reached_state_is_declared": ["REPLACE_ME/test_ui.py:test_details_open_and_close"]}


def interaction_model() -> UIInteractionModel:
    return UIInteractionModel(
        "details-panel", initial_state_id="closed",
        states=(
            UIStateNode("closed", visible_controls=("show",), enabled_controls=("show",),
                        hidden_controls=("hide",), rationale="Details start hidden."),
            UIStateNode("open", visible_controls=("hide",), enabled_controls=("hide",),
                        hidden_controls=("show",), rationale="The user can return."),
        ),
        controls=(UIControl("show", label="Show details", function_key="show-details"),
                  UIControl("hide", label="Hide details", function_key="hide-details")),
        transitions=(
            UITransition("click_show", "show", "closed", "open", pure_ui=True,
                         function_block="show-details", output="details visible", rationale="Reveal on request."),
            UITransition("click_hide", "hide", "open", "closed", pure_ui=True,
                         function_block="hide-details", output="details hidden", rationale="Return to hidden state."),
        ),
        validation_boundaries=("show and hide details",),
        rationale="A reversible pure UI action with explicit availability.",
    )


def build_explorer():
    return ui_journey_explorer(interaction_model())


def broken_variants():
    model = interaction_model()
    unknown = replace(model, transitions=(replace(model.transitions[0], target_state_id="unknown"), model.transitions[1]))
    return {"show_opens_an_unknown_state": ui_journey_explorer(unknown)}


def conformance():
    return ui_flow_code_facts(interaction_model(), UI_FILES, anchors=IMPLEMENTED_BY)
'''

__all__ = ['UI_FLOW_STRUCTURE_MODEL_TEMPLATE']
