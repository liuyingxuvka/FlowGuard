---
name: flowguard-ui-flow-structure
description: Use when a FlowGuard model should be built or reviewed for UI-level interaction behavior first, then used to derive UI parent/child topology, regions, menu levels, stable placement, event/display ownership, duplicate control/info review, overlays, recovery actions, and text hierarchy before visual design or frontend implementation.
---

# FlowGuard UI Flow Structure

Standalone FlowGuard satellite skill for UI interaction behavior and
model-derived screen/control/text structure. Use it before visual design or
frontend implementation when UI state, controls, journeys, overlays, or visible
recovery paths are the risk.

Return to `model-first-function-flow` when the task is not UI behavior/state.

## First Read

- Route id: `ui_flow_structure`.
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
- Running UI completion needs structured click-through or browser evidence.
- Broad UI transition-test coverage claims need projected transition coverage
  cells with code contract or runtime node owners before completion is claimed.
  The projected cells must then bind owner code contracts and current test
  evidence through Model-Test Alignment or TestMesh.

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

Show a UI state diagram with visible-control branches, regions, displays,
recovery paths, text ownership, and residual blindspots.
When drawing the snapshot, edges mean reachable UI states, visible-control branches, recovery paths, or interaction transitions.

## Non-Goals

- Do not start with visual styling when interaction behavior is unknown.
- Do not treat manual prose as implementation validation.
