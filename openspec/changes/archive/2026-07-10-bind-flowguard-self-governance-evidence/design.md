## Context

The self-maintenance model currently has transitions that set child-report/current/coverage flags together, while its runner constructs passing child reports in memory. `SelfMaintenanceChildReport` has no mandatory evidence identity, timestamp, or fingerprint. Formal summary logic can treat `pass_with_gaps` as observed success, allowing a locally scoped result to satisfy a broader parent expectation.

This change starts only after canonical suite membership, typed ownership, and all seventeen deep contracts are available. It turns those artifacts into freshness-bound evidence and makes the parent consume them exactly.

## Goals / Non-Goals

**Goals:**

- Define immutable, verifiable evidence receipts and deterministic freshness.
- Remove authoritative caller-supplied pass/current fields.
- Make parent completion depend on exact current child receipts and covered obligations.
- Backfill suite-wide behavior commitments and model/test evidence.
- Ensure partial, skipped, stale, or scoped results cannot become broad green claims.

**Non-Goals:**

- Schedule all model runners or optimize background execution.
- Install, sync, document, version, or publish the package.
- Change skill prompt contracts or route ownership.
- Store raw private inputs in receipts.

## Decisions

### 1. Receipts are immutable facts; eligibility is derived

Add an `EvidenceReceipt` schema containing receipt id, subject id/kind, producer id/version, claim scope, exact command, working-directory token, timestamps, exit code, environment fingerprint, contract/check/suite hashes, input snapshots, proof artifact/result fingerprint, covered obligations, required/consumed child receipts, skipped checks, blockers, and claim boundary.

Receipts do not store authoritative `current`. A verifier recomputes freshness and status eligibility from current inputs. Paths are tokenized; hashes and safe metadata are stored instead of raw sensitive content.

### 2. Raw and semantic hashes serve different purposes

Input snapshots may carry raw SHA-256 and normalized semantic SHA-256. Raw hashes prove byte-identical distribution; semantic hashes prevent line-ending-only invalidation where the contract permits it. Each obligation declares which comparison is required.

### 3. Parent ModelMesh consumes exact receipt ids

The self-maintenance parent declares required child subjects and obligation ids. It can transition only when each exact child receipt exists, verifies, is current, covers its obligation, and appears in `consumed_child_receipts`. A newer required child invalidates parent closure until re-consumed.

### 4. Broad status uses strict lattice semantics

For a `full` claim, only terminal exact `pass` can satisfy a required child. `pass_with_gaps`, `scoped`, `stale`, `skipped`, `not_run`, `progress_only`, and `blocked` remain visible and cannot be promoted. Formal runner expectations must declare an allowed scope/status explicitly; default expected success means exact pass.

### 5. Behavior commitments define the suite's externally visible obligations

Run BCL in `coverage_gap_backfill` over README/docs, CLI, prompts, route registry, contracts, model checks, installer/distribution surfaces, and project adoption. Every commitment has one primary owner model, source-to-commitment and commitment-to-source mappings, dependency receipts, CEM negative cases, and TestMesh shards. Helper fields are not automatically commitments.

### 6. Evidence is stored outside installed skill packages

Current receipts live under `.flowguard/evidence/skill-suite/` (or a configured output directory) and are not shipped as current truth inside installed skills. Schemas and check manifests may be distributed; run results are environment-local.

## Risks / Trade-offs

- **[Risk] Hash invalidation makes many checks rerun.** → Use obligation-scoped input sets and minimum revalidation; never broaden reuse beyond declared scope.
- **[Risk] Environment fingerprints leak machine details.** → Hash normalized allowlisted attributes and tokenize paths.
- **[Risk] Legacy reports become unusable.** → Provide a read-only diagnostic importer that classifies them as unbound historical evidence, never current full evidence.
- **[Risk] Parent closure is initially red.** → This is expected until every required child produces a current receipt; do not seed synthetic green receipts.

## Migration Plan

1. Add receipt schema, verifier, storage, path tokenization, and known-bad tests.
2. Emit receipts from one child contract check and prove invalidation behavior.
3. Backfill BCL commitments and suite-level MTA/TestMesh mappings.
4. Replace synthetic self-maintenance transitions and runner fixtures with child receipt loading.
5. Tighten formal status semantics and update scoped test expectations explicitly.
6. Run known-bad universe, focused models, then full parent closure.

Rollback may restore old reporting only as historical/scoped output; it must not restore synthetic full-pass authority.

## Open Questions

- None for schema ownership. Exact environment allowlist is chosen during implementation and locked by privacy tests before receipts are generated broadly.
