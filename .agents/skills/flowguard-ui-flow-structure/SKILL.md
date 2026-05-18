---
name: flowguard-ui-flow-structure
description: Use when a FlowGuard model should be built or reviewed for UI-level interaction behavior first, then used to derive UI parent/child topology, screen or region structure, menu levels, stable control placement, navigation state, button/event ownership, information display ownership, duplicate information/control-function review, overlays, recovery actions, and model-derived interface hierarchy before visual design or frontend implementation.
---

# FlowGuard UI Flow Structure

This is a standalone FlowGuard satellite skill for model-first UI interaction
structure. Use it directly when the user asks how a UI's buttons, controls,
states, navigation, regions, menus, panels, or overlays should work and fit
together before visual design or frontend implementation.

Return to `model-first-function-flow` when the UI behavior boundary is unclear,
when the request is visual-only or trivial, or when multiple FlowGuard routes
need coordination.

## Hard Gates

- Verify the real package before claiming FlowGuard use:
  `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- Do not create a fake mini-framework or prose-only substitute.
- Do not skip the UI interaction model and jump straight to layout prose.
- Represent UI behavior as `UI event x UI state -> Set(UI output x UI state)`.
- Derive hierarchy, menu levels, regions, overlays, stable placements, and
  information-display ownership from modeled UI states, controls, displays,
  events, transitions, and dependencies.
- Treat repeated information and repeated controls as reviewable design
  obligations: allow intentional duplication only when the model records why it
  is necessary, such as accessibility, persistent navigation, summary plus
  detail, or two user vocabularies for the same action.
- Keep visual design, Figma execution, frontend implementation, browser QA, and
  design review as downstream work, not proof that the UI flow model is sound.
- Keep skipped, deferred, stale, or not-run checks visible.

## Workflow

1. Read the product intent and any existing FlowGuard product/workflow model.
2. Build or review the UI interaction model: initial UI state, controls,
   displayed information, events, state nodes, transitions, failure/recovery
   states, terminal states, and state availability.
3. Run `review_ui_interaction_model(...)` when available.
4. Derive the UI structure from the reviewed UI model: parent/child nodes,
   first-level persistent menus, second-level contextual regions, third-level
   local controls, overlay hierarchy, stable toolbar/region placement,
   navigation ownership, display ownership, duplicate/redundancy rationale, and
   validation boundaries.
5. Run `review_ui_structure_derivation(...)` when available.
6. Hand the resulting UI structure contract to frontend, Figma, browser, or
   design-review workflows only after the model and derivation are explicit.

## Owned Helpers

- `UIInteractionModel`, `UIControl`, `UIDisplayElement`, `UIStateNode`,
  `UITransition`
- `UIStructureDerivation`, `UIRegionRecommendation`
- `review_ui_interaction_model(...)`
- `review_ui_structure_derivation(...)`
- `ui-flow-structure-template`
- `docs/ui_flow_structure.md`
- `references/ui_flow_structure_protocol.md`

## Non-Goals

- Do not choose brand style, typography, color palette, or visual polish.
- Do not implement frontend code.
- Do not replace `frontend-design`, Figma, Browser checks, or
  `design-implementation-reviewer`.
- Do not use this route for ordinary code module split advice; use
  `flowguard-code-structure-recommendation`.
- Do not use this route for existing large-code refactors; use
  `flowguard-structure-mesh`.

For detailed route rules, read `references/ui_flow_structure_protocol.md`.
