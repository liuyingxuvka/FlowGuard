---
name: flowguard-behavior-commitment-ledger
description: Use for external behavior registration, bidirectional source coverage, exactly one primary owner model, change-mode accounting, internal Primary Path Authority handoff, or broad done/release/archive/publish confidence.
---

# FlowGuard Behavior Commitment Ledger

## Purpose
Maintain one `BehaviorCommitmentLedger` against an independent exact source inventory, with one disposition per source and one owner per commitment.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns route/native owner `behavior_commitment_ledger` (`public_owner`) and the internal PPA handoff.

## Local Material Routing
Read `references/behavior_commitment_ledger_protocol.md` for fields, modes, lookup, PPA, and projections.

## Entrypoint Acceptance Map
Accept a bounded inventory/mode; register one owner per commitment; block coverage, relation, freshness, or PPA gaps; hand evidence downstream.

## Use When
- Use for the six ledger modes: bootstrap, add, change, remove/replace, gap backfill, or miss check.

## Do Not Use When
- Do not inventory helper internals or replace sibling evidence owners; return ordinary modeling to `flowguard`.

## Required Workflow
1. Define boundary/mode; derive expected sources independently from WorkContexts and native UI/field inventories.
2. Freeze the inventory revision, fingerprint, discovery evidence, and exact expected ids before reviewing ledger dispositions.
3. Give every source one `modeled`, `delegated`, or `scoped` disposition with owner/evidence or reason.
4. For modeled behavior, set one `product_runtime`, `agent_operation`, or `development_process` plane plus `actor_kind`; kind is form, not plane.
5. Give each exact same-plane intent one stable id/active commitment; equivalent surfaces map to it, never a delegate commitment.
6. Set one owner, typed variants/relations with cross-plane rationale, lookup binding, lifecycle, and evidence.
7. Bind one current-green `primary_path_id`; run `review_behavior_commitment_ledger()` and project DCAR/TestMesh/risk evidence.

## Hard Gates
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; only FlowGuard-declared checks may support completion claims.
- Use the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework or second success path.
- Missing/duplicate sources, identity/evidence gaps, conflicting dispositions, owner overlap, stale PPA/shards, and untyped cross-plane relations block broad confidence.
- Supporting, observed, and historical sources cannot displace a declared normative target. Provider status and the ledger's own candidate rows cannot prove expected-inventory completeness.
- Cross-plane language never merges owners. `unclassified`, legacy dependencies, and ambiguous plural paths are upgrade-only blockers.
- Broad discovery is for bootstrap or coverage-gap backfill; ordinary changes stay in the affected commitment closure.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, and commitment/source/owner/lookup/PPA status.
