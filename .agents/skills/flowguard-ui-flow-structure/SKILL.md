---
name: flowguard-ui-flow-structure
description: Use for UI interaction behavior, visible surface, structure, text hierarchy, and implementation evidence before frontend work.
---

# FlowGuard UI Flow Structure

Standalone FlowGuard satellite skill for UI states, controls, visible text, journeys, structure, and runnable evidence. Return to `model-first-function-flow` when not UI work.

## First Read

- Route id: `ui_flow_structure`.
- Starter: `ROUTE_STARTER_API["ui_flow_structure"]` and `ui-flow-structure-template`.
- Full: `ui-flow-structure-full-template` for journeys, regions, text blueprints, or many validation paths.
- Shape: UI event x UI state -> visible controls, displays, overlays, navigation, recovery.
- Helpers: `UIObservedSurfaceInventory`, `UIInteractionModel`, `UIVisibleSurface`, `UIControlFunctionalChainSet`, `MATLABBaselineCallbackGate`, `UIJourneyCoverage`, `UIImplementationValidation`, `UIRenderEvidenceSet`, `UIGeometryLayoutEvidenceSet`, `UITextHierarchyBlueprint`.
- Reference: `references/ui_flow_structure_protocol.md`.

## Hard Gates

- Verify the real package, keep AGENTS.md managed records current, and do not create a fake mini-framework.
- Existing/runnable UI: real-surface inventory is first. Map every observed button, input, select, table, displayed field, status text, dialog, and region to `UIControl`, `UIDisplayElement`, `UIVisibleSurfaceItem`, or blindspot.
- Every reachable enabled action/control needs a visible-control -> UI event -> code owner -> backend/local function -> UI state update -> click/test evidence chain. API/route/label proof is not enough.
- MATLAB migrations need `uigetfile`, `uigetdir`, `winopen`, no-callback, select/cancel/path/result/error semantics.
- UI complete/runnable/button-wired claims need `UIImplementationValidation`; screenshot, DOM text, native, and manual checks need evidence kind, event, result, ref, and boundary.
- Visible branches, recovery/cancel paths, visible-surface ownership, evidence kinds, and residual blindspots stay explicit.
- Broad transition-test claims need projected cells with code/runtime owners, then Model-Test Alignment or TestMesh evidence.

## Minimum Workflow

1. Inventory the real UI surface first when the UI exists or can run.
2. Model states, events, controls, displays, overlays, and transitions.
3. Review Visible surface, functional chains, MATLAB branches, duplicates, and blindspots.
4. Derive regions, persistent/contextual controls, text hierarchy, and calm typography guidance.
5. Add journey, evidence-kind, geometry/layout, transition-cell, and implementation validation as claim scope requires.

## Snapshot

Show a UI state diagram with visible controls, visible surface, regions, displays, recovery paths, text ownership, evidence kinds, and residual blindspots.

## Non-Goals

- Do not start with visual styling when interaction behavior is unknown.
- Do not treat manual prose as implementation validation.
