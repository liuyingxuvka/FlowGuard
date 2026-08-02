---
name: flowguard-behavior-commitment-ledger
description: Use for external behavior registration, source coverage, one primary owner, change accounting, Primary Path Authority handoff, or broad confidence.
---

# FlowGuard Behavior Commitment Ledger

## Purpose
Maintain one `BehaviorCommitmentLedger`: every external promise has source evidence, one disposition, one owner, and current Primary Path Authority.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns `behavior_commitment_ledger` (`public_owner`) and its PPA handoff.

## Local Material Routing
After admission, read `references/behavior_commitment_ledger_protocol.md` for all fields, modes, lookup, and projections.

## Entrypoint Acceptance Map
Accept a bounded source inventory and mode; register ownership; block coverage, relation, freshness, or PPA gaps.

## Use When
- Use for the six ledger modes: bootstrap, add, change, remove/replace, gap backfill, or miss check.

## Do Not Use When
- Do not inventory internals or replace sibling evidence owners; return ordinary modeling to `flowguard`.

## Required Workflow
1. Freeze boundary, mode, inventory revision/fingerprint, discovery evidence, and exact source ids.
2. Give every source one `modeled|delegated|scoped` disposition with evidence or reason; modeled behavior gets one plane, actor kind, stable commitment, owner, typed relations, lookup, and lifecycle.
3. Bind one current-green `primary_path_id`; run `review_behavior_commitment_ledger()` and hand DCAR/TestMesh/risk evidence downstream.
4. For an explicit blueprint claim, hand off only external commitment/source/path ids, owner references, and the ledger fingerprint. Internal files, symbols, helpers, implementation dispositions, and developer activity never enter BCL.

## Hard Gates
- Model-purpose gate: freeze task-specific failure(s); bind native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose: no mode/fallback; only FlowGuard-declared checks may support completion claims. Require the real FlowGuard check engine and AGENTS.md managed record; forbid a fake mini-framework.
- Missing/duplicate sources, conflicting dispositions, owner overlap, stale PPA, untyped relations, or ambiguous authority block broad confidence.
- Broad discovery is only for bootstrap/gap backfill; ordinary changes stay affected-only.
- BCL owns visible promises, not target roles, permissions, activity logs, internal code, resources, or implementation completeness. A blueprint may reference both independent owners by fingerprint; BCL never reconstructs software.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, `typed_next_actions`, and source/commitment/owner/lookup/PPA status. Blueprint handoff includes only current external ids and ledger fingerprint.
