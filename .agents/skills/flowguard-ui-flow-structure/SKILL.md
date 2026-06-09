---
name: flowguard-ui-flow-structure
description: Use for UI interaction behavior, visible surface, structure, text hierarchy, and implementation evidence before frontend work.
---

# FlowGuard UI Flow Structure

Standalone FlowGuard satellite skill for UI state, controls, visible text, journeys, overlays, recovery, structure, and runnable evidence. Return to `model-first-function-flow` when not UI work.

## First Read

- Route id: `ui_flow_structure`.
- Starter: `ROUTE_STARTER_API["ui_flow_structure"]` and `ui-flow-structure-template`.
- Full: `ui-flow-structure-full-template` for journeys, regions, text blueprints, or many validation paths.
- Shape: UI event x UI state -> visible controls, displays, overlays, navigation, recovery.
- Helpers: `UIInteractionModel`, `UIVisibleSurface`, `UIJourneyCoverage`, `UIImplementationValidation`, `UIRenderEvidenceSet`, `UIGeometryLayoutEvidenceSet`, `UITextHierarchyBlueprint`.
- Reference: `references/ui_flow_structure_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- Keep AGENTS.md managed records current, or say why not.
- Do not create a fake mini-framework.
- Visible branches, recovery/cancel paths, and residual blindspots stay explicit.
- Runnable claims need each reachable enabled action clicked or classified as pure UI/deferred with a blindspot reason.
- Visible surface keeps controls, status text, helper copy, placeholders, metadata, and disabled reasons user-facing and owned.
- Completion needs a declared evidence kind: screenshot, browser click-through, DOM text, geometry, accessibility, runtime trace, test result, or manual observation.
- Native dialogs/file pickers/manual observations need event, result, evidence ref, and boundary.
- Broad transition-test claims need projected cells with code/runtime owners, then Model-Test Alignment or TestMesh evidence.

## Minimum Workflow

1. Model UI states, events, controls, displays, overlays, transitions.
2. Review Visible surface: labels, helpers, status, placeholders, disabled reasons, metadata, internal-term leaks.
3. Derive persistent menus, contextual regions, local controls, and text slots.
4. Check duplicate controls/information and overlapping same-level controls.
5. Hand off text hierarchy with calm typography guidance: reuse treatments for similar jobs and explain visible differences.
6. Project UI transitions into coverage cells when claiming transition-test coverage; carry owner ids.
7. Add journey coverage, evidence kinds, geometry/layout evidence, and implementation validation for runnable UI.

## Snapshot

Show a UI state diagram with visible controls, visible surface, regions, displays, recovery paths, text ownership, evidence kinds, and residual blindspots; edges mean reachable controls and interaction transitions.

## Non-Goals

- Do not start with visual styling when interaction behavior is unknown.
- Do not treat manual prose as implementation validation.
