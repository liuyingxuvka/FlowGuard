---
name: flowguard-test-mesh
description: Use when tests or evidence are large, layered, stale, skipped, release-only, or need parent/child ownership.
---

# FlowGuard Test Mesh

## Purpose
Govern parent/child test hierarchy, validation partitions, results, and freshness.

## Entrypoint Scope
This standalone FlowGuard satellite skill gives `test_mesh_maintenance` evidence structure, not semantics, process shape, or execution.

## Local Material Routing
Read `references/test_mesh_protocol.md` for ownership, diagnostics, reuse, matrices, and release scope.

## Entrypoint Acceptance Map
Review a model-derived validation mesh; block stale, skipped, incomplete, or unowned evidence; hand semantics and lifecycle/risk to typed owners.

## Use When
- Large/slow/background child test scripts, stale/reused evidence, release gates, artifact-payload matrices, or diagnostic boundaries.

## Do Not Use When
- Do not split code/models, choose DPF shape, group root causes, decide semantics, or execute tests; send small tests to `flowguard`.

## Required Workflow
1. Define the parent gate and derive child suites/scripts from a FlowGuard validation-structure model.
2. Declare an independent inventory revision and every required surface, obligation, member, cell, case, and shard; map each id to one owner.
3. Attach status, freshness, artifacts, reuse, terminal identity, fingerprints, coverage, and versions. Record planned/executed/failed/not-run counts and stable finding ids. Provider context is not test evidence.
4. For long checks, bind inputs and traces in `ProofArtifactRef.artifact_fingerprints`; progress is liveness only.
5. Review routine/release scope and return child evidence plus typed handoffs.

## Hard Gates
- Model-purpose gate: freeze this instance's task-specific failure(s)/boundary and bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; only FlowGuard-declared checks may support completion claims.
- Use the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- PID/log/running/progress proves liveness only; reuse requires current `TestResultReuseTicket` and `ProofArtifactRef`.
- One test receipt may fan out only within its declared boundary; never count copies as executions.
- Require `planned = executed + not_run`, `failed <= executed`, no not-run under `declared_complete`, visible reasons elsewhere, and stable finding ids for failures.
- Locally green subsets cannot prove a declared complete inventory. Every required item has one executed or delegated disposition; delegation needs one native owner and current evidence.
- Reuse requires an independent terminal producer receipt whose owner and current fingerprints match.
- Resolve every owner before execution: missing/stale=`execute`; exact-current pass=`reuse_current`; malformed/tampered/ambiguous/unknown-impact/in-flight=`blocked`.
- Persist each successful child immediately. Parent/sibling failure cannot erase it; later requests execute only failed/stale owners and recompose from exact child ids/fingerprints.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, `typed_next_actions`, a validation mesh diagram, and child freshness.
