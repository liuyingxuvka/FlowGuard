---
name: flowguard-ui-flow-structure
description: Use for UI behavior, observed surface, capabilities, interaction states, journeys, structure/text, human operability, runnable evidence, geometry, responsiveness, or transition coverage.
---

# FlowGuard UI Flow Structure

## Purpose
Model UI event x UI state behavior and prove the declared boundary from observed surface through runnable evidence.

## Entrypoint Scope
Route id: `ui_flow_structure`; role: `public_owner`; native owner: `ui_flow_structure`. This standalone FlowGuard satellite skill owns UI behavior/surface evidence, not visual styling or code structure.

## Local Material Routing
Read `references/ui_flow_structure_protocol.md` as the index; load `references/ui_observed_surface_protocol.md`, `references/ui_capability_interaction_protocol.md`, `references/ui_journey_structure_text_protocol.md`, `references/ui_human_operability_protocol.md`, `references/ui_implementation_evidence_protocol.md`, and `references/ui_geometry_transition_protocol.md` only when that boundary is in scope.

## Entrypoint Acceptance Map
Accept `greenfield`, `source_based`, or `mixed` scope; inventory surface/capabilities; block unowned enabled actions, missing recovery, or design-only runnable claims; hand transitions to MTA/TestMesh.

## Use When
- Use for UI controls, displays, dialogs, menus, navigation, visible surface, tasks, blindspots, reachable enabled action chains, implementation runs, or layout/responsiveness evidence.

## Do Not Use When
- Do not style first, prose-validate, treat labels/API routes as functional proof, or replace frontend/design/code-structure workflows; return non-UI work to `model-first-function-flow`.

## Required Workflow
1. Declare work mode; inventory observed surface and required capabilities when a UI exists or runs.
2. Build UI states/events/controls/displays, journey coverage, structure, text hierarchy, task coverage, and human-operability evidence.
3. For runnable claims, bind screenshot/DOM/event/result evidence, click chains, geometry/transitions, blindspots, and tests.

## Hard Gates
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Every reachable enabled action needs control -> event -> owner -> function -> UI update -> click/test evidence, pure-UI disposition, or owned blindspot.
- Design evidence cannot prove runnable UI; source/mixed work needs baseline alignment, failures/recovery stay explicit, and deepened UI models require template harvest closure.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus a UI state diagram, task/control coverage, and blindspots.

## SkillGuard Maintenance
- Edit `.skillguard/contract-source.json`, then regenerate derived contracts; SkillGuard checks the UI route contract and cannot fabricate click-through, screenshot, DOM, or human evidence.
