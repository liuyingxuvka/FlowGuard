# UI Flow Structure

UI Flow Structure is FlowGuard's helper layer for model-first interface
planning. It first models the UI's interaction behavior, then derives the UI
structure from that model.

This route is for workflow-heavy interfaces where button placement, menu
levels, panels, overlays, persistent controls, and state-dependent actions need
to follow the product behavior instead of being placed arbitrarily.
It also reviews information and control redundancy: the same semantic
information or same-level function can be repeated only when the model records
why the repetition is intentional.

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
  parent/child UI topology before visual styling.
- a page may show the same information through a chart, card, table, text, or
  image, and repeated display needs to be checked for value rather than visual
  clutter;
- two buttons or menu items appear to trigger the same function at the same
  hierarchy level and need an explicit reason to remain separate.

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

## Two-Stage Workflow

```text
product/workflow intent
-> UI interaction model
-> review UI controls, states, transitions, availability, failures
-> UI structure derivation
-> review regions, menu levels, displays, overlays, stable placement, hierarchy
-> handoff to Figma, frontend implementation, browser checks, or design review
```

The first stage models the UI as:

```text
UI event x UI state -> Set(UI output x UI state)
```

The second stage derives placement and hierarchy from that flow:

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

The redundancy review is intentionally conservative:

- two display elements with the same `semantic_key` in one state need a
  `redundancy_rationale`;
- two same-level controls that trigger the same modeled function in one state
  need a `redundancy_rationale` or shared duplicate group;
- repeated global navigation across states is acceptable when it is modeled as
  persistent and stable;
- summary plus detail can be acceptable when the model explains the difference
  between the summary and the detail.

## Example

```python
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
print(model_report.format_text())
print(structure_report.format_text())
```

For a ready scaffold, run:

```powershell
python -m flowguard ui-flow-structure-template --output .
```

## Relationship To Other Routes

UI Flow Structure does not choose the visual style and does not implement
frontend code. It produces a structure contract that frontend, Figma, browser,
and design-review workflows can use.

Use Code Structure Recommendation when the question is how to split
implementation modules or files. Use StructureMesh when an existing codebase
refactor needs facade, dependency, parity, or public-entrypoint governance.
