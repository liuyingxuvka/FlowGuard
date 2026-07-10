---
name: flowguard-behavior-commitment-ledger
description: Use for external behavior registration, bidirectional source coverage, exactly one primary owner model, change-mode accounting, internal Primary Path Authority handoff, or broad done/release/archive/publish confidence.
---

# FlowGuard Behavior Commitment Ledger

## Purpose
Maintain the external behavior account book that binds promised behavior to current sources, one primary model owner, dependencies, evidence, and path authority.

## Entrypoint Scope
Route id: `behavior_commitment_ledger`; role: `public_owner`; native owner: `behavior_commitment_ledger`. This standalone FlowGuard satellite skill internally owns the `primary_path_authority` handoff for `path_sensitive=true` rows.

## Local Material Routing
Read `references/behavior_commitment_ledger_protocol.md` for commitment fields, six ledger modes, PPA binding, and broad-claim projections.

## Entrypoint Acceptance Map
Accept a bounded source/behavior inventory and selected mode; register commitments and one owner each; block missing/extra/overlapping/stale rows or blocked PPA; hand canonical cases, shards, alignment rows, and risk gates downstream.

## Use When
- Use for `bootstrap_ledger`, `add_behavior`, `change_behavior`, `remove_or_replace_behavior`, `coverage_gap_backfill`, or `model_miss_check`.

## Do Not Use When
- Do not inventory helper internals or replace PPA, Model-Test Alignment, TestMesh, or Risk Evidence Ledger; return no-inventory ordinary modeling to `model-first-function-flow`.

## Required Workflow
1. Define the boundary, choose the mode, and inventory fresh source surfaces bidirectionally.
2. Register external `BehaviorCommitmentLedger` rows with exactly one primary owner, dependencies, replacement/model-sync state, and evidence.
3. Bind path-sensitive rows through Primary Path Authority, run `review_behavior_commitment_ledger()`, and project DCAR/TestMesh/risk evidence.

## Hard Gates
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Default replacement leaves no second successful path; scoped rows still need owner, reason, validation boundary, and disposition.
- Missing source coverage, owner overlap, unknown dependency, stale evidence, blocked PPA, or absent broad-claim shards/gates blocks broad confidence.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus commitment/source/owner/PPA status.

## SkillGuard Maintenance
- Edit `.skillguard/contract-source.json`, then regenerate derived contracts; SkillGuard validates ledger ownership but cannot manufacture commitments, PPA evidence, or release confidence.
