# UI Flow Structure

UI Flow Structure is FlowGuard's helper layer for model-first interface
planning. It first models the UI's interaction behavior, then reviews
the user-visible surface, then reviews launch-to-terminal journey coverage when
complete app-level UI coverage is claimed, then derives the UI structure from
that model, then derives a UI text hierarchy blueprint from the reviewed
structure. When someone claims the running UI has been implemented or is
complete, implementation validation aligns user-visible feature contracts, the
reviewed UI journey coverage, and evidence kinds such as screenshot, browser
click-through, DOM text, geometry, accessibility/ARIA, runtime trace, test
result, or manual observation. A complete runnable UI claim must account for
every reachable enabled actionable control: click it through, classify it as a
pure UI action, or record a scoped blindspot with owner and validation
boundary.

This route is for workflow-heavy interfaces where button placement, menu
levels, panels, overlays, persistent controls, and state-dependent actions need
to follow the product behavior instead of being placed arbitrarily.
It also reviews information and control redundancy: the same semantic
information or same-level function can be repeated only when the model records
why the repetition is intentional.
The final blueprint stage keeps headings, labels, action text, status
messages, helper text, and error/recovery copy slots tied to modeled UI states
and owned regions before visual design or frontend implementation begins.
Visible-surface review keeps controls, status text, helper copy, placeholders,
metadata, and disabled reasons owned by user-facing state or control purpose.

## Use Cases

Use it when:

- a UI has meaningful states such as empty, loaded, running, failed, result
  ready, review, publish, or archived;
- buttons, menu items, inputs, panels, dialogs, drawers, or inspectors appear,
  disappear, enable, disable, block, recover, retry, cancel, or depend on
  another workflow stage;
- the agent needs to decide which functions are global, parent-level,
  child-level, contextual, local, destructive, terminal, or recovery actions;
- a design needs first-level persistent menus, second-level contextual regions,
  third-level local controls, overlay hierarchy, stable toolbar placement, or
  parent/child UI topology before visual styling;
- a page may show the same information through a chart, card, table, text, or
  image, and repeated display needs to be checked for value rather than visual
  clutter;
- two buttons or menu items appear to trigger the same function at the same
  hierarchy level and need an explicit reason to remain separate;
- helper copy, placeholders, metadata, status text, or disabled reasons need to
  be checked for user-facing purpose instead of leaking implementation terms;
- implemented UI claims need to name what kind of evidence supports the claim,
  including screenshots when screenshots are the right evidence;
- layout or responsiveness confidence depends on overflow, overlap, viewport
  bounds, focus/keyboard reachability, scroll ownership, immediate feedback, or
  stale-result guards;
- headings, labels, action text, status messages, helper text, empty/error
  states, validation text, or recovery copy slots need to follow the modeled
  interaction and region hierarchy instead of being invented as late visual
  copy.
- an agent or design artifact claims the whole app UI is covered from the first
  launch screen through entry branches such as new project, load existing
  project, cancel, recover, export, and exit.
- an agent claims the implemented or runnable UI has actually been opened and
  verified through browser, desktop, or manual click-through evidence.
- a file picker, save dialog, permission prompt, native dialog, or manual-only
  UI branch needs structured event/result evidence instead of a prose note.

Skip it for tiny visual-only edits with no behavior, state, navigation, or
control-availability impact.

## Public API

The UI interaction model objects are:

- `UIControl`: one button, input, menu item, command, status control, or other
  visible/invokable UI control. It can carry `function_key`,
  `duplicate_group`, and `redundancy_rationale` when controls intentionally
  overlap.
- `UIDisplayElement`: one modeled information item, such as a text summary,
  chart, metric card, table, status line, image, or diagram. It carries a
  `semantic_key` so FlowGuard can detect repeated information.
- `UIStateNode`: one abstract UI state with visible, enabled, disabled, hidden,
  recovery, terminal, failure-state, and visible-display information.
- `UITransition`: one modeled event that moves from a source UI state to a
  target UI state.
- `UIInteractionModel`: the complete UI flow model.
- `UIInteractionModelReport`: structured review output.
- `review_ui_interaction_model(model)`: checks whether the UI flow model is
  complete enough to derive structure.
- `ui_interaction_model_to_transition_coverage(model)`: projects modeled UI
  transitions into transition coverage cells that Model-Test Alignment and
  TestMesh evidence can target.

The app-level journey coverage objects are:

- `UIJourneyEntryPoint`: one launch-available app entry point with its control,
  event, source states, and rationale.
- `UIFeatureJourney`: one declared feature path with entry points, required
  states/events, success terminals, failure states, recovery/cancel/exit
  handling, validation, and rationale.
- `UITerminalActionAllowance`: one allowed outgoing action from a terminal
  state, such as export, restart, close, recovery, cancel, or exit.
- `UIBlindspot`: one deliberately scoped or unverified UI branch with feature,
  control, or event scope plus a reason, owner, validation boundary, and
  rationale.
- `UIJourneyCoverage`: the complete app-level launch-to-terminal coverage
  inventory for a source interaction model.
- `UIJourneyCoverageReport`: structured review output.
- `review_ui_journey_coverage(coverage, interaction_model=...)`: checks whether
  app-level entry points and feature journeys are reachable from launch and
  terminate or recover within the declared boundary.

The implementation validation objects are:

- `UIFeatureContract`: one user-visible feature from the functional model that
  should map to UI journeys, controls, and events.
- `UIImplementationStepEvidence`: one browser, desktop, or manual observation
  of a modeled control/event/state transition. Use one step row for each
  reachable enabled control that is part of the implementation claim.
- `UIImplementationJourneyRun`: one real UI run of a modeled feature journey,
  with method, result, evidence reference, and model revision.
- `UIBlindspot`: the same canonical blindspot row is used for intentionally
  unverified implementation branches.
- `UIImplementationValidation`: the complete implementation evidence boundary
  connecting feature contracts, journey coverage, real UI runs, pure UI
  actions, model revision, and blindspots.
- `UIImplementationValidationReport`: structured review output.
- `review_ui_implementation_validation(validation, interaction_model=..., journey_coverage=...)`:
  checks whether real UI evidence covers the feature and journey obligations
  before an implemented/runnable UI completion claim is accepted.

The visible-surface objects are:

- `UIVisibleSurfaceItem`: one user-facing item, such as control text, helper
  copy, placeholder text, metadata, status text, or disabled reason.
- `UIVisibleSurface`: the complete visible-surface inventory for a UI boundary.
- `UIVisibleSurfaceReport`: structured review output.
- `review_ui_visible_surface(surface, interaction_model=...)`: checks that
  visible items have an owner, user-facing purpose, disabled reasons where
  needed, no unhandled internal terminology, and no competing primary state
  messages.

The render/evidence-kind objects are:

- `UIRenderEvidence`: one render or implementation evidence row with an
  evidence kind such as screenshot, browser click-through, DOM text, computed
  style, geometry, accessibility/ARIA, runtime trace, log, test result, or
  manual observation.
- `UIRenderEvidenceSet`: the render evidence boundary for a runnable UI claim.
- `UIRenderEvidenceReport`: structured review output.
- `review_ui_render_evidence(evidence_set, interaction_model=...)`: checks
  evidence kind, target, reference, result, source model, and revision freshness.

The geometry and responsiveness objects are:

- `UIGeometryLayoutEvidence`: one universal layout evidence row for overflow,
  overlap, bounds, focus reachability, keyboard reachability, and scroll owner.
- `UIGeometryLayoutEvidenceSet`: the geometry/layout evidence boundary.
- `UIGeometryLayoutEvidenceReport`: structured review output.
- `review_ui_geometry_layout_evidence(geometry, interaction_model=...)`: checks
  universal layout evidence for the declared target.
- `UIHotPathAction`, `UIColdPathWork`, and `UIStableRegionRule`: hot feedback,
  deferred work, and stable-region preservation rows.
- `UIResponsivenessContract`: the hot/cold path responsiveness boundary.
- `UIResponsivenessContractReport`: structured review output.
- `review_ui_responsiveness_contract(contract, interaction_model=...)`: checks
  immediate feedback, stale-result protection, cancellation/coalescing, and
  stable-region preservation.

The structure derivation objects are:

- `UIRegionRecommendation`: one menu level, screen region, panel, overlay, or
  child UI boundary with placement and ownership.
- `UIStructureDerivation`: the complete structure derivation, including source
  model id, parent surface, state/control/event owner maps, hierarchy edges,
  display owner maps, persistent controls, contextual controls, overlay regions,
  stable regions, validation boundaries, and rationale.
- `UIStructureDerivationReport`: structured review output.
- `review_ui_structure_derivation(derivation, interaction_model=...)`: checks
  whether the UI structure follows from a reviewed UI interaction model.

The text hierarchy blueprint objects are:

- `UITypographyToken`: one semantic text style token with hierarchy level,
  allowed text roles, scale, weight, color role, and rationale. These are
  semantic tokens, not final brand font choices.
- `UITextElement`: one modeled text slot with role, token, semantic key,
  region, parent text, source state/control/display, state visibility, and
  redundancy rationale.
- `UITextHierarchyBlueprint`: the complete text hierarchy derivation, including
  source interaction model id, source structure derivation id, parent surface,
  typography tokens, text elements, validation boundaries, and rationale.
- `UITextHierarchyReport`: structured review output.
- `review_ui_text_hierarchy(blueprint, interaction_model=..., structure_derivation=...)`:
  checks whether text roles and tokens follow the reviewed UI model and
  structure.

## UI Flow Workflow

```text
product/workflow intent
-> UI interaction model
-> review UI controls, states, transitions, availability, failures
-> visible surface review
-> review helper copy, status text, placeholders, metadata, disabled reasons
-> UI journey coverage when claiming complete app-level UI coverage
-> review launch entry points, feature paths, terminal/recovery behavior, blindspots
-> UI structure derivation
-> review regions, menu levels, displays, overlays, stable placement, hierarchy
-> UI text hierarchy blueprint
-> review headings, labels, action text, status/helper/error/recovery slots
-> render evidence kinds, geometry, and responsiveness when claimed
-> review screenshot/DOM/click/geometry/accessibility/runtime/test/manual evidence, layout, hot/cold paths
-> transition coverage matrix when claiming model-to-code-to-test coverage
-> project UI transitions to Model-Test Alignment obligations, code contracts, or TestMesh cells
-> UI implementation validation when claiming the running UI is complete
-> review feature contracts, every reachable enabled control, real journey runs, step evidence, model freshness, blindspots
-> handoff to Figma, frontend implementation, browser checks, copy/design, or design review
```

The first stage models the UI as:

```text
UI event x UI state -> Set(UI output x UI state)
```

The visible-surface stage checks:

- controls, helper copy, status text, placeholders, metadata, and disabled
  reasons have an owner and a user-facing purpose;
- disabled controls explain availability in terms the user can understand;
- placeholder text is guidance, not proof that a feature is complete;
- implementation-facing terms such as mock, backend, hydration, debug route,
  dataset id, or render strategy do not leak to users without a clear reason;
- one state does not show multiple competing primary empty/loading/pending/error
  or success messages.

The journey stage is optional for local/component-only UI work, but required for
complete app-level UI claims. It checks:

- the launch state exists and is registered;
- top-level entry points such as new project, load existing project, settings,
  cancel, export, and exit are declared when they are in scope;
- each declared feature journey names required states/events and at least one
  reachable success terminal;
- each reachable visible/enabled actionable control has a modeled event or an
  explicit residual blindspot;
- each reachable modeled event is consumed by a feature journey, terminal
  allowance, entry point, or residual blindspot;
- recoverable failures have named recovery, cancel, exit, or terminal handling;
- terminal states do not expose unclassified forward-only actions;
- residual blindspots name their reason, owner, and validation boundary.

The structure stage derives placement and hierarchy from that reviewed flow:

- first-level persistent controls stay in stable global areas such as top
  toolbars, app shells, menu bars, or primary navigation;
- second-level contextual controls live in the owning parent workflow area,
  inspector, side panel, or phase region;
- third-level local controls stay near the local data, row, item, or child
  state they affect;
- blocking or parent-scoped interactions become modal, drawer, popover,
  inspector, or inline child regions;
- destructive controls are structurally separated from ordinary primary
  progression.

The text hierarchy stage derives text ownership and priority from the reviewed
structure:

- page or surface titles name the parent workflow or surface;
- region headings name the state group, display group, or child workflow owned
  by that region;
- primary, secondary, contextual, local, destructive, recovery, cancel, retry,
  export, and terminal action labels map to modeled control events;
- status, progress, success, warning, failure, terminal, helper, validation,
  empty-state, confirmation, diagnostic, and recovery text slots map to the
  UI state, control, display, region, or overlay that owns them;
- repeated text intent needs a rationale when it appears in more than one
  region or hierarchy level.

The redundancy review is intentionally conservative:

- two display elements with the same `semantic_key` in one state need a
  `redundancy_rationale`;
- two same-level controls that trigger the same modeled function in one state
  need a `redundancy_rationale` or shared duplicate group;
- repeated global navigation across states is acceptable when it is modeled as
  persistent and stable;
- summary plus detail can be acceptable when the model explains the difference
  between the summary and the detail.

The text blueprint is intentionally not final marketing copy. It should tell a
frontend, Figma, copy, or design-review workflow which text slots exist, what
each slot must communicate, which state or region owns it, and which labels
must remain stable across states.

The blueprint is also not a command to create one visual font size for every
semantic hierarchy level. During visual handoff, related text jobs should be
grouped into reusable treatments where possible. A visual difference in size,
weight, color role, spacing, or placement should have a clear job, such as
primary focus, region scanning, local control, warning, helper text, quiet
metadata, or intentional brand expression. Excessive one-off text treatments
are a design smell to review and consolidate, not a fixed numeric failure.

The evidence and implementation stages are only for implemented/runnable UI
claims. They check:

- every user-visible feature contract has a UI journey, entry point, event, or
  implementation blindspot;
- every reachable actionable control/event has a feature owner, pure UI
  classification, real run evidence, or blindspot;
- every modeled feature journey has passed browser, desktop, or manual
  click-through evidence;
- success evidence also covers modeled failure, recovery, cancel, and exit
  branches;
- each run records the model or implementation revision it validates;
- each render evidence row declares an evidence kind, including screenshot when
  screenshot evidence is used;
- geometry/layout claims have current evidence for overflow, overlap, bounds,
  focus/keyboard reachability, and scroll ownership;
- responsiveness claims have immediate hot-path feedback and stale-result
  protection for deferred work;
- skipped or hard-to-automate branches are recorded as implementation
  blindspots with scope, owner, and validation boundary.

Before a broad UI model-to-code-to-test coverage claim, project the reviewed
`UIInteractionModel.transitions` with
`ui_interaction_model_to_transition_coverage(...)`. Each transition should name
the handler/function block plus a code contract or runtime node id when broad
coverage is claimed. Each generated cell gives browser, desktop, or manual
evidence a stable target such as `loaded.click_run->running`. Small UI matrices
can be reviewed directly by Model-Test Alignment with projected obligations and
code contracts; larger browser or release-only matrices should route the
required cell ids to TestMesh while preserving those targets.

## Example

```python
from flowguard import (
    UIControl,
    UIDisplayElement,
    UIBlindspot,
    UIFeatureContract,
    UIFeatureJourney,
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


model = UIInteractionModel(
    "import-run-ui-flow",
    initial_state_id="empty",
    states=(
        UIStateNode(
            "empty",
            enabled_controls=("import", "settings"),
            disabled_controls=("run", "export"),
            rationale="The first screen starts with import and global settings.",
        ),
        UIStateNode(
            "result_ready",
            visible_displays=("result_summary",),
            enabled_controls=("export", "settings"),
            terminal=True,
            rationale="Results can be exported after the run completes.",
        ),
    ),
    controls=(
        UIControl("settings", level="global", persistent=True, rationale="Always available."),
        UIControl("import", level="primary", rationale="Starts the flow."),
        UIControl("export", level="secondary", depends_on_states=("result_ready",), rationale="Needs results."),
    ),
    displays=(
        UIDisplayElement(
            "result_summary",
            "run_summary",
            display_type="status",
            depends_on_states=("result_ready",),
            rationale="The result summary appears once on the result state.",
        ),
    ),
    transitions=(
        UITransition("click_import", "import", "empty", "result_ready", rationale="Demo import reaches results."),
        UITransition("click_export", "export", "result_ready", "result_ready", rationale="Export is terminal output."),
    ),
    validation_boundaries=("UI scenario review",),
    rationale="The UI model is explicit before structure is derived.",
)

model_report = review_ui_interaction_model(model)

coverage = UIJourneyCoverage(
    "import-run-journey-coverage",
    source_interaction_model_id="import-run-ui-flow",
    launch_state_id="empty",
    interaction_model_reviewed=model_report.ok,
    entry_points=(
        UIJourneyEntryPoint(
            "import",
            "import",
            "click_import",
            source_state_ids=("empty",),
            rationale="Import is the launch entry in this local example.",
        ),
    ),
    feature_journeys=(
        UIFeatureJourney(
            "import_run_export",
            entry_point_ids=("import",),
            required_state_ids=("result_ready",),
            required_event_ids=("click_import", "click_export"),
            success_terminal_state_ids=("result_ready",),
            validation_boundaries=("UI scenario review",),
            rationale="The local example reaches a result terminal and supports export.",
        ),
    ),
    terminal_action_allowances=(
        UITerminalActionAllowance(
            "result_ready",
            "click_export",
            "export",
            rationale="Export is a terminal-state output action.",
        ),
    ),
    residual_blindspots=(
        UIBlindspot(
            "load_existing_project",
            feature_id="load_existing_project",
            reason="The short example only demonstrates import.",
            owner="target app journey coverage",
            validation_boundaries=("full app journey review",),
            rationale="The omitted branch is visible instead of silently claimed.",
        ),
        UIBlindspot(
            "settings_panel",
            feature_id="settings_panel",
            control_ids=("settings",),
            reason="Settings are outside the short local example.",
            owner="settings journey review",
            validation_boundaries=("settings UI scenario review",),
            rationale="The visible settings control is explicitly bounded instead of becoming a silent no-op.",
        ),
    ),
    validation_boundaries=("UI scenario review",),
    rationale="App-level claims need declared journey coverage; this example records its boundary.",
)

journey_report = review_ui_journey_coverage(coverage, interaction_model=model)

implementation_validation = UIImplementationValidation(
    "import-run-implementation-validation",
    source_feature_model_id="import-run-product-flow",
    source_interaction_model_id="import-run-ui-flow",
    source_journey_coverage_id="import-run-journey-coverage",
    implementation_target="local browser build",
    current_model_revision="example-ui-rev-1",
    feature_contracts=(
        UIFeatureContract(
            "import_run_export",
            journey_ids=("import_run_export",),
            required_control_ids=("import", "export"),
            required_event_ids=("click_import", "click_export"),
            validation_boundaries=("functional model review",),
            rationale="The user-visible import/export feature must be reachable in UI.",
        ),
    ),
    journey_runs=(
        UIImplementationJourneyRun(
            "import_run_export_browser",
            "import_run_export",
            journey_id="import_run_export",
            method="browser",
            result="passed",
            evidence_ref="evidence://browser/import-run-export",
            model_revision="example-ui-rev-1",
            validation_boundaries=("browser click-through",),
            rationale="The feature was clicked through in the running UI.",
            steps=(
                UIImplementationStepEvidence(
                    "click_import_step",
                    "click_import",
                    control_id="import",
                    source_state_id="empty",
                    target_state_id="result_ready",
                    method="browser",
                    result="passed",
                    evidence_ref="evidence://browser/click-import",
                    observed_state_id="result_ready",
                ),
                UIImplementationStepEvidence(
                    "click_export_step",
                    "click_export",
                    control_id="export",
                    source_state_id="result_ready",
                    target_state_id="result_ready",
                    method="browser",
                    result="passed",
                    evidence_ref="evidence://browser/click-export",
                    observed_state_id="result_ready",
                ),
            ),
        ),
    ),
    implementation_blindspots=(
        UIBlindspot(
            "settings_implementation",
            feature_id="settings_panel",
            control_ids=("settings",),
            reason="Settings are outside the short local example.",
            owner="settings browser validation",
            validation_boundaries=("settings browser check",),
            rationale="The persistent settings control is bounded for a separate implementation check.",
        ),
    ),
    journey_coverage_reviewed=journey_report.ok,
    validation_boundaries=("browser click-through",),
    rationale="Implemented UI claims need real click-through evidence tied to the same model.",
)

implementation_report = review_ui_implementation_validation(
    implementation_validation,
    interaction_model=model,
    journey_coverage=coverage,
)

derivation = UIStructureDerivation(
    "import-run-ui-structure",
    source_interaction_model_id="import-run-ui-flow",
    parent_surface_id="workbench",
    interaction_model_reviewed=model_report.ok,
    target_regions=(
        UIRegionRecommendation(
            "top-toolbar",
            level="global",
            placement="top-toolbar",
            owns_controls=("settings",),
            stable_across_states=True,
            rationale="Persistent controls remain stable.",
        ),
        UIRegionRecommendation(
            "main",
            level="primary",
            placement="main",
            owns_states=("empty", "result_ready"),
            owns_controls=("import", "export"),
            owns_displays=("result_summary",),
            rationale="Main workflow actions stay together.",
        ),
    ),
    state_region_map=(("empty", "main"), ("result_ready", "main")),
    control_region_map=(("settings", "top-toolbar"), ("import", "main"), ("export", "main")),
    display_region_map=(("result_summary", "main"),),
    persistent_control_ids=("settings",),
    stable_region_ids=("top-toolbar",),
    validation_boundaries=("browser state transition test",),
    rationale="Global settings and workflow actions live at different levels.",
)

structure_report = review_ui_structure_derivation(derivation, interaction_model=model)

text_blueprint = UITextHierarchyBlueprint(
    "import-run-text-hierarchy",
    source_interaction_model_id="import-run-ui-flow",
    source_structure_derivation_id="import-run-ui-structure",
    parent_surface_id="workbench",
    structure_derivation_reviewed=structure_report.ok,
    typography_tokens=(
        UITypographyToken(
            "page-title",
            hierarchy_level=1,
            text_roles=("page_title",),
            scale="surface-title",
            rationale="The surface title is the highest text role.",
        ),
        UITypographyToken(
            "control-label",
            hierarchy_level=4,
            text_roles=("button_label", "menu_label", "control_label"),
            scale="standard-text",
            rationale="Control labels stay below headings.",
        ),
        UITypographyToken(
            "status-text",
            hierarchy_level=4,
            text_roles=("status_text",),
            scale="standard-text",
            rationale="Status text belongs to the state or display owner.",
        ),
    ),
    text_elements=(
        UITextElement(
            "surface_title",
            "page_title",
            "page-title",
            "surface_title",
            region_id="main",
            rationale="The page title names the parent workflow.",
        ),
        UITextElement(
            "import_label",
            "button_label",
            "control-label",
            "import_action",
            region_id="main",
            source_control_id="import",
            rationale="Import is an action label, not a heading.",
        ),
        UITextElement(
            "result_summary_text",
            "status_text",
            "status-text",
            "run_summary",
            region_id="main",
            source_display_id="result_summary",
            visible_in_states=("result_ready",),
            rationale="The summary text follows the modeled result display.",
        ),
    ),
    validation_boundaries=("design token review",),
    rationale="Text roles are derived from regions, controls, displays, and states.",
)

text_report = review_ui_text_hierarchy(
    text_blueprint,
    interaction_model=model,
    structure_derivation=derivation,
)
print(model_report.format_text())
print(journey_report.format_text())
print(implementation_report.format_text())
print(structure_report.format_text())
print(text_report.format_text())
```

For a ready scaffold, run:

```powershell
python -m flowguard ui-flow-structure-template --output .
```

## Relationship To Other Routes

UI Flow Structure does not choose the visual style and does not implement
frontend code. Journey coverage is model evidence for the declared UI boundary,
not browser, frontend, accessibility, or production conformance. Implementation
validation records browser, desktop, screenshot, DOM, geometry, accessibility,
runtime, test, or manual observation evidence after a running UI exists; it
still does not replace accessibility testing, visual review, production
telemetry, or release conformance. Together, the route produces visible-surface,
structure/text, geometry/responsiveness, and optional implementation evidence
boundaries that frontend, Figma, browser, copy, and design-review workflows can
use.

Use Code Structure Recommendation when the question is how to split
implementation modules or files. Use StructureMesh when an existing codebase
refactor needs facade, dependency, parity, or public-entrypoint governance.
