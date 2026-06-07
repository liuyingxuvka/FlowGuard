---
name: flowguard-ui-flow-structure
description: Use when UI interaction behavior should be modeled first, then used to derive topology, regions, menus, stable placement, event/display ownership, duplicate controls/info, overlays, recovery actions, and text hierarchy before frontend work.
---

# FlowGuard UI Flow Structure

Standalone FlowGuard satellite skill for UI interaction behavior and
model-derived screen/control/text structure. Use it when UI state, controls,
journeys, overlays, or recovery paths are the risk.

Return to `model-first-function-flow` when the task is not UI behavior/state.

## First Read

- Route id: `ui_flow_structure`.
- Default entry: `ROUTE_STARTER_API["ui_flow_structure"]` and
  `ui-flow-structure-template`.
- Full entry: `ui-flow-structure-full-template` for full journeys, regions,
  text blueprints, or many runnable validation paths.
- Model shape: UI event x UI state -> visible controls, displays, overlays,
  navigation, and recovery.
- Core helpers: `UIDisplayElement`, `UIJourneyCoverage`,
  `UIImplementationValidation`, `UITextHierarchyBlueprint`,
  `review_ui_interaction_model()`,
  `ui_interaction_model_to_transition_coverage()`.
- Reference: `references/ui_flow_structure_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- Visible-control branches, recovery/cancel paths, and residual blindspots must
  stay explicit.
- Running UI completion needs click-through or browser evidence.
- Broad transition-test claims need projected cells with code contract/runtime
  owners, then Model-Test Alignment or TestMesh evidence.

## Minimum Workflow

1. Model UI states, events, controls, displays, overlays, and transitions.
2. Derive persistent menus, contextual regions, local controls, and text slots.
3. Check duplicate controls/information and overlapping same-level controls.
4. Hand off text hierarchy with calm typography guidance: reuse treatments for
   similar text jobs and explain visible differences.
5. Project UI transitions into transition coverage cells when claiming
   transition-test coverage; carry code contract/runtime node ids for each
   handler that owns the transition.
6. Add journey coverage and implementation validation when claiming runnable UI.

## Snapshot

Show a UI state diagram with visible controls, regions, displays, recovery
paths, text ownership, and residual blindspots.

## Non-Goals

- Do not start with visual styling when interaction behavior is unknown.
- Do not treat manual prose as implementation validation.
