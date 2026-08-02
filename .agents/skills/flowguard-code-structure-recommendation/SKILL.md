---
name: flowguard-code-structure-recommendation
description: Use when a FlowGuard model should drive pre-code modules, FunctionBlock/state/field/effect owners, facades, adapters, or validation boundaries.
---

# FlowGuard Code Structure Recommendation

## Purpose
Derive recommendation-only FunctionBlock-to-module ownership, facades, adapters, fields, effects, and validation boundaries from a named model.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns `code_structure_recommendation` (`public_owner`), not refactoring.

## Local Material Routing
After admission, read `references/code_structure_recommendation_protocol.md` for the complete schema and handoffs.

## Entrypoint Acceptance Map
Accept a named current model; derive owners and boundaries; block omissions/duplicates; send existing-code work to StructureMesh.

## Use When
- Use before code when module, function, facade, adapter, field/effect owner, or validation boundary is unclear.

## Do Not Use When
- Do not refactor existing code, invent behavior, or replace parity evidence; return missing models to `flowguard`.

## Required Workflow
1. Freeze the model, maturation/admission identities, blocks, state, fields, effects, and public entrypoints.
2. Recommend cohesive modules, single owners, facades/adapters, and observable leaves; record StructureMesh, Model-Test Alignment, or FieldLifecycleMesh handoffs.
3. For an explicit blueprint claim, fingerprint the exact model-element universe, disposition every required element, and emit reverse implementation-coverage obligations for the independent source audit.
4. Without exact current admission for the same task/model/scope, remain recommendation-only.

## Hard Gates
- Model-purpose gate: freeze task-specific failure(s); bind native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose: no mode/fallback; only FlowGuard-declared checks may support completion claims. Require the real FlowGuard check engine and AGENTS.md managed record; forbid a fake mini-framework.
- Do not invent modules before responsibilities. Every write needs one owner; public facades and validation boundaries stay explicit; oversized leaves split or remain scoped.
- A diagram or nonempty map is not readiness. Omitted elements, missing reverse obligations, fingerprint drift, or scope beyond admission block blueprint use. This route neither scans source nor proves static closure.
- Route ArchitectureReduction only for a concrete evidence-backed contraction candidate. Any model/maturation/admission identity drift makes this recommendation stale.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, `typed_next_actions`, ownership map, and code structure diagram; edges mean owns, calls, adapts, exposes, or validates. Blueprint output adds the model fingerprint, exact mapped/unresolved ids, and reverse obligations.


<!--VTP:target adapter/catalog;native validation;stale|ambiguous=block;preview!=proof;harvest-->
