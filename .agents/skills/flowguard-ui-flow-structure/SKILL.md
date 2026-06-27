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
Bind each flowguard run to the declared integration mode, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers flowguard-ui-flow-structure plus explicitly routed local materials; no unrelated repos, private files, external services, publication, or release claims unless requested and routed.
## Local Material Routing
Use workspace, skill directory, user files, or configured project paths; keep private machine paths local and public instructions portable.
## Entrypoint Acceptance Map
Use SkillGuard as the runtime contract executor attached to the native route/check owner: FlowGuard skill route map plus the real flowguard package/model checks. It enforces contract gates through that native owner before progress or closure; duplicate SkillGuard-owned execution paths are invalid. Declared gates/routes: model preflight, process review, evidence alignment, closure.
## Use When
Use when the request matches flowguard-ui-flow-structure and needs this governed workflow, materials, checks, or handoff behavior.
## Do Not Use When
Do not use outside the domain, without required materials, when a more specific skill owns the work, or for tiny direct answers.
## Required Workflow
Select the target-owned native route/check surface, run the SkillGuard contract gates around the native workflow, collect evidence, run checks, fix failures, then report.
## Hard Gates
Do not skip phases, do not replace required evidence with prose, do not treat stale reports as current, do not weaken validation to pass, and do not claim completion when blockers remain.
## Output Requirements
Report evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary; distinguish checked, unchecked, blocked, and uncertain.
## SkillGuard Maintenance
Keep `.skillguard` contracts, checks, evidence, and ledger current; rerun SkillGuard after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
