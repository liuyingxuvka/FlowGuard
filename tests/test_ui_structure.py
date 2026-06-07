import unittest
from dataclasses import replace

from flowguard import (
    UIControl,
    UIDisplayElement,
    UIFeatureContract,
    UIFeatureJourney,
    UIBlindspot,
    UIImplementationJourneyRun,
    UIImplementationStepEvidence,
    UIImplementationValidation,
    UIInteractionModel,
    UIJourneyCoverage,
    UIJourneyEntryPoint,
    UIRegionRecommendation,
    UIStateNode,
    UIStructureDerivation,
    UITextElement,
    UITextHierarchyBlueprint,
    UITypographyToken,
    UITerminalActionAllowance,
    UITransition,
    review_ui_implementation_validation,
    review_ui_interaction_model,
    review_ui_journey_coverage,
    review_ui_structure_derivation,
    review_ui_text_hierarchy,
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


def app_ui_model(*, include_forward_terminal_run: bool = False, include_orphan_state: bool = False) -> UIInteractionModel:
    states = (
        state(
            "launch",
            visible_controls=("new_project", "load_project", "exit"),
            enabled_controls=("new_project", "load_project", "exit"),
        ),
        state(
            "new_project_setup",
            visible_controls=("create_project", "cancel"),
            enabled_controls=("create_project", "cancel"),
        ),
        state(
            "create_failed",
            visible_controls=("retry_create", "cancel"),
            failure=True,
            enabled_controls=("retry_create", "cancel"),
            recovery_controls=("retry_create",),
        ),
        state("load_picker", visible_controls=("choose_file", "cancel"), enabled_controls=("choose_file", "cancel")),
        state(
            "load_failed",
            visible_controls=("retry_load", "cancel"),
            failure=True,
            enabled_controls=("retry_load", "cancel"),
            recovery_controls=("retry_load",),
        ),
        state(
            "workbench_ready",
            visible_controls=("export",) if not include_forward_terminal_run else ("export", "run"),
            enabled_controls=("export",) if not include_forward_terminal_run else ("export", "run"),
            visible_displays=("project_summary",),
            terminal=True,
        ),
        state("running", visible_controls=("cancel",), enabled_controls=("cancel",)),
        state("cancelled", visible_controls=("exit",), terminal=True, enabled_controls=("exit",)),
        state("exited", visible_controls=(), terminal=True, enabled_controls=()),
    )
    if include_orphan_state:
        states = states + (state("orphan_review", visible_controls=("exit",), enabled_controls=("exit",)),)
    transitions = (
        transition("click_new_project", "new_project", "launch", "new_project_setup"),
        transition("create_project_success", "create_project", "new_project_setup", "workbench_ready"),
        transition("create_project_failure", "create_project", "new_project_setup", "create_failed"),
        transition("click_retry_create", "retry_create", "create_failed", "new_project_setup"),
        transition("click_cancel_create_failed", "cancel", "create_failed", "cancelled"),
        transition("click_load_project", "load_project", "launch", "load_picker"),
        transition("load_project_success", "choose_file", "load_picker", "workbench_ready"),
        transition("load_project_failure", "choose_file", "load_picker", "load_failed"),
        transition("click_retry_load", "retry_load", "load_failed", "load_picker"),
        transition("click_cancel_load_failed", "cancel", "load_failed", "cancelled"),
        transition("click_cancel_new", "cancel", "new_project_setup", "cancelled"),
        transition("click_cancel_load", "cancel", "load_picker", "cancelled"),
        transition("click_exit", "exit", "launch", "exited"),
        transition("click_exit_cancelled", "exit", "cancelled", "exited"),
        transition("click_export", "export", "workbench_ready", "workbench_ready"),
    )
    if include_forward_terminal_run:
        transitions = transitions + (transition("click_run_again", "run", "workbench_ready", "running"),)
    controls = (
        control("new_project", level="primary"),
        control("create_project", level="primary", depends_on_states=("new_project_setup",)),
        control("load_project", level="primary"),
        control("choose_file", level="primary", depends_on_states=("load_picker",)),
        control("retry_create", level="contextual", depends_on_states=("create_failed",)),
        control("retry_load", level="contextual", depends_on_states=("load_failed",)),
        control("cancel", level="contextual"),
        control("exit", level="secondary"),
        control("export", level="secondary", depends_on_states=("workbench_ready",)),
    )
    if include_forward_terminal_run:
        controls = controls + (control("run", level="primary", depends_on_states=("workbench_ready",)),)
    return UIInteractionModel(
        "project-app-ui-flow",
        initial_state_id="launch",
        states=states,
        controls=controls,
        displays=(display("project_summary", "project_summary", depends_on_states=("workbench_ready",)),),
        transitions=transitions,
        validation_boundaries=("UI journey scenario review",),
        rationale="The app model starts at launch and branches into new, load, cancel, exit, and workbench states.",
    )


def journey_entry(entry_id: str, control_id: str, event_id: str, **kwargs) -> UIJourneyEntryPoint:
    defaults = {
        "label": entry_id.replace("_", " ").title(),
        "source_state_ids": ("launch",),
        "rationale": f"{entry_id} is a launch entry point",
    }
    defaults.update(kwargs)
    return UIJourneyEntryPoint(entry_id, control_id, event_id, **defaults)


def feature_journey(feature_id: str, **kwargs) -> UIFeatureJourney:
    defaults = {
        "label": feature_id.replace("_", " ").title(),
        "entry_point_ids": (feature_id,),
        "success_terminal_state_ids": ("workbench_ready",),
        "validation_boundaries": ("journey scenario review",),
        "rationale": f"{feature_id} is covered from launch to terminal state",
    }
    defaults.update(kwargs)
    return UIFeatureJourney(feature_id, **defaults)


def journey_coverage(**kwargs) -> UIJourneyCoverage:
    defaults = {
        "source_interaction_model_id": "project-app-ui-flow",
        "launch_state_id": "launch",
        "entry_points": (
            journey_entry("new_project", "new_project", "click_new_project"),
            journey_entry("load_project", "load_project", "click_load_project"),
            journey_entry("exit_app", "exit", "click_exit"),
        ),
        "feature_journeys": (
            feature_journey(
                "new_project",
                required_state_ids=("new_project_setup",),
                required_event_ids=("click_new_project", "create_project_success", "create_project_failure"),
                failure_state_ids=("create_failed",),
                recovery_event_ids=("click_retry_create",),
                cancel_event_ids=("click_cancel_new", "click_cancel_create_failed"),
            ),
            feature_journey(
                "load_project",
                required_state_ids=("load_picker",),
                required_event_ids=("click_load_project", "load_project_success", "load_project_failure"),
                failure_state_ids=("load_failed",),
                recovery_event_ids=("click_retry_load",),
                cancel_event_ids=("click_cancel_load", "click_cancel_load_failed"),
            ),
            feature_journey(
                "exit_app",
                required_event_ids=("click_exit",),
                success_terminal_state_ids=("exited",),
            ),
        ),
        "terminal_action_allowances": (
            UITerminalActionAllowance(
                "workbench_ready",
                "click_export",
                "export",
                rationale="Export is a terminal-state side effect, not forward progress.",
            ),
            UITerminalActionAllowance(
                "cancelled",
                "click_exit_cancelled",
                "exit",
                rationale="Exit closes the app after a cancelled setup or load branch.",
            ),
        ),
        "residual_blindspots": (
            UIBlindspot(
                "open_recent_project",
                feature_id="open_recent_project",
                reason="Recent-project history is a downstream shell integration in this template.",
                owner="browser or desktop shell validation",
                validation_boundaries=("shell integration test",),
                rationale="The template records the omitted branch instead of claiming it is covered.",
            ),
        ),
        "interaction_model_reviewed": True,
        "validation_boundaries": ("journey scenario review", "browser state transition test"),
        "rationale": "Complete app-level UI claims require launch-to-terminal journey coverage.",
    }
    defaults.update(kwargs)
    return UIJourneyCoverage("project-app-journeys", **defaults)


def feature_contract(feature_id: str, **kwargs) -> UIFeatureContract:
    journey_ids = kwargs.pop("journey_ids", (feature_id,))
    required_control_ids = kwargs.pop("required_control_ids", ())
    required_event_ids = kwargs.pop("required_event_ids", ())
    defaults = {
        "label": feature_id.replace("_", " ").title(),
        "journey_ids": journey_ids,
        "required_control_ids": required_control_ids,
        "required_event_ids": required_event_ids,
        "validation_boundaries": ("functional model review",),
        "rationale": f"{feature_id} is a user-visible functional feature.",
    }
    defaults.update(kwargs)
    return UIFeatureContract(feature_id, **defaults)


def implementation_step(event_id: str, control_id: str, source: str, target: str, **kwargs) -> UIImplementationStepEvidence:
    defaults = {
        "control_id": control_id,
        "source_state_id": source,
        "target_state_id": target,
        "method": "browser",
        "result": "passed",
        "evidence_ref": f"evidence://{event_id}",
        "observed_state_id": target,
        "rationale": f"{event_id} was observed in the running UI.",
    }
    defaults.update(kwargs)
    return UIImplementationStepEvidence(f"{event_id}_step", event_id, **defaults)


def implementation_run(feature_id: str, *steps: UIImplementationStepEvidence, **kwargs) -> UIImplementationJourneyRun:
    defaults = {
        "journey_id": feature_id,
        "steps": steps,
        "method": "browser",
        "result": "passed",
        "evidence_ref": f"evidence://{feature_id}",
        "model_revision": "ui-rev-1",
        "validation_boundaries": ("browser click-through",),
        "rationale": f"{feature_id} was clicked through from the running UI.",
    }
    defaults.update(kwargs)
    return UIImplementationJourneyRun(f"{feature_id}_run", feature_id, **defaults)


def implementation_validation(**kwargs) -> UIImplementationValidation:
    defaults = {
        "source_feature_model_id": "project-feature-model",
        "source_interaction_model_id": "project-app-ui-flow",
        "source_journey_coverage_id": "project-app-journeys",
        "implementation_target": "local browser build",
        "current_model_revision": "ui-rev-1",
        "feature_contracts": (
            feature_contract(
                "new_project",
                required_control_ids=("new_project", "create_project", "retry_create"),
                required_event_ids=(
                    "click_new_project",
                    "create_project_success",
                    "create_project_failure",
                    "click_retry_create",
                    "click_cancel_new",
                    "click_cancel_create_failed",
                ),
            ),
            feature_contract(
                "load_project",
                required_control_ids=("load_project", "choose_file", "retry_load"),
                required_event_ids=(
                    "click_load_project",
                    "load_project_success",
                    "load_project_failure",
                    "click_retry_load",
                    "click_cancel_load",
                    "click_cancel_load_failed",
                ),
            ),
            feature_contract(
                "exit_app",
                required_control_ids=("exit",),
                required_event_ids=("click_exit",),
            ),
        ),
        "journey_runs": (
            implementation_run(
                "new_project",
                implementation_step("click_new_project", "new_project", "launch", "new_project_setup"),
                implementation_step("create_project_success", "create_project", "new_project_setup", "workbench_ready"),
                implementation_step("create_project_failure", "create_project", "new_project_setup", "create_failed"),
                implementation_step("click_retry_create", "retry_create", "create_failed", "new_project_setup"),
                implementation_step("click_cancel_new", "cancel", "new_project_setup", "cancelled"),
                implementation_step("click_cancel_create_failed", "cancel", "create_failed", "cancelled"),
            ),
            implementation_run(
                "load_project",
                implementation_step("click_load_project", "load_project", "launch", "load_picker"),
                implementation_step("load_project_success", "choose_file", "load_picker", "workbench_ready"),
                implementation_step("load_project_failure", "choose_file", "load_picker", "load_failed"),
                implementation_step("click_retry_load", "retry_load", "load_failed", "load_picker"),
                implementation_step("click_cancel_load", "cancel", "load_picker", "cancelled"),
                implementation_step("click_cancel_load_failed", "cancel", "load_failed", "cancelled"),
            ),
            implementation_run(
                "exit_app",
                implementation_step("click_exit", "exit", "launch", "exited"),
                journey_id="exit_app",
            ),
        ),
        "pure_ui_control_ids": ("cancel", "export"),
        "pure_ui_event_ids": ("click_exit_cancelled", "click_export"),
        "implementation_blindspots": (
            UIBlindspot(
                "open_recent_project_impl",
                feature_id="open_recent_project",
                reason="Recent-project history requires shell state not present in the template.",
                owner="browser or desktop validation",
                validation_boundaries=("desktop shell validation",),
                rationale="The branch is deferred instead of claimed as clicked through.",
            ),
        ),
        "journey_coverage_reviewed": True,
        "validation_boundaries": ("browser click-through", "manual fallback"),
        "rationale": "Implemented UI claims require functional features, modeled UI journeys, and real UI evidence.",
    }
    defaults.update(kwargs)
    return UIImplementationValidation("project-app-implementation-validation", **defaults)


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


def typography_token(token_id: str, hierarchy_level: int, text_roles: tuple[str, ...]) -> UITypographyToken:
    visual_scale_by_token = {
        "page-title": "surface-title",
        "section-title": "region-heading",
        "panel-title": "region-heading",
        "control-label": "standard-text",
        "status-text": "standard-text",
        "body-text": "standard-text",
        "caption-text": "supporting-text",
    }
    return UITypographyToken(
        token_id,
        hierarchy_level=hierarchy_level,
        text_roles=text_roles,
        scale=visual_scale_by_token.get(token_id, "standard-text"),
        weight="regular" if hierarchy_level >= 4 else "semibold",
        color_role="default",
        rationale=f"{token_id} is the semantic typography token for {text_roles}",
    )


def text_element(text_id: str, role: str, token_id: str, semantic_key: str, **kwargs) -> UITextElement:
    defaults = {
        "label": text_id.replace("_", " ").title(),
        "region_id": "primary-workspace",
        "rationale": f"{text_id} is derived from the modeled UI hierarchy",
    }
    defaults.update(kwargs)
    return UITextElement(text_id, role, token_id, semantic_key, **defaults)


def text_hierarchy() -> UITextHierarchyBlueprint:
    return UITextHierarchyBlueprint(
        "import-run-text-hierarchy",
        source_interaction_model_id="import-run-ui-flow",
        source_structure_derivation_id="import-run-ui-structure",
        parent_surface_id="import-run-workbench",
        structure_derivation_reviewed=True,
        typography_tokens=(
            typography_token("page-title", 1, ("page_title",)),
            typography_token("section-title", 2, ("section_title",)),
            typography_token("panel-title", 3, ("panel_title",)),
            typography_token("control-label", 4, ("button_label", "menu_label", "tab_label", "control_label")),
            typography_token("status-text", 4, ("status_text", "error_text")),
            typography_token("body-text", 5, ("body_text", "field_label", "data_value")),
            typography_token("caption-text", 6, ("caption", "help_text")),
        ),
        text_elements=(
            text_element("surface_title", "page_title", "page-title", "surface_title"),
            text_element(
                "workspace_title",
                "section_title",
                "section-title",
                "workflow_area",
                parent_text_id="surface_title",
            ),
            text_element(
                "settings_label",
                "button_label",
                "control-label",
                "settings_action",
                region_id="top-toolbar",
                source_control_id="settings",
            ),
            text_element("import_label", "button_label", "control-label", "import_action", source_control_id="import"),
            text_element("run_label", "button_label", "control-label", "run_action", source_control_id="run"),
            text_element("export_label", "button_label", "control-label", "export_action", source_control_id="export"),
            text_element(
                "results_title",
                "panel_title",
                "panel-title",
                "results_panel",
                parent_text_id="workspace_title",
                source_state_ids=("result_ready",),
            ),
            text_element(
                "summary_value",
                "status_text",
                "status-text",
                "run_summary",
                source_display_id="summary_card",
                visible_in_states=("result_ready",),
            ),
            text_element(
                "result_table_caption",
                "caption",
                "caption-text",
                "result_rows",
                source_display_id="result_table",
                visible_in_states=("result_ready",),
            ),
            text_element(
                "failure_title",
                "panel_title",
                "panel-title",
                "failure_panel",
                region_id="failure-inspector",
                parent_text_id="workspace_title",
                source_state_ids=("failed",),
            ),
            text_element(
                "retry_label",
                "button_label",
                "control-label",
                "retry_action",
                region_id="failure-inspector",
                source_control_id="retry",
                visible_in_states=("failed",),
            ),
            text_element(
                "cancel_label",
                "button_label",
                "control-label",
                "cancel_action",
                region_id="cancel-overlay",
                source_control_id="cancel",
                visible_in_states=("running",),
            ),
        ),
        validation_boundaries=("design token review", "browser text hierarchy review"),
        rationale="Text roles and tokens are derived from the reviewed UI structure, not chosen ad hoc.",
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


class UIJourneyCoverageTests(unittest.TestCase):
    def test_complete_app_journey_coverage_can_continue(self):
        model = app_ui_model()
        self.assertTrue(review_ui_interaction_model(model).ok)

        report = review_ui_journey_coverage(journey_coverage(), interaction_model=model)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(0, report.blocker_count())
        self.assertIn("launch", report.reachable_state_ids)
        self.assertIn("workbench_ready", report.reachable_state_ids)

    def test_missing_launch_state_and_entry_blocks(self):
        broken = journey_coverage(
            launch_state_id="missing_launch",
            entry_points=(),
            feature_journeys=(feature_journey("load_project", entry_point_ids=("load_project",)),),
        )

        report = review_ui_journey_coverage(broken, interaction_model=app_ui_model())
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("launch_state_not_registered", codes)
        self.assertIn("missing_entry_points", codes)
        self.assertIn("feature_entry_point_not_declared", codes)

    def test_unreachable_required_state_blocks(self):
        broken = journey_coverage(
            feature_journeys=(
                feature_journey(
                    "new_project",
                    required_state_ids=("orphan_review",),
                    required_event_ids=("click_new_project",),
                ),
            )
        )

        report = review_ui_journey_coverage(broken, interaction_model=app_ui_model(include_orphan_state=True))
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("feature_state_unreachable_from_launch", codes)

    def test_unknown_required_event_blocks(self):
        broken = journey_coverage(
            feature_journeys=(feature_journey("new_project", required_event_ids=("ghost_event",)),)
        )

        report = review_ui_journey_coverage(broken, interaction_model=app_ui_model())

        self.assertFalse(report.ok)
        self.assertIn("feature_event_not_registered", [finding.code for finding in report.findings])

    def test_visible_control_without_modeled_event_blocks(self):
        base = app_ui_model()
        launch = replace(
            base.states[0],
            visible_controls=base.states[0].visible_controls + ("help",),
            enabled_controls=base.states[0].enabled_controls + ("help",),
        )
        model = UIInteractionModel(
            base.model_id,
            initial_state_id=base.initial_state_id,
            states=(launch,) + base.states[1:],
            controls=base.controls + (control("help", level="secondary"),),
            displays=base.displays,
            transitions=base.transitions,
            validation_boundaries=base.validation_boundaries,
            rationale=base.rationale,
        )

        report = review_ui_journey_coverage(journey_coverage(), interaction_model=model)

        self.assertFalse(report.ok)
        self.assertIn("visible_control_without_modeled_event", [finding.code for finding in report.findings])

    def test_reachable_event_missing_from_journey_coverage_blocks(self):
        base = app_ui_model()
        launch = replace(
            base.states[0],
            visible_controls=base.states[0].visible_controls + ("help",),
            enabled_controls=base.states[0].enabled_controls + ("help",),
        )
        model = UIInteractionModel(
            base.model_id,
            initial_state_id=base.initial_state_id,
            states=(launch,) + base.states[1:],
            controls=base.controls + (control("help", level="secondary"),),
            displays=base.displays,
            transitions=base.transitions + (transition("click_help", "help", "launch", "launch"),),
            validation_boundaries=base.validation_boundaries,
            rationale=base.rationale,
        )

        report = review_ui_journey_coverage(journey_coverage(), interaction_model=model)

        self.assertFalse(report.ok)
        self.assertIn("journey_event_not_covered", [finding.code for finding in report.findings])

    def test_residual_blindspot_can_bound_uncovered_visible_branch(self):
        base = app_ui_model()
        launch = replace(
            base.states[0],
            visible_controls=base.states[0].visible_controls + ("help",),
            enabled_controls=base.states[0].enabled_controls + ("help",),
        )
        model = UIInteractionModel(
            base.model_id,
            initial_state_id=base.initial_state_id,
            states=(launch,) + base.states[1:],
            controls=base.controls + (control("help", level="secondary"),),
            displays=base.displays,
            transitions=base.transitions + (transition("click_help", "help", "launch", "launch"),),
            validation_boundaries=base.validation_boundaries,
            rationale=base.rationale,
        )
        coverage = journey_coverage(
            residual_blindspots=journey_coverage().residual_blindspots
            + (
                UIBlindspot(
                    "help_center",
                    feature_id="help_center",
                    control_ids=("help",),
                    event_ids=("click_help",),
                    reason="Help center content is owned by the support surface.",
                    owner="support UI journey review",
                    validation_boundaries=("support UI browser test",),
                    rationale="The visible branch is bounded instead of silently omitted.",
                ),
            )
        )

        report = review_ui_journey_coverage(coverage, interaction_model=model)

        self.assertTrue(report.ok, report.format_text())

    def test_missing_success_terminal_blocks(self):
        broken = journey_coverage(
            feature_journeys=(feature_journey("new_project", success_terminal_state_ids=()),)
        )

        report = review_ui_journey_coverage(broken, interaction_model=app_ui_model())

        self.assertFalse(report.ok)
        self.assertIn("missing_feature_success_terminal", [finding.code for finding in report.findings])

    def test_failure_without_named_recovery_blocks(self):
        broken = journey_coverage(
            feature_journeys=(
                feature_journey(
                    "load_project",
                    required_state_ids=("load_picker",),
                    required_event_ids=("click_load_project", "load_project_success"),
                    failure_state_ids=("load_failed",),
                    recovery_event_ids=(),
                    cancel_event_ids=(),
                    exit_event_ids=(),
                ),
            )
        )

        report = review_ui_journey_coverage(broken, interaction_model=app_ui_model())

        self.assertFalse(report.ok)
        self.assertIn("missing_feature_failure_handling", [finding.code for finding in report.findings])

    def test_terminal_forward_action_without_allowed_purpose_blocks(self):
        broken = journey_coverage(
            terminal_action_allowances=(
                UITerminalActionAllowance(
                    "workbench_ready",
                    "click_export",
                    "export",
                    rationale="Export is allowed.",
                ),
            )
        )

        report = review_ui_journey_coverage(
            broken,
            interaction_model=app_ui_model(include_forward_terminal_run=True),
        )

        self.assertFalse(report.ok)
        self.assertIn("terminal_action_without_allowance", [finding.code for finding in report.findings])

    def test_terminal_forward_action_with_export_purpose_still_blocks(self):
        broken = journey_coverage(
            terminal_action_allowances=(
                UITerminalActionAllowance(
                    "workbench_ready",
                    "click_export",
                    "export",
                    rationale="Export is allowed.",
                ),
                UITerminalActionAllowance(
                    "workbench_ready",
                    "click_run_again",
                    "export",
                    rationale="Wrongly classifies forward run as export.",
                ),
            )
        )

        report = review_ui_journey_coverage(
            broken,
            interaction_model=app_ui_model(include_forward_terminal_run=True),
        )

        self.assertFalse(report.ok)
        self.assertIn("terminal_forward_action", [finding.code for finding in report.findings])

    def test_blindspot_without_validation_blocks(self):
        broken = journey_coverage(
            residual_blindspots=(
                UIBlindspot("open_recent_project", reason="deferred", rationale="deferred branch"),
            )
        )

        report = review_ui_journey_coverage(broken, interaction_model=app_ui_model())

        self.assertFalse(report.ok)
        self.assertIn("missing_blindspot_validation", [finding.code for finding in report.findings])


class UIImplementationValidationTests(unittest.TestCase):
    def test_complete_implementation_validation_can_continue(self):
        model = app_ui_model()
        coverage = journey_coverage()

        report = review_ui_implementation_validation(
            implementation_validation(),
            interaction_model=model,
            journey_coverage=coverage,
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertIn("new_project", report.covered_feature_ids)
        self.assertIn("click_load_project", report.covered_event_ids)

    def test_user_visible_feature_without_ui_path_blocks(self):
        validation = implementation_validation(
            feature_contracts=implementation_validation().feature_contracts
            + (
                feature_contract(
                    "publish_project",
                    required_control_ids=("publish",),
                    required_event_ids=("click_publish",),
                ),
            )
        )

        report = review_ui_implementation_validation(
            validation,
            interaction_model=app_ui_model(),
            journey_coverage=journey_coverage(),
        )

        self.assertFalse(report.ok)
        self.assertIn("feature_not_exposed_by_ui_model", [finding.code for finding in report.findings])

    def test_reachable_control_without_functional_owner_blocks(self):
        base = app_ui_model()
        launch = replace(
            base.states[0],
            visible_controls=base.states[0].visible_controls + ("help",),
            enabled_controls=base.states[0].enabled_controls + ("help",),
        )
        model = UIInteractionModel(
            base.model_id,
            initial_state_id=base.initial_state_id,
            states=(launch,) + base.states[1:],
            controls=base.controls + (control("help", level="secondary"),),
            displays=base.displays,
            transitions=base.transitions + (transition("click_help", "help", "launch", "launch"),),
            validation_boundaries=base.validation_boundaries,
            rationale=base.rationale,
        )
        coverage = journey_coverage(
            residual_blindspots=journey_coverage().residual_blindspots
            + (
                UIBlindspot(
                    "help_center",
                    feature_id="help_center",
                    control_ids=("help",),
                    event_ids=("click_help",),
                    reason="Help center is modeled but owned by support.",
                    owner="support UI journey review",
                    validation_boundaries=("support UI browser test",),
                    rationale="Journey coverage scopes the branch.",
                ),
            )
        )

        report = review_ui_implementation_validation(
            implementation_validation(),
            interaction_model=model,
            journey_coverage=coverage,
        )

        self.assertFalse(report.ok)
        self.assertIn("implementation_control_without_feature_owner", [finding.code for finding in report.findings])

    def test_missing_run_for_feature_journey_blocks(self):
        validation = implementation_validation(
            journey_runs=tuple(
                run for run in implementation_validation().journey_runs if run.feature_id != "load_project"
            )
        )

        report = review_ui_implementation_validation(
            validation,
            interaction_model=app_ui_model(),
            journey_coverage=journey_coverage(),
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_implementation_run_for_journey", [finding.code for finding in report.findings])

    def test_success_only_evidence_missing_failure_recovery_blocks(self):
        validation = implementation_validation(
            journey_runs=(
                implementation_run(
                    "new_project",
                    implementation_step("click_new_project", "new_project", "launch", "new_project_setup"),
                    implementation_step(
                        "create_project_success",
                        "create_project",
                        "new_project_setup",
                        "workbench_ready",
                    ),
                ),
            )
            + tuple(run for run in implementation_validation().journey_runs if run.feature_id != "new_project")
        )

        report = review_ui_implementation_validation(
            validation,
            interaction_model=app_ui_model(),
            journey_coverage=journey_coverage(),
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_implementation_event_evidence", [finding.code for finding in report.findings])

    def test_stale_implementation_evidence_blocks(self):
        stale_runs = tuple(replace(run, model_revision="old-rev") for run in implementation_validation().journey_runs)
        validation = implementation_validation(journey_runs=stale_runs)

        report = review_ui_implementation_validation(
            validation,
            interaction_model=app_ui_model(),
            journey_coverage=journey_coverage(),
        )

        self.assertFalse(report.ok)
        self.assertIn("stale_implementation_evidence", [finding.code for finding in report.findings])

    def test_failed_or_skipped_step_evidence_blocks(self):
        runs = list(implementation_validation().journey_runs)
        broken_steps = (
            replace(runs[0].steps[0], result="skipped"),
        ) + runs[0].steps[1:]
        runs[0] = replace(runs[0], steps=broken_steps)
        validation = implementation_validation(journey_runs=tuple(runs))

        report = review_ui_implementation_validation(
            validation,
            interaction_model=app_ui_model(),
            journey_coverage=journey_coverage(),
        )

        self.assertFalse(report.ok)
        self.assertIn("step_evidence_not_passed", [finding.code for finding in report.findings])

    def test_implementation_blindspot_can_bound_unverified_branch(self):
        validation = implementation_validation(
            journey_runs=tuple(
                run for run in implementation_validation().journey_runs if run.feature_id != "load_project"
            ),
            implementation_blindspots=implementation_validation().implementation_blindspots
            + (
                UIBlindspot(
                    "load_project_manual_followup",
                    feature_id="load_project",
                    reason="Native file picker cannot run in this browser check.",
                    owner="manual QA",
                    validation_boundaries=("manual desktop click-through",),
                    rationale="The branch is explicitly deferred to manual validation.",
                ),
            ),
        )

        report = review_ui_implementation_validation(
            validation,
            interaction_model=app_ui_model(),
            journey_coverage=journey_coverage(),
        )

        self.assertTrue(report.ok, report.format_text())

    def test_unscoped_implementation_blindspot_blocks(self):
        validation = implementation_validation(
            implementation_blindspots=(UIBlindspot("mystery"),)
        )

        report = review_ui_implementation_validation(
            validation,
            interaction_model=app_ui_model(),
            journey_coverage=journey_coverage(),
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_implementation_blindspot_scope", [finding.code for finding in report.findings])


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


class UITextHierarchyTests(unittest.TestCase):
    def test_complete_text_hierarchy_can_continue(self):
        model = ui_model()
        structure = derivation()
        self.assertTrue(review_ui_interaction_model(model).ok)
        self.assertTrue(review_ui_structure_derivation(structure, interaction_model=model).ok)

        report = review_ui_text_hierarchy(
            text_hierarchy(),
            interaction_model=model,
            structure_derivation=structure,
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(0, report.blocker_count())

    def test_text_hierarchy_before_review_and_unknown_source_blocks(self):
        broken = UITextHierarchyBlueprint(
            "broken-text-hierarchy",
            source_interaction_model_id="wrong-model",
            source_structure_derivation_id="wrong-structure",
            parent_surface_id="workbench",
            typography_tokens=(typography_token("control-label", 4, ("button_label",)),),
            text_elements=(
                text_element(
                    "ghost_button",
                    "button_label",
                    "control-label",
                    "ghost_action",
                    source_control_id="ghost",
                ),
            ),
            validation_boundaries=("text review",),
            rationale="broken source references",
        )

        report = review_ui_text_hierarchy(
            broken,
            interaction_model=ui_model(),
            structure_derivation=derivation(),
        )
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("source_interaction_model_mismatch", codes)
        self.assertIn("source_structure_derivation_mismatch", codes)
        self.assertIn("source_structure_derivation_not_reviewed", codes)
        self.assertIn("text_control_not_in_interaction_model", codes)

    def test_prominent_button_and_flat_child_title_block(self):
        broken = UITextHierarchyBlueprint(
            "broken-prominence",
            source_interaction_model_id="import-run-ui-flow",
            source_structure_derivation_id="import-run-ui-structure",
            parent_surface_id="import-run-workbench",
            structure_derivation_reviewed=True,
            typography_tokens=(
                typography_token("section-title", 2, ("section_title",)),
                typography_token("panel-at-section-level", 2, ("panel_title",)),
                typography_token("hero-button", 1, ("button_label",)),
            ),
            text_elements=(
                text_element("parent_section", "section_title", "section-title", "parent_section"),
                text_element(
                    "child_panel",
                    "panel_title",
                    "panel-at-section-level",
                    "child_panel",
                    parent_text_id="parent_section",
                ),
                text_element(
                    "import_label",
                    "button_label",
                    "hero-button",
                    "import_action",
                    source_control_id="import",
                ),
            ),
            validation_boundaries=("text review",),
            rationale="broken hierarchy",
        )

        report = review_ui_text_hierarchy(
            broken,
            interaction_model=ui_model(),
            structure_derivation=derivation(),
        )
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("child_text_not_less_prominent_than_parent", codes)
        self.assertIn("text_role_too_prominent", codes)

    def test_duplicate_text_semantic_same_region_state_requires_rationale(self):
        broken = UITextHierarchyBlueprint(
            "duplicate-text",
            source_interaction_model_id="import-run-ui-flow",
            source_structure_derivation_id="import-run-ui-structure",
            parent_surface_id="import-run-workbench",
            structure_derivation_reviewed=True,
            typography_tokens=(typography_token("status-text", 4, ("status_text",)),),
            text_elements=(
                text_element(
                    "summary_status",
                    "status_text",
                    "status-text",
                    "run_summary",
                    source_display_id="summary_card",
                    visible_in_states=("result_ready",),
                ),
                text_element(
                    "summary_sentence",
                    "status_text",
                    "status-text",
                    "run_summary",
                    source_display_id="summary_card",
                    visible_in_states=("result_ready",),
                ),
            ),
            validation_boundaries=("text review",),
            rationale="broken duplicate semantic text",
        )

        report = review_ui_text_hierarchy(
            broken,
            interaction_model=ui_model(),
            structure_derivation=derivation(),
        )

        self.assertFalse(report.ok)
        self.assertIn("duplicate_text_semantic_same_region_state", [finding.code for finding in report.findings])

    def test_justified_duplicate_text_semantic_can_continue(self):
        blueprint = UITextHierarchyBlueprint(
            "justified-duplicate-text",
            source_interaction_model_id="import-run-ui-flow",
            source_structure_derivation_id="import-run-ui-structure",
            parent_surface_id="import-run-workbench",
            structure_derivation_reviewed=True,
            typography_tokens=(typography_token("status-text", 4, ("status_text",)),),
            text_elements=(
                text_element(
                    "summary_status",
                    "status_text",
                    "status-text",
                    "run_summary",
                    source_display_id="summary_card",
                    visible_in_states=("result_ready",),
                    duplicate_group="summary-accessibility",
                    redundancy_rationale="The compact metric and screen-reader sentence expose the same semantic result intentionally.",
                ),
                text_element(
                    "summary_sentence",
                    "status_text",
                    "status-text",
                    "run_summary",
                    source_display_id="summary_card",
                    visible_in_states=("result_ready",),
                    duplicate_group="summary-accessibility",
                    redundancy_rationale="The sentence carries the same summary for accessibility.",
                ),
            ),
            validation_boundaries=("text review",),
            rationale="intentional duplicate semantic text is modeled",
        )

        report = review_ui_text_hierarchy(
            blueprint,
            interaction_model=ui_model(),
            structure_derivation=derivation(),
        )

        self.assertTrue(report.ok, report.format_text())


if __name__ == "__main__":
    unittest.main()
