"""Template text for FlowGuard ui flow structure route."""

from __future__ import annotations

UI_FLOW_STRUCTURE_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Model UI-level interaction behavior first, then derive parent/child UI structure and text hierarchy from that model.
Guards against: layout-only UI plans, unmodeled controls, missing recovery actions, drifting menu levels, unstable global controls, duplicate information, overlapping same-level controls, ad hoc headings, over-prominent button text, and hierarchy recommendations that are not tied to UI state.
Use before editing: Ask for this route before visual design or frontend implementation when UI controls, states, navigation, panels, menus, overlays, or parent/child UI topology matter.
Run: python .flowguard/ui_flow_structure/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    UIControl,
    UIDisplayElement,
    UIFeatureContract,
    UIFeatureJourney,
    UIImplementationBlindspot,
    UIImplementationJourneyRun,
    UIImplementationStepEvidence,
    UIImplementationValidation,
    UIInteractionModel,
    UIJourneyCoverage,
    UIJourneyEntryPoint,
    UIRegionRecommendation,
    UIResidualBlindspot,
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


def interaction_model() -> UIInteractionModel:
    return UIInteractionModel(
        "project-workbench-ui-flow",
        initial_state_id="launch",
        source_product_model_id="project-workbench-product-flow",
        states=(
            UIStateNode(
                "launch",
                visible_controls=("new_project", "load_project", "settings", "run", "export", "exit"),
                enabled_controls=("new_project", "load_project", "settings", "exit"),
                disabled_controls=("run", "export"),
                rationale="The first screen lets the user create a new project, load an existing project, adjust settings, or exit.",
            ),
            UIStateNode(
                "new_project_setup",
                visible_controls=("create_project", "cancel", "settings"),
                enabled_controls=("create_project", "cancel", "settings"),
                disabled_controls=("run", "export"),
                rationale="A new project flow collects setup before workbench actions become available.",
            ),
            UIStateNode(
                "load_picker",
                visible_controls=("choose_file", "cancel", "settings"),
                enabled_controls=("choose_file", "cancel", "settings"),
                disabled_controls=("run", "export"),
                rationale="Loading an existing project scopes the UI to file choice or cancellation.",
            ),
            UIStateNode(
                "loaded",
                visible_controls=("run", "settings", "export"),
                enabled_controls=("run", "settings"),
                disabled_controls=("export",),
                rationale="A loaded file enables the primary run action.",
            ),
            UIStateNode(
                "running",
                visible_controls=("cancel", "settings"),
                enabled_controls=("cancel",),
                disabled_controls=("run", "export"),
                rationale="Running work scopes the UI to cancellation and status.",
            ),
            UIStateNode(
                "result_ready",
                visible_controls=("export", "settings"),
                enabled_controls=("export", "settings"),
                visible_displays=("summary_card", "result_table"),
                terminal=True,
                rationale="The result state is a success terminal that enables export.",
            ),
            UIStateNode(
                "failed",
                visible_controls=("retry", "settings"),
                enabled_controls=("retry", "settings"),
                recovery_controls=("retry",),
                failure=True,
                rationale="A recoverable failure offers retry and global settings.",
            ),
            UIStateNode(
                "cancelled",
                visible_controls=("exit", "settings"),
                enabled_controls=("exit", "settings"),
                terminal=True,
                rationale="Cancelled setup or load work reaches a terminal cancellation state.",
            ),
            UIStateNode(
                "exited",
                visible_controls=(),
                enabled_controls=(),
                terminal=True,
                rationale="Exit closes the app-level flow.",
            ),
        ),
        controls=(
            UIControl(
                "settings",
                label="Settings",
                level="global",
                placement_hint="top-toolbar",
                persistent=True,
                rationale="Settings are always available and should not drift between screens.",
            ),
            UIControl("new_project", label="New", level="primary", rationale="New project starts a launch-level feature journey."),
            UIControl("load_project", label="Load", level="primary", rationale="Load project starts a launch-level feature journey."),
            UIControl(
                "create_project",
                label="Create",
                level="primary",
                depends_on_states=("new_project_setup",),
                rationale="Create completes new project setup.",
            ),
            UIControl(
                "choose_file",
                label="Choose",
                level="primary",
                depends_on_states=("load_picker",),
                rationale="Choose loads an existing project file.",
            ),
            UIControl(
                "run",
                label="Run",
                level="primary",
                depends_on_states=("loaded",),
                rationale="Run advances the main workflow after input exists.",
            ),
            UIControl(
                "cancel",
                label="Cancel",
                level="contextual",
                depends_on_states=("running",),
                rationale="Cancel only exists while work is running.",
            ),
            UIControl(
                "retry",
                label="Retry",
                level="contextual",
                depends_on_states=("failed",),
                rationale="Retry recovers from a failed run.",
            ),
            UIControl(
                "export",
                label="Export",
                level="secondary",
                depends_on_states=("result_ready",),
                rationale="Export depends on completed results.",
            ),
            UIControl("exit", label="Exit", level="secondary", rationale="Exit closes the app-level flow."),
        ),
        displays=(
            UIDisplayElement(
                "summary_card",
                "run_summary",
                label="Run summary",
                display_type="status",
                depends_on_states=("result_ready",),
                rationale="The compact summary states the result once.",
            ),
            UIDisplayElement(
                "result_table",
                "result_rows",
                label="Result table",
                display_type="table",
                depends_on_states=("result_ready",),
                rationale="The table shows row-level output, not a duplicate summary.",
            ),
        ),
        transitions=(
            UITransition("click_new_project", "new_project", "launch", "new_project_setup", function_block="StartNewProject", output="new_project_setup", rationale="New project opens the setup state."),
            UITransition("create_project_success", "create_project", "new_project_setup", "loaded", function_block="CreateProject", output="project_created", rationale="Successful creation loads the workbench."),
            UITransition("create_project_failure", "create_project", "new_project_setup", "failed", function_block="CreateProject", output="recoverable_error", rationale="Creation can fail into recoverable state."),
            UITransition("click_load_project", "load_project", "launch", "load_picker", function_block="StartLoadProject", output="load_picker_opened", rationale="Load project opens the file picker state."),
            UITransition("load_project_success", "choose_file", "load_picker", "loaded", function_block="LoadProject", output="project_loaded", rationale="Successful load reaches the workbench."),
            UITransition("load_project_failure", "choose_file", "load_picker", "failed", function_block="LoadProject", output="recoverable_error", rationale="Loading can fail into recoverable state."),
            UITransition("click_run", "run", "loaded", "running", function_block="StartRun", output="run_started", rationale="Run starts the primary processing state."),
            UITransition("click_cancel", "cancel", "running", "loaded", function_block="CancelRun", output="run_cancelled", rationale="Cancel returns to the loaded state."),
            UITransition("click_cancel_new", "cancel", "new_project_setup", "cancelled", function_block="CancelNewProject", output="cancelled", rationale="Cancel leaves new project setup."),
            UITransition("click_cancel_load", "cancel", "load_picker", "cancelled", function_block="CancelLoadProject", output="cancelled", rationale="Cancel leaves load project setup."),
            UITransition("run_success", "run", "running", "result_ready", function_block="FinishRun", output="result_ready", rationale="A successful run exposes results."),
            UITransition("run_failure", "run", "running", "failed", function_block="FailRun", output="recoverable_error", rationale="A failed run enters a recoverable failure state."),
            UITransition("click_retry", "retry", "failed", "running", function_block="RetryRun", output="retry_started", rationale="Retry returns to the running state."),
            UITransition("click_export", "export", "result_ready", "result_ready", function_block="ExportResult", output="exported", rationale="Export is terminal-state output, not a new workflow phase."),
            UITransition("click_exit", "exit", "launch", "exited", function_block="ExitApp", output="exited", rationale="Exit closes the launch flow."),
            UITransition("click_exit_cancelled", "exit", "cancelled", "exited", function_block="ExitApp", output="exited", rationale="Exit closes the app after cancellation."),
        ),
        validation_boundaries=("UI scenario review", "browser state transition test"),
        rationale="The model separates launch, new-project, load-existing, loaded, running, result, failure, cancel, and exit UI states before any layout is derived.",
    )


def journey_coverage() -> UIJourneyCoverage:
    return UIJourneyCoverage(
        "project-workbench-journey-coverage",
        source_interaction_model_id="project-workbench-ui-flow",
        launch_state_id="launch",
        interaction_model_reviewed=True,
        entry_points=(
            UIJourneyEntryPoint("new_project", "new_project", "click_new_project", label="New", source_state_ids=("launch",), rationale="New project is a launch entry."),
            UIJourneyEntryPoint("load_project", "load_project", "click_load_project", label="Load", source_state_ids=("launch",), rationale="Load project is a launch entry."),
            UIJourneyEntryPoint("exit_app", "exit", "click_exit", label="Exit", source_state_ids=("launch",), rationale="Exit is available from launch."),
        ),
        feature_journeys=(
            UIFeatureJourney(
                "new_project",
                label="New project",
                entry_point_ids=("new_project",),
                required_state_ids=("new_project_setup", "loaded", "running"),
                required_event_ids=("click_new_project", "create_project_success", "create_project_failure", "click_run", "run_success", "run_failure"),
                success_terminal_state_ids=("result_ready",),
                failure_state_ids=("failed",),
                recovery_event_ids=("click_retry",),
                cancel_event_ids=("click_cancel_new", "click_cancel"),
                validation_boundaries=("journey scenario review",),
                rationale="A user can create a project, run it, recover from failure, or cancel setup.",
            ),
            UIFeatureJourney(
                "load_project",
                label="Load project",
                entry_point_ids=("load_project",),
                required_state_ids=("load_picker", "loaded", "running"),
                required_event_ids=("click_load_project", "load_project_success", "load_project_failure", "click_run", "run_success", "run_failure"),
                success_terminal_state_ids=("result_ready",),
                failure_state_ids=("failed",),
                recovery_event_ids=("click_retry",),
                cancel_event_ids=("click_cancel_load", "click_cancel"),
                validation_boundaries=("journey scenario review",),
                rationale="A user can load an existing project, run it, recover from failure, or cancel loading.",
            ),
            UIFeatureJourney(
                "exit_app",
                label="Exit app",
                entry_point_ids=("exit_app",),
                required_event_ids=("click_exit",),
                success_terminal_state_ids=("exited",),
                validation_boundaries=("journey scenario review",),
                rationale="A user can leave the app from launch.",
            ),
        ),
        terminal_action_allowances=(
            UITerminalActionAllowance(
                "result_ready",
                "click_export",
                "export",
                rationale="Export is a terminal-state output action.",
            ),
            UITerminalActionAllowance(
                "cancelled",
                "click_exit_cancelled",
                "exit",
                rationale="Exit closes the app after a cancelled setup or load branch.",
            ),
        ),
        residual_blindspots=(
            UIResidualBlindspot(
                "open_recent_project",
                feature_id="open_recent_project",
                reason="Recent-project shell history is outside this starter template.",
                owner="target app integration tests",
                validation_boundaries=("browser or desktop shell test",),
                rationale="The template records the omitted branch instead of claiming full coverage for it.",
            ),
            UIResidualBlindspot(
                "settings_panel",
                feature_id="settings_panel",
                control_ids=("settings",),
                reason="Settings are app-specific configuration details outside this starter template.",
                owner="target app settings journey review",
                validation_boundaries=("settings panel browser test",),
                rationale="The persistent settings button is explicitly bounded instead of becoming a silent no-op.",
            ),
        ),
        validation_boundaries=("journey scenario review", "browser state transition test"),
        rationale="Complete app-level UI coverage is declared from launch through feature terminals.",
    )


def feature_contract(feature_id: str, controls: tuple[str, ...], events: tuple[str, ...]) -> UIFeatureContract:
    return UIFeatureContract(
        feature_id,
        label=feature_id.replace("_", " ").title(),
        journey_ids=(feature_id,),
        required_control_ids=controls,
        required_event_ids=events,
        validation_boundaries=("functional model review",),
        rationale=f"{feature_id} is user-visible functionality that must align with a UI journey and implementation evidence.",
    )


def step(event_id: str, control_id: str, source_state_id: str, target_state_id: str) -> UIImplementationStepEvidence:
    return UIImplementationStepEvidence(
        f"{event_id}_step",
        event_id,
        control_id=control_id,
        source_state_id=source_state_id,
        target_state_id=target_state_id,
        method="browser",
        result="passed",
        evidence_ref=f"evidence://browser/{event_id}",
        observed_state_id=target_state_id,
        rationale=f"{event_id} was clicked or observed in the running UI.",
    )


def journey_run(feature_id: str, *steps: UIImplementationStepEvidence) -> UIImplementationJourneyRun:
    return UIImplementationJourneyRun(
        f"{feature_id}_implementation_run",
        feature_id,
        journey_id=feature_id,
        steps=steps,
        method="browser",
        result="passed",
        evidence_ref=f"evidence://browser/{feature_id}",
        model_revision="template-ui-rev-1",
        validation_boundaries=("browser click-through",),
        rationale=f"{feature_id} was validated from the running UI against the model-derived journey.",
    )


def implementation_validation() -> UIImplementationValidation:
    return UIImplementationValidation(
        "project-workbench-implementation-validation",
        source_feature_model_id="project-workbench-product-flow",
        source_interaction_model_id="project-workbench-ui-flow",
        source_journey_coverage_id="project-workbench-journey-coverage",
        implementation_target="local browser build",
        current_model_revision="template-ui-rev-1",
        feature_contracts=(
            feature_contract(
                "new_project",
                ("new_project", "create_project", "run", "retry"),
                (
                    "click_new_project",
                    "create_project_success",
                    "create_project_failure",
                    "click_run",
                    "run_success",
                    "run_failure",
                    "click_retry",
                    "click_cancel_new",
                    "click_cancel",
                ),
            ),
            feature_contract(
                "load_project",
                ("load_project", "choose_file", "run", "retry"),
                (
                    "click_load_project",
                    "load_project_success",
                    "load_project_failure",
                    "click_run",
                    "run_success",
                    "run_failure",
                    "click_retry",
                    "click_cancel_load",
                    "click_cancel",
                ),
            ),
            feature_contract("exit_app", ("exit",), ("click_exit",)),
        ),
        journey_runs=(
            journey_run(
                "new_project",
                step("click_new_project", "new_project", "launch", "new_project_setup"),
                step("create_project_success", "create_project", "new_project_setup", "loaded"),
                step("create_project_failure", "create_project", "new_project_setup", "failed"),
                step("click_run", "run", "loaded", "running"),
                step("run_success", "run", "running", "result_ready"),
                step("run_failure", "run", "running", "failed"),
                step("click_retry", "retry", "failed", "running"),
                step("click_cancel_new", "cancel", "new_project_setup", "cancelled"),
                step("click_cancel", "cancel", "running", "loaded"),
            ),
            journey_run(
                "load_project",
                step("click_load_project", "load_project", "launch", "load_picker"),
                step("load_project_success", "choose_file", "load_picker", "loaded"),
                step("load_project_failure", "choose_file", "load_picker", "failed"),
                step("click_run", "run", "loaded", "running"),
                step("run_success", "run", "running", "result_ready"),
                step("run_failure", "run", "running", "failed"),
                step("click_retry", "retry", "failed", "running"),
                step("click_cancel_load", "cancel", "load_picker", "cancelled"),
                step("click_cancel", "cancel", "running", "loaded"),
            ),
            journey_run(
                "exit_app",
                step("click_exit", "exit", "launch", "exited"),
            ),
        ),
        pure_ui_control_ids=("cancel", "export"),
        pure_ui_event_ids=("click_export", "click_exit_cancelled"),
        implementation_blindspots=(
            UIImplementationBlindspot(
                "settings_panel_implementation",
                feature_id="settings_panel",
                control_ids=("settings",),
                reason="Settings panel contents are app-specific and not part of this starter implementation.",
                owner="target app settings validation",
                validation_boundaries=("settings browser check",),
                rationale="The persistent settings control is bounded instead of silently claimed.",
            ),
            UIImplementationBlindspot(
                "open_recent_project_implementation",
                feature_id="open_recent_project",
                reason="Recent-project shell history is outside this starter template.",
                owner="target app integration tests",
                validation_boundaries=("browser or desktop shell test",),
                rationale="The omitted branch remains visible for downstream validation.",
            ),
        ),
        journey_coverage_reviewed=True,
        validation_boundaries=("browser click-through", "manual fallback for native dialogs"),
        rationale="Implemented UI evidence is generated from feature contracts and the reviewed journey coverage.",
    )


def structure_derivation() -> UIStructureDerivation:
    return UIStructureDerivation(
        "project-workbench-ui-structure",
        source_interaction_model_id="project-workbench-ui-flow",
        parent_surface_id="project-workbench",
        interaction_model_reviewed=True,
        target_regions=(
            UIRegionRecommendation(
                "top-toolbar",
                level="global",
                placement="top-toolbar",
                owns_controls=("settings",),
                stable_across_states=True,
                rationale="Global settings live in a first-level stable toolbar.",
            ),
            UIRegionRecommendation(
                "primary-workspace",
                level="primary",
                placement="main",
                owns_states=("launch", "new_project_setup", "load_picker", "loaded", "running", "result_ready", "cancelled", "exited"),
                owns_controls=("new_project", "load_project", "create_project", "choose_file", "run", "export", "exit"),
                owns_displays=("summary_card", "result_table"),
                owns_events=("click_new_project", "create_project_success", "click_load_project", "load_project_success", "click_run", "run_success", "click_export", "click_exit", "click_exit_cancelled"),
                stable_across_states=True,
                rationale="Main workflow actions live in the primary workspace.",
            ),
            UIRegionRecommendation(
                "failure-inspector",
                level="secondary",
                placement="right-inspector",
                parent_region_id="primary-workspace",
                owns_states=("failed",),
                owns_controls=("retry",),
                owns_events=("run_failure", "click_retry"),
                rationale="Recoverable failure is a child inspector of the main workflow.",
            ),
            UIRegionRecommendation(
                "cancel-overlay",
                level="overlay",
                placement="modal",
                parent_region_id="primary-workspace",
                owns_controls=("cancel",),
                owns_events=("click_cancel", "click_cancel_new", "click_cancel_load"),
                rationale="Cancel temporarily scopes the running parent flow.",
            ),
        ),
        state_region_map=(
            ("launch", "primary-workspace"),
            ("new_project_setup", "primary-workspace"),
            ("load_picker", "primary-workspace"),
            ("loaded", "primary-workspace"),
            ("running", "primary-workspace"),
            ("result_ready", "primary-workspace"),
            ("failed", "failure-inspector"),
            ("cancelled", "primary-workspace"),
            ("exited", "primary-workspace"),
        ),
        control_region_map=(
            ("settings", "top-toolbar"),
            ("new_project", "primary-workspace"),
            ("load_project", "primary-workspace"),
            ("create_project", "primary-workspace"),
            ("choose_file", "primary-workspace"),
            ("run", "primary-workspace"),
            ("export", "primary-workspace"),
            ("exit", "primary-workspace"),
            ("retry", "failure-inspector"),
            ("cancel", "cancel-overlay"),
        ),
        display_region_map=(
            ("summary_card", "primary-workspace"),
            ("result_table", "primary-workspace"),
        ),
        event_region_map=(
            ("click_new_project", "primary-workspace"),
            ("create_project_success", "primary-workspace"),
            ("create_project_failure", "failure-inspector"),
            ("click_load_project", "primary-workspace"),
            ("load_project_success", "primary-workspace"),
            ("load_project_failure", "failure-inspector"),
            ("click_run", "primary-workspace"),
            ("run_success", "primary-workspace"),
            ("run_failure", "failure-inspector"),
            ("click_retry", "failure-inspector"),
            ("click_cancel", "cancel-overlay"),
            ("click_cancel_new", "cancel-overlay"),
            ("click_cancel_load", "cancel-overlay"),
            ("click_export", "primary-workspace"),
            ("click_exit", "primary-workspace"),
            ("click_exit_cancelled", "primary-workspace"),
        ),
        hierarchy_edges=(("primary-workspace", "failure-inspector"), ("primary-workspace", "cancel-overlay")),
        persistent_control_ids=("settings",),
        contextual_control_ids=("retry", "cancel"),
        overlay_region_ids=("cancel-overlay",),
        stable_region_ids=("top-toolbar", "primary-workspace"),
        validation_boundaries=("browser state transition test", "design implementation review"),
        rationale="First-level persistent controls stay in the toolbar; phase controls and overlays follow the UI model.",
    )


def typography_token(token_id: str, level: int, roles: tuple[str, ...]) -> UITypographyToken:
    return UITypographyToken(
        token_id,
        hierarchy_level=level,
        text_roles=roles,
        scale=f"level-{level}",
        weight="regular" if level >= 4 else "semibold",
        color_role="default",
        rationale=f"{token_id} is reserved for {roles}.",
    )


def text_hierarchy() -> UITextHierarchyBlueprint:
    return UITextHierarchyBlueprint(
        "project-workbench-text-hierarchy",
        source_interaction_model_id="project-workbench-ui-flow",
        source_structure_derivation_id="project-workbench-ui-structure",
        parent_surface_id="project-workbench",
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
            UITextElement(
                "surface_title",
                "page_title",
                "page-title",
                "surface_title",
                label="Project Workbench",
                region_id="primary-workspace",
                rationale="The parent surface title names the full workflow.",
            ),
            UITextElement(
                "workspace_title",
                "section_title",
                "section-title",
                "workflow_area",
                label="Run workspace",
                region_id="primary-workspace",
                parent_text_id="surface_title",
                rationale="The primary region gets one section title below the surface title.",
            ),
            UITextElement(
                "settings_label",
                "button_label",
                "control-label",
                "settings_action",
                label="Settings",
                region_id="top-toolbar",
                source_control_id="settings",
                rationale="The global settings control uses the shared control-label token.",
            ),
            UITextElement("new_project_label", "button_label", "control-label", "new_project_action", label="New", region_id="primary-workspace", source_control_id="new_project", rationale="New is an app-entry action label, not a heading."),
            UITextElement("load_project_label", "button_label", "control-label", "load_project_action", label="Load", region_id="primary-workspace", source_control_id="load_project", rationale="Load is an app-entry action label, not a heading."),
            UITextElement("run_label", "button_label", "control-label", "run_action", label="Run", region_id="primary-workspace", source_control_id="run", rationale="Run is an action label, not a heading."),
            UITextElement("export_label", "button_label", "control-label", "export_action", label="Export", region_id="primary-workspace", source_control_id="export", rationale="Export is an action label, not a heading."),
            UITextElement(
                "results_title",
                "panel_title",
                "panel-title",
                "results_panel",
                label="Results",
                region_id="primary-workspace",
                parent_text_id="workspace_title",
                source_state_ids=("result_ready",),
                rationale="The result panel is subordinate to the primary workspace.",
            ),
            UITextElement(
                "summary_value",
                "status_text",
                "status-text",
                "run_summary",
                label="Run completed",
                region_id="primary-workspace",
                source_display_id="summary_card",
                visible_in_states=("result_ready",),
                rationale="The summary card text uses a status role tied to the modeled display.",
            ),
            UITextElement(
                "result_table_caption",
                "caption",
                "caption-text",
                "result_rows",
                label="Result rows",
                region_id="primary-workspace",
                source_display_id="result_table",
                visible_in_states=("result_ready",),
                rationale="The table caption is less prominent than the result panel title.",
            ),
            UITextElement(
                "failure_title",
                "panel_title",
                "panel-title",
                "failure_panel",
                label="Recovery",
                region_id="failure-inspector",
                parent_text_id="workspace_title",
                source_state_ids=("failed",),
                rationale="The failure inspector title is a child of the main workflow section.",
            ),
            UITextElement(
                "retry_label",
                "button_label",
                "control-label",
                "retry_action",
                label="Retry",
                region_id="failure-inspector",
                source_control_id="retry",
                visible_in_states=("failed",),
                rationale="Retry is a recovery action label scoped to the failure inspector.",
            ),
            UITextElement(
                "cancel_label",
                "button_label",
                "control-label",
                "cancel_action",
                label="Cancel",
                region_id="cancel-overlay",
                source_control_id="cancel",
                visible_in_states=("running",),
                rationale="Cancel is an overlay action label, not a panel heading.",
            ),
        ),
        validation_boundaries=("design token review", "browser text hierarchy review"),
        rationale="Text roles and typography tokens are derived from source regions, controls, displays, and states.",
    )


def broken_interaction_model() -> UIInteractionModel:
    return UIInteractionModel(
        "broken-ui-flow",
        initial_state_id="empty",
        states=(UIStateNode("empty"), UIStateNode("failed", failure=True)),
        controls=(UIControl("delete", label="Delete", level="primary", destructive=True),),
        displays=(
            UIDisplayElement("chart", "same_summary", display_type="chart"),
            UIDisplayElement("text", "same_summary", display_type="text"),
        ),
        transitions=(UITransition("click_delete", "delete", "empty", "failed"),),
    )


def broken_structure_derivation() -> UIStructureDerivation:
    return UIStructureDerivation(
        "broken-ui-structure",
        source_interaction_model_id="project-workbench-ui-flow",
        parent_surface_id="project-workbench",
        target_regions=(UIRegionRecommendation("main"),),
        state_region_map=(("launch", "main"),),
        control_region_map=(("settings", "main"),),
        display_region_map=(("chart", "main"), ("text", "main")),
    )


def broken_journey_coverage() -> UIJourneyCoverage:
    return UIJourneyCoverage(
        "broken-project-workbench-journey",
        source_interaction_model_id="project-workbench-ui-flow",
        launch_state_id="launch",
        interaction_model_reviewed=True,
        entry_points=(
            UIJourneyEntryPoint("new_project", "new_project", "click_new_project", source_state_ids=("launch",), rationale="New project is modeled."),
        ),
        feature_journeys=(
            UIFeatureJourney(
                "load_project",
                entry_point_ids=("load_project",),
                required_state_ids=("load_picker",),
                required_event_ids=("missing_load_event",),
                success_terminal_state_ids=(),
                validation_boundaries=("journey review",),
                rationale="Broken because the load entry and terminal are missing.",
            ),
        ),
        residual_blindspots=(
            UIResidualBlindspot("open_recent_project", reason="deferred", rationale="Broken because no validation boundary is named."),
        ),
        validation_boundaries=("journey review",),
        rationale="Broken journey coverage demonstrates missing app-level branches.",
    )


def broken_implementation_validation() -> UIImplementationValidation:
    return UIImplementationValidation(
        "broken-project-workbench-implementation",
        source_feature_model_id="project-workbench-product-flow",
        source_interaction_model_id="project-workbench-ui-flow",
        source_journey_coverage_id="project-workbench-journey-coverage",
        implementation_target="local browser build",
        current_model_revision="template-ui-rev-1",
        feature_contracts=(
            feature_contract(
                "new_project",
                ("new_project", "create_project"),
                ("click_new_project", "create_project_success", "create_project_failure", "click_retry"),
            ),
            feature_contract(
                "load_project",
                ("load_project", "choose_file"),
                ("click_load_project", "load_project_success", "load_project_failure", "click_retry"),
            ),
        ),
        journey_runs=(
            journey_run(
                "new_project",
                step("click_new_project", "new_project", "launch", "new_project_setup"),
                step("create_project_success", "create_project", "new_project_setup", "loaded"),
            ),
        ),
        pure_ui_control_ids=("cancel",),
        journey_coverage_reviewed=True,
        validation_boundaries=("browser click-through",),
        rationale="Broken implementation validation omits load-project and failure/recovery evidence.",
    )


def broken_text_hierarchy() -> UITextHierarchyBlueprint:
    return UITextHierarchyBlueprint(
        "broken-text-hierarchy",
        source_interaction_model_id="project-workbench-ui-flow",
        source_structure_derivation_id="project-workbench-ui-structure",
        parent_surface_id="project-workbench",
        typography_tokens=(
            typography_token("section-title", 2, ("section_title",)),
            typography_token("hero-button", 1, ("button_label",)),
        ),
        text_elements=(
            UITextElement(
                "primary_section",
                "section_title",
                "section-title",
                "run_summary",
                label="Summary",
                region_id="primary-workspace",
                visible_in_states=("result_ready",),
                rationale="First duplicate summary heading.",
            ),
            UITextElement(
                "duplicate_summary",
                "section_title",
                "section-title",
                "run_summary",
                label="Summary again",
                region_id="primary-workspace",
                visible_in_states=("result_ready",),
                rationale="Second duplicate summary heading without a redundancy reason.",
            ),
            UITextElement(
                "import_label",
                "button_label",
                "hero-button",
                "new_project_action",
                label="New",
                region_id="primary-workspace",
                source_control_id="new_project",
                rationale="Broken because a button label uses a top-level token.",
            ),
        ),
        validation_boundaries=("text hierarchy review",),
        rationale="This intentionally broken blueprint demonstrates duplicate text and over-prominent action labels.",
    )


def run_checks():
    model = interaction_model()
    structure = structure_derivation()
    model_report = review_ui_interaction_model(model)
    journey_report = review_ui_journey_coverage(journey_coverage(), interaction_model=model)
    implementation_report = review_ui_implementation_validation(
        implementation_validation(),
        interaction_model=model,
        journey_coverage=journey_coverage(),
    )
    structure_report = review_ui_structure_derivation(structure, interaction_model=model)
    text_report = review_ui_text_hierarchy(
        text_hierarchy(),
        interaction_model=model,
        structure_derivation=structure,
    )
    broken_model_report = review_ui_interaction_model(broken_interaction_model())
    broken_journey_report = review_ui_journey_coverage(broken_journey_coverage(), interaction_model=model)
    broken_implementation_report = review_ui_implementation_validation(
        broken_implementation_validation(),
        interaction_model=model,
        journey_coverage=journey_coverage(),
    )
    broken_structure_report = review_ui_structure_derivation(
        broken_structure_derivation(),
        interaction_model=model,
    )
    broken_text_report = review_ui_text_hierarchy(
        broken_text_hierarchy(),
        interaction_model=model,
        structure_derivation=structure,
    )
    return (
        model_report,
        journey_report,
        implementation_report,
        structure_report,
        text_report,
        broken_model_report,
        broken_journey_report,
        broken_implementation_report,
        broken_structure_report,
        broken_text_report,
    )
'''

UI_FLOW_STRUCTURE_RUN_CHECKS_TEMPLATE = '''"""Run the UI Flow Structure template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    (
        model_report,
        journey_report,
        implementation_report,
        structure_report,
        text_report,
        broken_model,
        broken_journey,
        broken_implementation,
        broken_structure,
        broken_text,
    ) = run_checks()
    print(model_report.format_text())
    print()
    print(journey_report.format_text())
    print()
    print(implementation_report.format_text())
    print()
    print(structure_report.format_text())
    print()
    print(text_report.format_text())
    print()
    print(broken_model.format_text(max_findings=5))
    print()
    print(broken_journey.format_text(max_findings=5))
    print()
    print(broken_implementation.format_text(max_findings=25))
    print()
    print(broken_structure.format_text(max_findings=5))
    print()
    print(broken_text.format_text(max_findings=5))
    return 0 if (
        model_report.ok
        and journey_report.ok
        and implementation_report.ok
        and structure_report.ok
        and text_report.ok
        and not broken_model.ok
        and not broken_journey.ok
        and not broken_implementation.ok
        and not broken_structure.ok
        and not broken_text.ok
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

UI_FLOW_STRUCTURE_NOTES_TEMPLATE = """# FlowGuard UI Flow Structure Notes

Use this scaffold before visual design or frontend implementation when the UI
itself needs a model-first interaction flow.

## What This Route Produces

- a UI interaction model: initial state, controls, events, state nodes,
  transitions, failure and recovery states, terminal states, and availability;
- app-level journey coverage when the route claims complete UI coverage:
  launch state, entry points, feature journeys, terminal actions,
  failure/recovery handling, reachable visible/enabled control branches, and
  residual blindspots;
- a structure derivation from that model: parent/child UI nodes, first-level
  persistent menus, second-level contextual regions, third-level local actions,
  overlays, stable layout positions, and validation boundaries;
- a text hierarchy blueprint from that reviewed structure: page titles,
  section titles, panel titles, labels, button text, status text, captions,
  semantic text keys, typography tokens, parent/child text priority, and
  redundancy rationale;
- implementation validation when the route claims a running UI is implemented
  or complete: user-visible feature contracts, mapped journeys,
  browser/desktop/manual journey runs, step evidence, model revision, pure UI
  actions, and residual implementation blindspots;
- review findings when a control has no modeled event, a failure state has no
  recovery path, a destructive control is too prominent, or a persistent
  control is not assigned to a stable global region;
- journey coverage findings when a launch entry is missing, a reachable
  button/control has no modeled event, a modeled event is outside all journeys,
  a required feature path is unreachable, a terminal state has unclassified
  outgoing actions, or a residual blindspot lacks validation;
- implementation validation findings when a feature has no UI path, a visible
  control has no functional owner, a journey lacks click-through evidence,
  branch evidence is missing, or the recorded evidence is stale;
- redundancy findings when the same page/state shows the same semantic
  information twice or exposes multiple same-level controls for one function
  without an explicit rationale;
- text hierarchy findings when a button label uses a heading token, a child
  title is not visually subordinate to its parent title, or the same semantic
  text is repeated in one region and state without a modeled reason.

UI Flow Structure does not choose final brand styling or implement frontend
code. Use the derived structure and text hierarchy contract as input to Figma,
frontend implementation, browser checks, and design implementation review; feed
real click-through results back as implementation validation before claiming
the running UI is complete.
"""

__all__ = [
    'UI_FLOW_STRUCTURE_MODEL_TEMPLATE',
    'UI_FLOW_STRUCTURE_RUN_CHECKS_TEMPLATE',
    'UI_FLOW_STRUCTURE_NOTES_TEMPLATE',
]
