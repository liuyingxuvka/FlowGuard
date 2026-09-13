---
name: flowguard-test-mesh
description: standalone FlowGuard satellite skill; Use when tests/evidence are large, stale, skipped, release-only, or need parent/child ownership.
---

# FlowGuard Test Mesh

## Purpose
Govern owners, results, freshness, path quality.

## Entrypoint Scope
Owner `test_mesh_maintenance`; structures evidence, not semantics/execution.

## Local Material Routing
After admission, read `references/test_mesh_protocol.md`; load `references/test_mesh_reuse_protocol.md`, `references/test_mesh_long_check_protocol.md`, `references/test_mesh_release_protocol.md` only when triggered.

## Entrypoint Acceptance Map
Use this route's row in `../flowguard/references/route_execution_contract.md`; AGENTS.md managed; fake mini-frameworks forbidden. Progress and parent composition never replace child execution.

### Shared execution contract

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
- Model-purpose gate: task-specific failure(s); native good/bad-per-failure/oracle/current evidence; Reusable types are not fixed-purpose; no mode/fallback; FlowGuard check engine: only FlowGuard-declared checks may support completion claims.
- PID/log/progress proves liveness; reuse needs current `TestResultReuseTicket`/`ProofArtifactRef`. One receipt fans out only inside its boundary; copies are not executions.
- Require `planned = executed + not_run`, `failed <= executed`, no not-run under `declared_complete`, visible reasons, stable finding ids.
- Local green cannot prove completeness. Every item is executed or delegated; delegation needs one owner and current evidence.
- Resolve owners before execution: missing/stale=`execute`; exact-current pass=`reuse_current`; malformed/tampered/ambiguous/unknown-impact/in-flight=`blocked`.
- Persist each child once; later work executes only failed/stale owners and recomposes exact ids.
- One parent invocation verifies each current child once, derives aggregates from one observation, performs one final source check, batch-publishes leaves, and reconciles ids once. Never persist the observation or repeat per-leaf semantics/currentness/store scans.
- Verify evidence; never create necessity witnesses, select candidates, recompute Pareto dominance, or promote `normative_target`; deep members need current triggers.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, mesh diagram, owner, freshness, and blueprint depth/gap. Compact evidence preserves denominator, selected/executed/reused/not-run counts, fingerprints, negative cases, and omitted ids; parent owns release confidence after freeze.
