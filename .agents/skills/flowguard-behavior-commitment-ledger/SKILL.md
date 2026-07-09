---
name: flowguard-behavior-commitment-ledger
description: Use for behavior registration, source coverage, one owner model, PPA handoff, or broad release confidence.
---

# FlowGuard Behavior Commitment Ledger

Standalone FlowGuard satellite skill for the external behavior account book. Use before broad behavior, release, archive, publish, or done claims.

Return to `model-first-function-flow` when no behavior inventory is in scope. Use Primary Path Authority after `path_sensitive=true`.

## First Read

- Route id: `behavior_commitment_ledger`.
- Starter: `ROUTE_STARTER_API["behavior_commitment_ledger"]`.
- Helpers: `BehaviorCommitmentLedger`, `BehaviorCommitment`, `BehaviorSourceSurface`, `BehaviorPathAuthorityBinding`, `review_behavior_commitment_ledger()`.
- Template: `behavior-commitment-ledger-template`.
- Reference: `references/behavior_commitment_ledger_protocol.md`.

## Hard Gates

- Verify FlowGuard check engine and AGENTS.md managed records; no fake mini-framework.
- Commitment means external promise: UI, API, CLI, skill, workflow, release, process, docs, or visible behavior; not helper internals.
- Current source evidence is bidirectional: source -> commitment and commitment -> source.
- Pick mode before edits: `bootstrap_ledger`, `add_behavior`, `change_behavior`, `remove_or_replace_behavior`, `coverage_gap_backfill`, or `model_miss_check`.
- Use broad historical discovery only for bootstrap or coverage-gap backfill.
- Every commitment has one primary owner model; child/supporting models are subordinate.
- Replacement is single-path: active, deprecated, replaced, or removed/scoped out; no second successful route.
- Model miss is backfeed: map to existing commitment/owner first; backfill only if behavior was unregistered.
- Missing/extra commitments, overlaps, unknown deps, stale evidence, and scoped rows without disposition block broad confidence.
- Path-sensitive rows require Primary Path Authority; blocked PPA blocks the commitment.
- Broad claims need DCAR cases, TestMesh shards, MTA rows, Risk gates, and template harvest closure.

## Minimum Workflow

1. Define project/work-package boundary.
2. Pick the change mode.
3. Inventory source surfaces and freshness.
4. Register only external behavior commitments.
5. Record actor, trigger, result, failure boundary, owner, dependency, replacement/model-sync state, evidence, validation, rationale.
6. Send `path_sensitive=true` rows to PPA.
7. Route DCAR cases, TestMesh shards, and MTA rows.
8. Run `review_behavior_commitment_ledger()` and repair gaps before broad claims.

## Snapshot

Show sources -> commitments -> primary owner models -> PPA -> evidence/risk gates. Status: missing, extra, overlap, dependency, evidence, PPA.

## Non-Goals

- Do not replace PPA, MTA, TestMesh, or Risk Evidence Ledger.
- Do not treat a model list as complete behavior coverage.
- Do not certify future AI behavior; report current evidence and blockers.
