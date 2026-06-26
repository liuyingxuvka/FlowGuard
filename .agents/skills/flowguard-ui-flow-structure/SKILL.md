---
name: flowguard-ui-flow-structure
description: Use for UI behavior, visible surface, human-operability, and evidence.
---

# FlowGuard UI Flow Structure

Standalone FlowGuard satellite skill for UI states, journeys, human-operability, structure, and evidence. Return to `model-first-function-flow` when non-UI.

## First Read

- Route id: `ui_flow_structure`.
- Starter: `ROUTE_STARTER_API["ui_flow_structure"]`; templates: compact/full.
- Shape: UI event x UI state -> controls, displays, overlays, recovery, feedback.
- Helpers: inventory, capability coverage, model, Visible surface, journey, task/human, implementation, render/geometry, text.
- Reference: `references/ui_flow_structure_protocol.md`.

## Hard Gates

- Verify real package and AGENTS.md managed records; no fake mini-framework.
- Work mode first: `greenfield`, `source_based`, or `mixed`; source-based/mixed need baseline -> mapping -> observed alignment.
- Existing/runnable UI: observed surface is first. Map visible controls, fields, status, dialogs, menus, toolbars, and regions to owner or blindspot.
- Non-trivial or runnable UI claims need capability coverage: capability -> feature, task, UI path, owner/chain, output, evidence or blindspot.
- Each reachable enabled action needs visible-control -> event -> owner -> backend/local/native function -> UI state update -> click/test evidence. Label proof is not enough.
- Supported tasks need path, primary control, chain, feedback, cancel/error, keyboard/focus, walkthrough, and affordance/grammar/region/dialog behavior.
- Source-based scopes need generic source branches and approved differences.
- Complete/runnable/button-wired claims need `UIImplementationValidation` with evidence kind such as screenshot/DOM text, event, result, ref, and boundary.
- Branches, recovery/cancel, ownership, typography guidance, and blindspots stay explicit.
- Broad transition-test claims need owner cells, then MTA or TestMesh.
- New/deepened UI models need harvest closure before broad claims.

## Minimum Workflow

1. Declare work mode.
2. Inventory real UI surface when it exists or runs.
3. For source-based/mixed scope, inventory source, map target differences, and align observed UI.
4. Model states, events, controls, displays, overlays, transitions, availability.
5. Add capability coverage: required capabilities, scoped gaps, outputs, and bindings to feature/task/UI path/owner/evidence.
6. Review visible surface, chains, source branches, duplicates, blindspots.
7. Add task coverage and human-operability evidence.
8. Derive regions, controls, text hierarchy, calm typography guidance.
9. Add journey, evidence-kind, geometry, transition-cell, and implementation validation as needed.

Snapshot: UI state diagram with controls, capabilities, tasks, visible surface, recovery, text ownership, evidence, blindspots.
Status: surface, task/control, evidence/gap, next UI check.

## Non-Goals

- Do not style-first or prose-validate.


<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose

Use this skill for its declared flowguard workflow while binding each run to a route, evidence, checks, and a bounded completion claim.

## Entrypoint Scope

The entrypoint covers the installed flowguard-ui-flow-structure skill and the local materials explicitly routed by its instructions. It does not expand to unrelated repositories, private files, external services, publication, or release claims unless the user request and skill workflow explicitly include them.

## Local Material Routing

Resolve local materials from the active workspace, this skill directory, user-provided files, or explicitly configured project paths. Treat private machine paths as local-only inputs and keep public-facing instructions portable.

## Entrypoint Acceptance Map

A valid run selects one declared route, follows the phase order, records direct evidence, runs required checks, reports blockers and failures, and closes only inside the claim boundary. Available routes: model preflight, process review, evidence alignment, closure.

## Use When

Use when the user request matches the flowguard-ui-flow-structure activation boundary and needs this skill's governed workflow, source material, checks, or handoff behavior.

## Do Not Use When

Do not use when the task is outside this skill's domain, when required local materials are unavailable, when another more specific skill owns the request, or when the user asks only for a tiny direct answer.

## Required Workflow

Select the route, inspect local materials, perform the work in phase order, collect direct evidence, run the required checks, fix failures, and only then report progress or completion.

## Output Requirements

When reporting, include evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary. State clearly what was checked, what was not checked, and what remains blocked or uncertain.

## SkillGuard Maintenance

Keep the `.skillguard` control root, work contract, check manifest, check scripts, evidence records, and progress ledger current. Re-run SkillGuard checks after changing this entrypoint, route behavior, evidence rules, or closure wording.

<!-- END SKILLGUARD CONTRACT LAYER -->
