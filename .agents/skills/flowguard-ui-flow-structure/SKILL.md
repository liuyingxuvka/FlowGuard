---
name: flowguard-ui-flow-structure
description: Use for UI behavior, visible surface, human-operability, and evidence before frontend work.
---

# FlowGuard UI Flow Structure

Standalone FlowGuard satellite skill for UI states, text, journeys,
human-operability, structure, runnable evidence. Return to
`model-first-function-flow` when not UI work.

## First Read

- Route id: `ui_flow_structure`.
- Starter: `ROUTE_STARTER_API["ui_flow_structure"]`, `ui-flow-structure-template`; full: `ui-flow-structure-full-template`.
- Shape: UI event x UI state -> controls, displays, overlays, recovery, feedback.
- Helpers: inventory, model, Visible surface, journey, task coverage, human-operability, implementation validation, render/geometry evidence, text hierarchy.
- Reference: `references/ui_flow_structure_protocol.md`.

## Hard Gates

- Verify the real package, keep AGENTS.md managed records current, and do not create a fake mini-framework.
- Existing/runnable UI: real Visible surface inventory is first. Map every observed button, input, select, table, field, status, dialog, region, menu, and toolbar to model item or blindspot.
- Every reachable enabled action/control needs visible-control -> UI event -> code owner -> backend/local/native function -> UI state update -> click/test evidence. Label proof is not enough.
- Every supported task needs feature -> task -> UI path -> primary control -> functional chain -> feedback -> cancel/error -> keyboard/focus -> walkthrough evidence.
- Affordance, grammar, region, dialog/window returns, and focus must match what a human can operate.
- MATLAB migrations need `uigetfile`, `uigetdir`, `winopen`, no-callback, select/cancel/path/result/error semantics.
- UI complete/runnable/button-wired claims need `UIImplementationValidation`; screenshot, DOM text, native, manual checks need evidence kind, event, result, ref, boundary.
- Visible branches, recovery/cancel, ownership, evidence kinds, calm typography guidance, and blindspots stay explicit.
- Broad transition-test claims need cells with owners, then MTA or TestMesh.
- New/deepened UI models need harvest closure before broad claims.

## Minimum Workflow

1. Inventory the real UI surface first when the UI exists or can run.
2. Model states, events, controls, displays, overlays, transitions, availability.
3. Review visible surface, chains, MATLAB branches, duplicates, blindspots.
4. Add task coverage and human-operability: affordance, grammar, regions, dialogs/windows, keyboard/focus, walkthroughs.
5. Derive regions, controls, text hierarchy, calm typography guidance.
6. Add journey, evidence-kind, geometry, transition-cell, and implementation validation as needed.

## Snapshot

Show a UI state diagram with controls, task flows, visible surface, regions,
displays, recovery, text ownership, evidence kinds, and blindspots.

## Non-Goals

- Do not start with styling when interaction behavior is unknown.
- Do not treat prose as implementation validation.
