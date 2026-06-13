---
name: flowguard-ui-flow-structure
description: Use for UI behavior, visible surface, human-operability, and evidence.
---

# FlowGuard UI Flow Structure

Standalone FlowGuard satellite skill for UI states, text, journeys,
human-operability, structure, runnable evidence. Return to
`model-first-function-flow` when non-UI.

## First Read

- Route id: `ui_flow_structure`.
- Starter: `ROUTE_STARTER_API["ui_flow_structure"]`; templates: `ui-flow-structure-template`, `ui-flow-structure-full-template`.
- Shape: UI event x UI state -> controls, displays, overlays, recovery, feedback.
- Helpers: inventory, model, Visible surface, journey, task/human, implementation validation, render/geometry, text hierarchy.
- Reference: `references/ui_flow_structure_protocol.md`.

## Hard Gates

- Verify real package and AGENTS.md managed records; no fake mini-framework.
- Work mode comes first: `greenfield`, `source_based`, or `mixed`. Source-based/mixed need source baseline -> target mapping -> observed-source alignment; greenfield invents no source.
- Existing/runnable UI: real Visible surface inventory is first. Map observed buttons, inputs, selects, tables, fields, status, dialogs, regions, menus, toolbars to model owner or blindspot.
- Every reachable enabled action needs visible-control -> event -> code owner -> backend/local/native function -> UI state update -> click/test evidence. Label proof is not enough.
- Every supported task needs task path, primary control, chain, feedback, cancel/error, keyboard/focus, walkthrough, and human-operable affordance/grammar/region/dialog behavior.
- Source-based scopes need generic source branches: picker, external open, dialog, no-handler, trigger/confirm/cancel/value/result/error, and approved differences.
- UI complete/runnable/button-wired claims need `UIImplementationValidation`; screenshot, DOM text, native/manual checks need evidence kind, event, result, ref, boundary.
- Visible branches, recovery/cancel, ownership, calm typography guidance, and blindspots stay explicit.
- Broad transition-test claims need owner cells, then MTA or TestMesh.
- New/deepened UI models need harvest closure before broad claims.

## Minimum Workflow

1. Declare work mode.
2. Inventory real UI surface when it exists or runs.
3. For source-based/mixed scope, inventory source, map target differences, and align observed UI.
4. Model states, events, controls, displays, overlays, transitions, availability.
5. Review visible surface, chains, source branches, duplicates, blindspots.
6. Add task coverage and human-operability evidence.
7. Derive regions, controls, text hierarchy, calm typography guidance.
8. Add journey, evidence-kind, geometry, transition-cell, and implementation validation as needed.

Snapshot: UI state diagram with controls, tasks, visible surface, recovery, text ownership, evidence kinds, and blindspots.

## Non-Goals

- Do not style-first or prose-validate.
