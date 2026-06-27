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

Snapshot: UI state diagram, controls, capabilities, tasks, recovery, evidence/blindspots; edges mean reachable controls/screens and interaction transitions.
Status: surface, task/control, evidence/gap, next UI check.

## Non-Goals

- Do not style-first or prose-validate.

<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose
Bind this FlowGuard route to one work contract, native checks, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers flowguard-ui-flow-structure and routed local materials only; no unrelated repos, private paths, services, publication, or release claims unless separately routed.
## Local Material Routing
Use FlowGuard's native router, package/model checks, `.skillguard/work-contract.json`, check_manifest, and run records; keep public text portable.
## Entrypoint Acceptance Map
Mode is native-integrated/hybrid as declared; SkillGuard executes gates around the native owner and must not add a second execution route.
## Use When
Use when this skill is selected and the task needs governed route, evidence, check, handoff, or closure behavior.
## Do Not Use When
Do not use outside the skill domain, without required materials, when a more specific skill owns the work, or for tiny direct answers.
## Required Workflow
Select the FlowGuard-owned route, open/compile the contract, start/update run record, run native model/check gates, refresh evidence, fix blockers, then close from current checks.
## Hard Gates
Block skipped phases, stale/prose-only evidence, hollow contracts, quality downgrades, native-route conflicts, and completion claims with blockers.
## Output Requirements
Report target, route, evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary; separate checked facts from judgment.
## SkillGuard Maintenance
Refresh contracts, checks, evidence, and installed copies after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
