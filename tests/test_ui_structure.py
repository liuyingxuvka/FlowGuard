import unittest

from flowguard import (
    UIControl,
    UIDisplayElement,
    UIInteractionModel,
    UIRegionRecommendation,
    UIStateNode,
    UIStructureDerivation,
    UITransition,
    review_ui_interaction_model,
    review_ui_structure_derivation,
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
            state("running", enabled_controls=("cancel",), disabled_controls=("run", "export")),
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
            transition("run_success", "run", "running", "result_ready"),
            transition("run_failure", "run", "running", "failed"),
            transition("click_retry", "retry", "failed", "running"),
            transition("click_export", "export", "result_ready", "result_ready"),
        ),
        validation_boundaries=("UI flow scenario review",),
        rationale="The UI model separates initial, loaded, running, result, and failure phases.",
    )


def region(region_id: str, **kwargs) -> UIRegionRecommendation:
    defaults = {
        "placement": "main",
        "rationale": f"{region_id} owns a model-derived UI level",
        "validation_boundaries": ("component state test",),
    }
    defaults.update(kwargs)
    return UIRegionRecommendation(region_id, **defaults)


def derivation() -> UIStructureDerivation:
    return UIStructureDerivation(
        "import-run-ui-structure",
        source_interaction_model_id="import-run-ui-flow",
        parent_surface_id="import-run-workbench",
        interaction_model_reviewed=True,
        target_regions=(
            region(
                "top-toolbar",
                level="global",
                placement="top-toolbar",
                owns_controls=("settings",),
                stable_across_states=True,
            ),
            region(
                "primary-workspace",
                level="primary",
                placement="main",
                owns_states=("empty", "file_loaded", "running", "result_ready"),
                owns_controls=("import", "run", "export"),
                owns_displays=("summary_card", "result_table"),
                owns_events=("click_import", "click_run", "run_success", "click_export"),
                stable_across_states=True,
            ),
            region(
                "failure-inspector",
                level="secondary",
                placement="right-inspector",
                parent_region_id="primary-workspace",
                owns_states=("failed",),
                owns_controls=("retry",),
                owns_events=("run_failure", "click_retry"),
            ),
            region(
                "cancel-overlay",
                level="overlay",
                placement="modal",
                parent_region_id="primary-workspace",
                owns_controls=("cancel",),
            ),
        ),
        state_region_map=(
            ("empty", "primary-workspace"),
            ("file_loaded", "primary-workspace"),
            ("running", "primary-workspace"),
            ("result_ready", "primary-workspace"),
            ("failed", "failure-inspector"),
        ),
        control_region_map=(
            ("settings", "top-toolbar"),
            ("import", "primary-workspace"),
            ("run", "primary-workspace"),
            ("export", "primary-workspace"),
            ("retry", "failure-inspector"),
            ("cancel", "cancel-overlay"),
        ),
        display_region_map=(
            ("summary_card", "primary-workspace"),
            ("result_table", "primary-workspace"),
        ),
        event_region_map=(
            ("click_import", "primary-workspace"),
            ("click_run", "primary-workspace"),
            ("click_cancel", "cancel-overlay"),
            ("run_success", "primary-workspace"),
            ("run_failure", "failure-inspector"),
            ("click_retry", "failure-inspector"),
            ("click_export", "primary-workspace"),
        ),
        hierarchy_edges=(
            ("primary-workspace", "failure-inspector"),
            ("primary-workspace", "cancel-overlay"),
        ),
        persistent_control_ids=("settings",),
        contextual_control_ids=("retry", "cancel"),
        overlay_region_ids=("cancel-overlay",),
        stable_region_ids=("top-toolbar", "primary-workspace"),
        validation_boundaries=("browser state transition test",),
        rationale="Global settings stay in the top toolbar; phase controls stay in the owning workspace or child region.",
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
        self.assertIn("missing_validation_plan", codes)

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


class UIStructureDerivationTests(unittest.TestCase):
    def test_complete_structure_derivation_can_continue(self):
        model = ui_model()
        model_report = review_ui_interaction_model(model)
        self.assertTrue(model_report.ok)

        report = review_ui_structure_derivation(derivation(), interaction_model=model)

        self.assertTrue(report.ok)
        self.assertEqual(0, report.blocker_count())

    def test_derivation_before_review_blocks(self):
        broken = UIStructureDerivation(
            "broken-ui-structure",
            source_interaction_model_id="import-run-ui-flow",
            parent_surface_id="workbench",
            target_regions=(region("main"),),
            state_region_map=(("empty", "main"),),
            control_region_map=(("import", "main"),),
            validation_boundaries=("browser test",),
            rationale="broken because source model was not reviewed",
        )

        report = review_ui_structure_derivation(broken, interaction_model=ui_model())

        self.assertFalse(report.ok)
        self.assertIn("source_interaction_model_not_reviewed", [finding.code for finding in report.findings])

    def test_unregistered_and_duplicate_regions_block(self):
        broken = UIStructureDerivation(
            "broken-ui-structure",
            source_interaction_model_id="import-run-ui-flow",
            parent_surface_id="workbench",
            interaction_model_reviewed=True,
            target_regions=(region("main"),),
            state_region_map=(("empty", "main"), ("empty", "other")),
            control_region_map=(("settings", "other"),),
            event_region_map=(("click_import", "other"),),
            persistent_control_ids=("settings",),
            validation_boundaries=("browser test",),
            rationale="broken unregistered regions",
        )

        report = review_ui_structure_derivation(broken, interaction_model=ui_model())
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("duplicate_state_region_owner", codes)
        self.assertIn("state_region_not_registered", codes)
        self.assertIn("control_region_not_registered", codes)
        self.assertIn("event_region_not_registered", codes)
        self.assertIn("persistent_control_not_stable_global", codes)

    def test_missing_rationale_and_placement_block(self):
        broken = UIStructureDerivation(
            "broken-ui-structure",
            source_interaction_model_id="import-run-ui-flow",
            parent_surface_id="workbench",
            interaction_model_reviewed=True,
            target_regions=(UIRegionRecommendation("main"),),
            state_region_map=(("empty", "main"),),
            control_region_map=(("import", "main"),),
        )

        report = review_ui_structure_derivation(broken, interaction_model=ui_model())
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("missing_validation_plan", codes)
        self.assertIn("missing_structure_rationale", codes)
        self.assertIn("missing_region_placement", codes)
        self.assertIn("missing_region_rationale", codes)

    def test_duplicate_information_same_region_blocks_without_rationale(self):
        model = UIInteractionModel(
            "region-duplicate-ui",
            initial_state_id="result_ready",
            states=(
                state(
                    "result_ready",
                    visible_displays=("summary_chart", "summary_text"),
                    terminal=True,
                ),
            ),
            controls=(control("settings", level="global", persistent=True),),
            displays=(
                display("summary_chart", "run_summary", display_type="chart"),
                display("summary_text", "run_summary", display_type="text"),
            ),
            transitions=(transition("click_settings", "settings", "result_ready", "result_ready"),),
            validation_boundaries=("UI redundancy review",),
            rationale="broken structure redundancy model",
        )
        broken = UIStructureDerivation(
            "region-duplicate-structure",
            source_interaction_model_id="region-duplicate-ui",
            parent_surface_id="workbench",
            interaction_model_reviewed=True,
            target_regions=(region("main"),),
            state_region_map=(("result_ready", "main"),),
            control_region_map=(("settings", "main"),),
            display_region_map=(("summary_chart", "main"), ("summary_text", "main")),
            validation_boundaries=("browser test",),
            rationale="both displays are placed in the same region without explaining why",
        )

        report = review_ui_structure_derivation(broken, interaction_model=model)

        self.assertFalse(report.ok)
        self.assertIn("duplicate_information_same_region", [finding.code for finding in report.findings])


if __name__ == "__main__":
    unittest.main()
