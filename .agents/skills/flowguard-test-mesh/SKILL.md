---
name: flowguard-test-mesh
description: Use when tests/evidence are large, stale, skipped, release-only, or need parent/child ownership.
---

# FlowGuard Test Mesh

## Purpose
Govern owners, results, freshness, path quality.

## Entrypoint Scope
A standalone FlowGuard satellite skill; owner `test_mesh_maintenance`; structures evidence, not semantics/execution.

## Local Material Routing
Read `references/test_mesh_protocol.md`; load `references/test_mesh_reuse_protocol.md`, `references/test_mesh_long_check_protocol.md`, `references/test_mesh_release_protocol.md` only when triggered.

## Entrypoint Acceptance Map
Review a model-derived mesh, block incomplete evidence, and hand decisions to typed owners.

## Use When
- Large/slow/background child test scripts, stale/reused evidence, release gates, parent/child test hierarchy, artifact-payload matrices, or diagnostic boundaries.

## Do Not Use When
- Do not split code/models or choose semantics; send small tests to `flowguard`.

## Required Workflow
1. Define the parent gate and derive child test scripts/suites from a validation-structure model.
2. Freeze inventory; map each required surface, obligation, witness/check, member, case, shard to one owner.
3. Attach status, freshness, artifacts, reuse, terminal id, fingerprints, coverage, counts, findings; provider context is not evidence.
4. Bind long-check inputs/traces in `ProofArtifactRef.artifact_fingerprints`; progress is liveness only. Return child evidence and handoffs.

## Hard Gates
- Model-purpose gate: freeze task-specific failure(s)/claim_boundary; bind native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose: no mode/fallback; only FlowGuard-declared checks may support completion claims. Require real FlowGuard check engine and AGENTS.md managed record; forbid a fake mini-framework.
- PID/log/progress proves liveness; reuse needs current `TestResultReuseTicket`/`ProofArtifactRef`. One receipt fans out only inside its boundary; copies are not executions.
- Require `planned = executed + not_run`, `failed <= executed`, no not-run under `declared_complete`, visible reasons, stable finding ids.
- Local green cannot prove completeness. Every item is executed or delegated; delegation needs one owner and current evidence.
- Resolve owners before execution: missing/stale=`execute`; exact-current pass=`reuse_current`; malformed/tampered/ambiguous/unknown-impact/in-flight=`blocked`.
- Persist each successful child immediately; later requests execute only failed/stale owners and recompose exact identities.
- One parent invocation verifies each current child once, derives aggregates from one observation, performs one final source check, batch-publishes leaves, and reconciles ids once. Never persist the observation or repeat per-leaf semantics/currentness/store scans.
- TestMesh verifies cited evidence but cannot create necessity witnesses, select candidates, recompute Pareto dominance, or promote `normative_target`. Deep members need current triggers.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, validation mesh diagram, owner, freshness, blueprint depth/gap. Compact evidence preserves denominator, selected/executed/reused/not-run counts, fingerprints, negative cases, omitted ids; parent owns release confidence after freeze.
