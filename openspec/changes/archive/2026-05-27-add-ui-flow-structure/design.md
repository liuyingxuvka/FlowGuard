## Context

FlowGuard already has a compact Skill Kernel and route-specific satellite
skills for model-test alignment, process freshness, model misses, code
structure, ModelMesh, TestMesh, and StructureMesh. UI work is currently covered
only at the global trigger level as `ui_state_flow`; there is no direct route
for turning product intent into a UI-specific interaction model and then using
that model to derive stable interface structure.

The important boundary is that this route is not a visual design system. It is
a model-first UI interaction and topology route. It should help Codex decide
what the UI can do, in which state, from which control, and where each control
belongs before any Figma, frontend, or styling work begins.

## Goals / Non-Goals

**Goals:**

- Model the UI itself as `UI event x UI state -> Set(UI output x UI state)`.
- Represent initial UI state, control events, state nodes, transitions,
  persistent controls, contextual controls, parent/child interaction nodes,
  terminal states, recovery actions, state availability, semantic information
  displays, and intentional redundancy.
- Derive a UI structure blueprint from that UI interaction model: regions,
  screens or panels, control tiers, navigation, global actions, stage actions,
  dependency relationships, menu levels, overlay hierarchy, stable placement
  rules, display ownership, duplicate/overlap rationale, and validation
  boundaries.
- Provide public helper APIs and an executable reviewer for both the UI
  interaction model and the derived structure.
- Add a directly invokable `flowguard-ui-flow-structure` Codex satellite skill
  and route ambiguous cases back to `model-first-function-flow`.
- Keep README and public docs aligned with the expanded FlowGuard capability
  surface.

**Non-Goals:**

- Do not generate visual style, brand language, typography, or Figma mockups.
- Do not implement frontend code.
- Do not replace `frontend-design`, Figma, browser QA, or design implementation
  review.
- Do not turn every small UI tweak into a mandatory model.
- Do not claim production confidence from UI structure alone without runtime,
  frontend, browser, or conformance evidence when those surfaces exist.

## Decisions

### Two-stage helper model

The public helper will expose two related review surfaces:

1. `UIInteractionModel` reviewed by `review_ui_interaction_model(...)`.
2. `UIStructureDerivation` reviewed by `review_ui_structure_derivation(...)`.

The first surface checks whether the UI's own flow is complete and coherent.
The second checks whether the proposed UI regions and control hierarchy are
derived from that flow, including first-level persistent menus, second-level
contextual regions, third-level local controls, blocking overlays, drawers,
inspectors, information-display ownership, intentional redundancy, and layout
placements that must remain stable across states. This
avoids collapsing the user's clarified requirement into a one-step
model-to-layout translation.

Alternative considered: only add `UIStructureRecommendation`. That misses the
required UI-flow modeling stage and would allow arbitrary layouts without a UI
state transition basis.

### Keep the route as a satellite skill

The new `flowguard-ui-flow-structure` Skill will be directly invokable when the
user asks for model-first UI interaction design, UI button flow modeling,
stateful UI structure, or model-derived UI topology. The kernel remains the
canonical owner of applicability decisions, hard gates, and ambiguous routing.

Alternative considered: keep the route only inside the kernel. That would
avoid another skill, but it would keep a high-frequency UI design route hard to
discover and too easy to skip during frontend work.

### Public API, not private prompt only

The route will include package helper APIs and a template CLI, mirroring Code
Structure Recommendation. The skill text tells Codex when and how to use the
route; the helper API makes the output checkable.

Alternative considered: add only a prompt skill. That is faster but weak: it
would not catch missing initial states, unowned controls, missing recovery
actions, or undocumented stage-dependent controls.

### README is part of the release surface

This release should rewrite the README's front structure so FlowGuard's current
capabilities are visible before deep examples. The README should keep old
accurate material, but reorganize it around current routes, helpers, skills,
templates, and practical use.

## Risks / Trade-offs

- **Over-modeling small UI edits** -> The skill and docs will declare small,
  visual-only edits out of scope.
- **Confusing UI structure with visual design** -> Non-goals and workflow
  boundaries will explicitly hand off to frontend/Figma/design review only
  after the UI interaction model and structure blueprint exist.
- **API surface growth** -> Keep helper classes small, plain dataclasses, and
  aligned with existing helper style.
- **README drift** -> Update tests, docs, changelog, and version in the same
  release.
- **Installed skill mismatch** -> Sync repository skills to the installed Codex
  skill directory before release and verify the installed copy.

## Migration Plan

1. Add the helper module and tests without changing the core FlowGuard model
   semantics.
2. Add the template CLI and public exports.
3. Add the satellite skill and kernel route wording.
4. Update docs, README, changelog, and release checklist.
5. Sync installed skills and shadow workspace.
6. Run model checks, OpenSpec validation, skill validation, focused tests, and
   full regression before tagging.

Rollback is simple before release: remove the helper module, skill directory,
docs, template command, and exports. After release, remove only in a new
breaking or deprecation-aware change.
