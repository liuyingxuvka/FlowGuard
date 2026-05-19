---
name: flowguard-ui-flow-structure
description: Use when a FlowGuard model should be built or reviewed for UI-level interaction behavior first, then used to derive UI parent/child topology, screen or region structure, menu levels, stable control placement, navigation state, button/event ownership, information display ownership, duplicate information/control-function review, overlays, recovery actions, model-derived interface hierarchy, and a UI text hierarchy blueprint before visual design, copywriting, or frontend implementation.
---

# FlowGuard UI Flow Structure

This is a standalone FlowGuard satellite skill for model-first UI interaction
structure. Use it directly when the user asks how a UI's buttons, controls,
states, navigation, regions, menus, panels, overlays, labels, headings, status
text, or empty/error/recovery messages should work and fit together before
visual design, copywriting, or frontend implementation.

Return to `model-first-function-flow` when the UI behavior boundary is unclear,
when the request is visual-only or trivial, or when multiple FlowGuard routes
need coordination.

## Hard Gates

- Verify the real package before claiming FlowGuard use:
  `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- Do not create a fake mini-framework or prose-only substitute.
- Do not skip the UI interaction model and jump straight to layout prose.
- Do not claim complete app-level UI coverage until launch-to-terminal UI
  journey coverage has been reviewed: launch state, entry points, feature
  journeys, every reachable visible/enabled control branch,
  terminal/recovery/cancel/exit behavior, and residual blindspots.
- Do not claim an implemented, runnable, or complete real UI until
  implementation validation has aligned the user-visible feature contracts, the
  reviewed UI journey coverage, and browser, desktop, or manual click-through
  evidence. Model-complete UI and running-UI-complete are different claims.
- Do not skip the structure derivation and jump straight to microcopy or
  screen text.
- Represent UI behavior as `UI event x UI state -> Set(UI output x UI state)`.
- Derive hierarchy, menu levels, regions, overlays, stable placements, and
  information-display ownership from modeled UI states, controls, displays,
  events, transitions, and dependencies.
- Derive the UI text hierarchy blueprint from the reviewed structure:
  headings, section labels, primary/secondary action labels, status text,
  helper text, empty states, error/recovery copy slots, and text ownership must
  trace back to modeled states, controls, displays, regions, and hierarchy
  levels.
- Treat repeated information and repeated controls as reviewable design
  obligations: allow intentional duplication only when the model records why it
  is necessary, such as accessibility, persistent navigation, summary plus
  detail, or two user vocabularies for the same action.
- Keep visual design, Figma execution, frontend implementation, browser QA, and
  design review as downstream work, not proof that the UI flow model, structure
  derivation, or text hierarchy blueprint is sound.
- When downstream browser QA, desktop automation, or human click-through
  evidence exists, record it through implementation validation instead of
  treating prose like "manually tested" as sufficient completion proof.
- Keep skipped, deferred, stale, or not-run checks visible.

## Workflow

1. Read the product intent and any existing FlowGuard product/workflow model.
2. Build or review the UI interaction model: initial UI state, controls,
   displayed information, events, state nodes, transitions, failure/recovery
   states, terminal states, and state availability.
3. Run `review_ui_interaction_model(...)` when available.
4. For complete app-level UI claims, build or review UI journey coverage from
   launch state through declared entry points, feature journeys, terminal
   states, recovery/cancel/exit behavior, every reachable visible/enabled
   control branch, and residual blindspots. Run
   `review_ui_journey_coverage(...)` when available.
5. Derive the UI structure from the reviewed UI model and app-level journey
   coverage when required: parent/child nodes,
   first-level persistent menus, second-level contextual regions, third-level
   local controls, overlay hierarchy, stable toolbar/region placement,
   navigation ownership, display ownership, duplicate/redundancy rationale, and
   validation boundaries.
6. Run `review_ui_structure_derivation(...)` when available.
7. Derive the UI text hierarchy blueprint from the reviewed structure: page and
   region headings, labels, action text, state/status messages, helper text,
   validation text, recovery/error copy slots, and text priority/ownership.
8. When claiming the running UI is implemented or complete, build or review UI
   implementation validation: feature contracts, mapped journeys, browser,
   desktop, or manual journey runs, step evidence, current model revision, pure
   UI actions, and residual implementation blindspots. Run
   `review_ui_implementation_validation(...)` when available.
9. When the UI model or implementation evidence is hard to understand from
   prose alone, include an optional user-facing Mermaid diagram showing launch
   entries, key UI states, visible-control branches, failure/recovery/terminal
   paths, evidence status, and claim boundaries. The diagram explains the model
   and does not replace the executable reviews.
10. Hand the resulting UI structure and text hierarchy contract to frontend,
   Figma, browser, copy/design, or design-review workflows only after the model,
   required journey coverage, derivation, blueprint, and any implementation
   completion evidence are explicit.

## Owned Helpers

- `UIInteractionModel`, `UIControl`, `UIDisplayElement`, `UIStateNode`,
  `UITransition`
- `UIJourneyCoverage`, `UIJourneyEntryPoint`, `UIFeatureJourney`,
  `UITerminalActionAllowance`, `UIResidualBlindspot`
- `UIFeatureContract`, `UIImplementationValidation`,
  `UIImplementationJourneyRun`, `UIImplementationStepEvidence`,
  `UIImplementationBlindspot`
- `UIStructureDerivation`, `UIRegionRecommendation`
- `UITextHierarchyBlueprint`, `UITextElement`, `UITypographyToken`
- `review_ui_interaction_model(...)`
- `review_ui_journey_coverage(...)`
- `review_ui_implementation_validation(...)`
- `review_ui_structure_derivation(...)`
- `review_ui_text_hierarchy(...)`
- `ui-flow-structure-template`
- `docs/ui_flow_structure.md`
- `references/ui_flow_structure_protocol.md`

## Non-Goals

- Do not choose brand style, final font family, color palette, or visual
  polish. Semantic typography tokens are allowed when they are derived from the
  UI model and text hierarchy.
- Do not write final brand copy or marketing language; produce the hierarchy,
  ownership, and intent of UI text slots.
- Do not implement frontend code.
- Do not replace `frontend-design`, Figma, Browser checks, or
  `design-implementation-reviewer`.
- Do not use this route for ordinary code module split advice; use
  `flowguard-code-structure-recommendation`.
- Do not use this route for existing large-code refactors; use
  `flowguard-structure-mesh`.

For detailed route rules, read `references/ui_flow_structure_protocol.md`.
