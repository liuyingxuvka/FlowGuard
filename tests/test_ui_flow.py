"""UI interaction structure, executable journeys and source-bound control identifiers."""

import unittest
from dataclasses import replace

from flowguard.ui_flow import (
    UIControl, UIDisplayElement, UIInteractionModel, UIStateNode, UITransition,
    review_ui_interaction_model, ui_flow_code_facts, ui_journey_explorer,
)


def state(state_id: str, **kwargs) -> UIStateNode:
    defaults = {
        "visible_controls": ("import", "settings"),
        "enabled_controls": ("settings",),
        "rationale": f"{state_id} is a modeled UI phase",
    }
    defaults.update(kwargs)
    return UIStateNode(state_id, **defaults)


def control(control_id: str, **kwargs) -> UIControl:
    defaults = {
        "label": control_id.title(),
        "rationale": f"{control_id} has a modeled UI purpose",
    }
    defaults.update(kwargs)
    return UIControl(control_id, **defaults)


def transition(event_id: str, control_id: str, source: str, target: str, **kwargs) -> UITransition:
    defaults = {
        "function_block": event_id,
        "output": target,
        "rationale": f"{event_id} moves {source} to {target}",
    }
    defaults.update(kwargs)
    return UITransition(event_id, control_id, source, target, **defaults)


def display(display_id: str, semantic_key: str, **kwargs) -> UIDisplayElement:
    defaults = {
        "label": display_id.title(),
        "rationale": f"{display_id} shows one modeled information concept",
    }
    defaults.update(kwargs)
    return UIDisplayElement(display_id, semantic_key, **defaults)


def ui_model() -> UIInteractionModel:
    return UIInteractionModel(
        "import-run-ui-flow",
        initial_state_id="empty",
        source_product_model_id="import-run-product-flow",
        states=(
            state("empty", enabled_controls=("import", "settings"), disabled_controls=("run", "export")),
            state(
                "file_loaded",
                enabled_controls=("run", "settings"),
                disabled_controls=("export",),
            ),
            state("running", visible_controls=("cancel", "complete"), enabled_controls=("cancel", "complete"), disabled_controls=("run", "export")),
            state(
                "result_ready",
                visible_displays=("summary_card", "result_table"),
                enabled_controls=("export", "run", "settings"),
                terminal=True,
            ),
            state(
                "failed",
                failure=True,
                enabled_controls=("retry", "settings"),
                recovery_controls=("retry",),
            ),
        ),
        controls=(
            control("settings", level="global", persistent=True),
            control("import", level="primary"),
            control("run", level="primary", depends_on_states=("file_loaded", "result_ready")),
            control("cancel", level="contextual", depends_on_states=("running",)),
            control("complete", level="contextual", depends_on_states=("running",)),
            control("retry", level="contextual", depends_on_states=("failed",)),
            control("export", level="secondary", depends_on_states=("result_ready",)),
        ),
        displays=(
            display(
                "summary_card",
                "run_summary",
                display_type="status",
                depends_on_states=("result_ready",),
            ),
            display(
                "result_table",
                "result_rows",
                display_type="table",
                depends_on_states=("result_ready",),
            ),
        ),
        transitions=(
            transition("click_import", "import", "empty", "file_loaded"),
            transition("click_run", "run", "file_loaded", "running"),
            transition("click_cancel", "cancel", "running", "file_loaded"),
            transition("run_success", "complete", "running", "result_ready"),
            transition("run_failure", "complete", "running", "failed"),
            transition("click_retry", "retry", "failed", "running"),
            transition("click_export", "export", "result_ready", "result_ready"),
        ),
        validation_boundaries=("UI flow scenario review",),
        rationale="The UI model separates initial, loaded, running, result, and failure phases.",
    )


class UIInteractionModelTests(unittest.TestCase):
    def test_complete_ui_interaction_model_can_continue(self):
        report = review_ui_interaction_model(ui_model())

        self.assertTrue(report.ok)
        self.assertEqual(0, report.blocker_count())

    def test_missing_initial_state_and_availability_block(self):
        model = UIInteractionModel(
            "broken-ui",
            initial_state_id="missing",
            states=(UIStateNode("empty"),),
            controls=(control("import"),),
            transitions=(transition("click_import", "import", "empty", "loaded"),),
            rationale="broken model",
        )

        report = review_ui_interaction_model(model)
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("initial_state_not_registered", codes)
        self.assertIn("missing_state_availability_matrix", codes)
        self.assertIn("transition_target_state_not_registered", codes)

    def test_failure_without_recovery_and_destructive_primary_block(self):
        model = UIInteractionModel(
            "broken-failure-ui",
            initial_state_id="empty",
            states=(
                state("empty", enabled_controls=("delete",)),
                state("failed", failure=True, visible_controls=("delete",), enabled_controls=("delete",)),
            ),
            controls=(control("delete", level="primary", destructive=True),),
            transitions=(transition("click_delete", "delete", "empty", "failed"),),
            validation_boundaries=("scenario",),
            rationale="broken failure model",
        )

        report = review_ui_interaction_model(model)
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("missing_failure_recovery", codes)
        self.assertIn("destructive_control_too_prominent", codes)

    def test_duplicate_information_and_same_level_control_function_block(self):
        model = UIInteractionModel(
            "duplicate-ui",
            initial_state_id="result_ready",
            states=(
                state(
                    "result_ready",
                    visible_controls=("export", "download"),
                    visible_displays=("summary_chart", "summary_text"),
                    enabled_controls=("export", "download"),
                    terminal=True,
                ),
            ),
            controls=(
                control("export", level="primary", function_key="export_result"),
                control("download", level="primary", function_key="export_result"),
            ),
            displays=(
                display("summary_chart", "run_summary", display_type="chart"),
                display("summary_text", "run_summary", display_type="text"),
            ),
            transitions=(
                transition("click_export", "export", "result_ready", "result_ready", function_block="export_result"),
                transition("click_download", "download", "result_ready", "result_ready", function_block="export_result"),
            ),
            validation_boundaries=("UI redundancy review",),
            rationale="broken redundancy model",
        )

        report = review_ui_interaction_model(model)
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("duplicate_information_same_state", codes)
        self.assertIn("duplicate_control_function_same_state_level", codes)

    def test_justified_duplicate_information_and_control_function_can_continue(self):
        model = UIInteractionModel(
            "justified-duplicate-ui",
            initial_state_id="result_ready",
            states=(
                state(
                    "result_ready",
                    visible_controls=("export", "download"),
                    visible_displays=("summary_chart", "summary_text"),
                    enabled_controls=("export", "download"),
                    terminal=True,
                ),
            ),
            controls=(
                control(
                    "export",
                    level="primary",
                    function_key="export_result",
                    duplicate_group="export-actions",
                    redundancy_rationale="Toolbar and keyboard-oriented export entry points share one export contract.",
                ),
                control(
                    "download",
                    level="primary",
                    function_key="export_result",
                    duplicate_group="export-actions",
                    redundancy_rationale="Download is an alias retained for user vocabulary.",
                ),
            ),
            displays=(
                display(
                    "summary_chart",
                    "run_summary",
                    display_type="chart",
                    duplicate_group="summary-evidence",
                    redundancy_rationale="Chart shows trend shape.",
                ),
                display(
                    "summary_text",
                    "run_summary",
                    display_type="text",
                    duplicate_group="summary-evidence",
                    redundancy_rationale="Text states the same result for accessibility.",
                ),
            ),
            transitions=(
                transition("click_export", "export", "result_ready", "result_ready", function_block="export_result"),
                transition("click_download", "download", "result_ready", "result_ready", function_block="export_result"),
            ),
            validation_boundaries=("UI redundancy review",),
            rationale="intentional redundancy is explicit",
        )

        report = review_ui_interaction_model(model)

        self.assertTrue(report.ok)


def test_ui_dead_button_gives_unmodeled_control_event():
    from flowguard.ui_flow import UIControl, UIInteractionModel, UIStateNode, UITransition, review_ui_interaction_model

    def model(*transitions):
        return UIInteractionModel(
            "export-flow",
            initial_state_id="empty",
            states=(
                UIStateNode("empty", visible_controls=("export",), enabled_controls=("export",)),
                UIStateNode("done", terminal=True),
            ),
            controls=(UIControl("export", label="Export"),),
            transitions=transitions,
        )

    dead = review_ui_interaction_model(model())
    assert "unmodeled_control_event" in {f.code for f in dead.findings}
    wired = review_ui_interaction_model(model(UITransition("click_export", "export", "empty", "done")))
    assert "unmodeled_control_event" not in {f.code for f in wired.findings}


def _details_model(target="open"):
    from flowguard.ui_flow import UIControl, UIInteractionModel, UIStateNode, UITransition

    return UIInteractionModel(
        "details", initial_state_id="closed",
        states=(UIStateNode("closed", visible_controls=("show",), enabled_controls=("show",), hidden_controls=("hide",)),
                UIStateNode("open", visible_controls=("hide",), enabled_controls=("hide",), hidden_controls=("show",))),
        controls=(UIControl("show", label="Show", function_key="show"), UIControl("hide", label="Hide", function_key="hide")),
        transitions=(UITransition("click_show", "show", "closed", target, pure_ui=True, function_block="show", output="shown",
                                  rationale="reveal"),
                     UITransition("click_hide", "hide", "open", "closed", pure_ui=True, function_block="hide",
                                  output="hidden", rationale="return")),
        validation_boundaries=("details",), rationale="toggle")


def test_ui_journey_kit_explores_controls_and_compares_ids_with_the_ui_source(tmp_path):
    from flowguard.ui_flow import ui_flow_code_facts, ui_journey_explorer

    assert ui_journey_explorer(_details_model()).explore().ok
    bad = ui_journey_explorer(_details_model(target="ghost")).explore()
    assert not bad.ok and any("undeclared UI state 'ghost'" in v.message for v in bad.violations)
    (tmp_path / "index.html").write_text('<button id="show">Show</button><button id="hide">Hide</button>\n')
    (tmp_path / "app.js").write_text("function showDetails() {}\nfunction hideDetails() {}\n")
    files, anchors = ["index.html", "app.js"], {"show": "app.js:showDetails", "hide": "app.js:hideDetails"}
    assert ui_flow_code_facts(_details_model(), files, anchors=anchors, root=tmp_path).ok
    (tmp_path / "index.html").write_text('<button id="show">Show</button>\n')
    report = ui_flow_code_facts(_details_model(), files, anchors=anchors, root=tmp_path)
    assert not report.ok and "control hide is in the UI source" in report.format_text()



def _journey_model():
    return UIInteractionModel(
        "recoverable-details", initial_state_id="closed",
        states=(
            UIStateNode("closed", visible_controls=("show", "fail"), enabled_controls=("show", "fail")),
            UIStateNode("open", role="dialog", visible_controls=("hide",), enabled_controls=("hide",)),
            UIStateNode("failed", failure=True, visible_controls=("recover",), enabled_controls=("recover",),
                        recovery_controls=("recover",))),
        controls=tuple(UIControl(name, label=name.title(), function_key=name)
                       for name in ("show", "fail", "hide", "recover")),
        transitions=tuple(UITransition(event, control, source, target, pure_ui=True, function_block=control)
                          for event, control, source, target in (
                              ("show_details", "show", "closed", "open"),
                              ("fail_details", "fail", "closed", "failed"),
                              ("hide_details", "hide", "open", "closed"),
                              ("recover_details", "recover", "failed", "closed"))))


def _with_state(model, state_id, **changes):
    return replace(model, states=tuple(replace(node, **changes) if node.state_id == state_id else node
                                       for node in model.states))


def _assert_fault_and_repair(bad, repaired, code, *, max_steps=2):
    rejected = review_ui_interaction_model(bad)
    assert not rejected.ok and code in {finding.code for finding in rejected.findings}, rejected.format_text()
    journey = ui_journey_explorer(bad, max_steps=max_steps).explore()
    assert not journey.ok, journey.format_text()
    accepted = review_ui_interaction_model(repaired)
    assert accepted.ok, accepted.format_text()
    repaired_journey = ui_journey_explorer(repaired, max_steps=max_steps).explore()
    assert repaired_journey.ok, repaired_journey.format_text()


def test_ui_journey_rejects_an_unknown_state():
    good = _journey_model()
    bad = replace(good, transitions=tuple(replace(row, target_state_id="ghost") if row.control_id == "show" else row
                                         for row in good.transitions))
    _assert_fault_and_repair(bad, good, "transition_target_state_not_registered")


def test_enabled_control_without_transition_is_rejected():
    good = _journey_model()
    bad = replace(good, controls=good.controls + (UIControl("export", label="Export", function_key="export"),))
    bad = _with_state(bad, "closed", visible_controls=("show", "fail", "export"),
                      enabled_controls=("show", "fail", "export"))
    _assert_fault_and_repair(bad, good, "unmodeled_control_event")


def test_dialog_cannot_close_requires_a_real_exit():
    good = _journey_model()
    for role in ("dialog", "modal", "overlay"):
        repaired = _with_state(good, "open", role=role)
        bad = replace(repaired, transitions=tuple(replace(row, target_state_id="open") if row.control_id == "hide" else row
                                                  for row in repaired.transitions))
        _assert_fault_and_repair(bad, repaired, "dialog_cannot_close")
    for changes in (
        dict(enabled_controls=(), disabled_controls=("hide",)),
        dict(visible_controls=(), enabled_controls=(), hidden_controls=("hide",)),
    ):
        _assert_fault_and_repair(_with_state(good, "open", **changes), good, "dialog_cannot_close")
    unknown = replace(good, transitions=tuple(replace(row, target_state_id="ghost") if row.control_id == "hide" else row
                                             for row in good.transitions))
    _assert_fault_and_repair(unknown, good, "dialog_cannot_close")
    cancel = replace(good,
                     controls=tuple(replace(control, control_id="cancel", label="Cancel") if control.control_id == "hide"
                                    else control for control in good.controls),
                     transitions=tuple(replace(row, control_id="cancel", event_id="cancel_details")
                                       if row.control_id == "hide" else row for row in good.transitions))
    cancel = _with_state(cancel, "open", visible_controls=("cancel",), enabled_controls=("cancel",))
    report = review_ui_interaction_model(cancel)
    assert report.ok and "dialog_cannot_close" not in {finding.code for finding in report.findings}, report.format_text()
    explorer = ui_journey_explorer(cancel, max_steps=2)
    assert explorer.explore().ok
    closed = explorer.initial_states[0]
    opened = explorer.workflow.blocks[0].apply("show", closed)[0].new_state
    returned = explorer.workflow.blocks[0].apply("cancel", opened)[0].new_state
    assert opened.state_id == "open" and returned.state_id == "closed"


def test_failure_without_recovery_is_rejected():
    good = _journey_model()
    bad = _with_state(good, "failed", recovery_controls=(), enabled_controls=(), disabled_controls=("recover",))
    bad = replace(bad, transitions=tuple(row for row in bad.transitions if row.source_state_id != "failed"))
    _assert_fault_and_repair(bad, good, "missing_failure_recovery")
    # The old rule intentionally accepts terminal failure and actual outgoing
    # recovery even when recovery_controls does not redundantly list the exit.
    terminal = _with_state(
        replace(bad, controls=tuple(control for control in bad.controls if control.control_id != "recover")),
        "failed", terminal=True, visible_controls=(), disabled_controls=())
    outgoing = _with_state(good, "failed", recovery_controls=())
    for model in (terminal, outgoing):
        report = review_ui_interaction_model(model)
        assert report.ok and "missing_failure_recovery" not in {finding.code for finding in report.findings}, report.format_text()
        assert ui_journey_explorer(model, max_steps=2).explore().ok


def test_declared_state_must_be_reachable():
    # Reachability is the full declared graph, independent of this two-step
    # journey's exploration horizon; the last state takes four steps to reach.
    good = UIInteractionModel(
        "long-path", initial_state_id="s0",
        states=tuple(UIStateNode(f"s{index}", terminal=index == 4,
                                 visible_controls=("step",), enabled_controls=() if index == 4 else ("step",))
                     for index in range(5)),
        controls=(UIControl("step", label="Next", function_key="step"),),
        transitions=tuple(UITransition(f"step_{index}", "step", f"s{index}", f"s{index + 1}",
                                       pure_ui=True, function_block="step") for index in range(4)))
    bad = replace(good, states=good.states + (UIStateNode("orphan", terminal=True),))
    _assert_fault_and_repair(bad, good, "state_unreachable", max_steps=2)


def test_destructive_primary_and_global_controls_are_rejected():
    base = _journey_model()
    repaired = replace(base, controls=tuple(replace(control, destructive=True, level="secondary")
                                            if control.control_id == "fail" else control for control in base.controls))
    for level in ("primary", "global"):
        bad = replace(repaired, controls=tuple(replace(control, level=level) if control.control_id == "fail" else control
                                               for control in repaired.controls))
        _assert_fault_and_repair(bad, repaired, "destructive_control_too_prominent")


def test_disabled_controls_stay_put_and_nondeterministic_targets_remain_real():
    good = _with_state(_journey_model(), "closed", visible_controls=("show", "fail", "hide"),
                       enabled_controls=("show", "fail"), disabled_controls=("hide",))
    review = review_ui_interaction_model(good)
    assert review.ok, review.format_text()
    explorer = ui_journey_explorer(good, max_steps=2)
    assert explorer.explore().ok
    initial = explorer.initial_states[0]
    unavailable = explorer.workflow.blocks[0].apply("hide", initial)
    assert len(unavailable) == 1 and unavailable[0].output == "unavailable" and unavailable[0].new_state == initial
    conflict = _with_state(good, "closed", enabled_controls=("show", "fail", "hide"))
    assert "conflicting_control_availability" in {finding.code for finding in review_ui_interaction_model(conflict).findings}
    branching = replace(good, transitions=good.transitions + (
        UITransition("show_failure", "show", "closed", "failed", pure_ui=True, function_block="show"),))
    report = review_ui_interaction_model(branching)
    assert report.ok, report.format_text()
    branches = ui_journey_explorer(branching, max_steps=2)
    assert branches.explore().ok
    destinations = branches.workflow.blocks[0].apply("show", branches.initial_states[0])
    assert {result.new_state.state_id for result in destinations} == {"open", "failed"}
