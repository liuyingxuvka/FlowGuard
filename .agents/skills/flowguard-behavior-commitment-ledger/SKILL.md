---
name: flowguard-behavior-commitment-ledger
description: Use for behavior registration, source coverage, one owner model, PPA handoff, or broad release confidence.
---

# FlowGuard Behavior Commitment Ledger

Standalone FlowGuard satellite skill for the external behavior account book.
Use before broad feature, UI/API/CLI/workflow, release, archive, or publish claims.

Return to `model-first-function-flow` when no project/work-package behavior
inventory is in scope. Use Primary Path Authority only after this ledger marks
a commitment `path_sensitive=true`.

## First Read

- Route id: `behavior_commitment_ledger`.
- Starter: `ROUTE_STARTER_API["behavior_commitment_ledger"]`.
- Helpers: `BehaviorCommitmentLedger`, `BehaviorCommitment`,
  `BehaviorSourceSurface`, `BehaviorPathAuthorityBinding`, `review_behavior_commitment_ledger()`,
  `behavior_path_binding_from_primary_path_report()`, and
  `behavior_commitment_contract_exhaustion_plan()`.
- Template: `behavior-commitment-ledger-template`.
- Reference: `references/behavior_commitment_ledger_protocol.md`.

## Hard Gates

- Verify FlowGuard check engine and AGENTS.md managed records; no fake mini-framework.
- A commitment is an external promise: UI, API, CLI, skill, workflow, release,
  process, docs, or user/agent visible behavior. Do not register helper
  functions, private files, fields, buttons, or models as commitments.
- Every in-scope source surface maps to commitments, and every in-scope
  commitment maps back to source evidence.
- Every in-scope commitment has exactly one primary owner model; supporting or
  child models cannot also be primary.
- Unknown dependencies, missing commitments, invented extras, overlap,
  stale evidence, and scoped-out rows without disposition block broad confidence.
- Path-sensitive commitments require Primary Path Authority evidence; blocked
  PPA blocks the commitment and any broad claim depending on it.
- Broad claims need ContractExhaustionMesh cases, TestMesh shards, MTA rows,
  Risk Evidence Ledger gates, and template harvest closure.

## Minimum Workflow

1. Define the project/work-package/release/UI/API/CLI/skill/process boundary.
2. Inventory source surfaces that promise behavior.
3. Register only external behavior commitments.
4. Record actor, trigger, result, failure boundary, owner, dependencies, evidence, validation, rationale.
5. Send `path_sensitive=true` rows to Primary Path Authority.
6. Run `review_behavior_commitment_ledger()` and repair gaps before broad claims.

## Snapshot

Show source surfaces -> commitments -> primary owner models -> PPA handoff ->
evidence/risk gates. Status: missing, extra, overlap, dependency, evidence, PPA.

## Non-Goals

- Do not replace Primary Path Authority, Model-Test Alignment, TestMesh, or Risk Evidence Ledger.
- Do not treat a model list as complete behavior coverage without ledger mapping.
- Do not certify future AI behavior; report current evidence and blockers only.
