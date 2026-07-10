## Context

Model regression discovery currently relies on finding `run_checks.py`, which omits at least one executable model. The aggregate run lacks per-runner timeouts, tier/filter/shard controls, and a declared mutation contract; historical full runs take roughly eleven minutes and have timed out. Validation examples emit tens of thousands of characters by default. Distribution verification compares only a subset of files even though complete source, formal, shadow, and installed trees must agree.

This final productization change consumes canonical inventory, generated contracts, and evidence receipts. It is the only change in this program that owns model-run orchestration, install lifecycle, complete-tree parity, documentation polish, versioning, and release closure.

## Goals / Non-Goals

**Goals:**

- Register every model runner or explicit exclusion in a manifest.
- Provide safe, observable, tiered, shardable validation with terminal receipts.
- Provide concise human output and canonical JSON/full artifacts.
- Make skill install/check/uninstall/dry-run idempotent and layout-neutral.
- Prove complete-tree parity across source, formal, shadow, and installed copies.
- Align bilingual documentation and require post-publication verification before release closure.

**Non-Goals:**

- Redefine suite membership, route owners, prompt contracts, or receipt semantics.
- Replace pytest, FlowGuard's formal runner, or SkillGuard.
- Publish before all prerequisite changes and verification contracts pass.

## Decisions

### 1. A checked-in manifest owns model regression inventory

Add `.flowguard/model-regression-manifest.json` with model id, runner command, tier, timeout, shard-safety, mutation policy, input globs, expected artifacts, and explicit exclusion reason if applicable. A discovery audit compares every model directory and executable model entry to the manifest in both directions.

Implicit `rglob` remains only as a discovery diagnostic, not execution authority.

### 2. Execution tiers share one orchestrator

`flowguard/model_regressions.py` and a thin script support `--tier fast|focused|full`, `--model`, `--shard`, `--jobs`, `--timeout`, `--output-dir`, `--json`, and cancellation. Each runner gets its own process, timeout, progress events, stdout/stderr artifact, and terminal receipt. Parallel execution is allowed only when manifest entries are shard-safe and output-isolated.

Default mode is non-mutating. A runner declared mutating is blocked unless a separate explicit flag and isolated output/worktree policy are provided.

### 3. One result model drives human and machine output

Commands build a canonical result object. Human default shows status, counts, first actionable failures, blockers, skipped checks, residual risk, claim boundary, and artifact paths. `--json` emits encoding-stable machine output; `--full` exposes or points to full traces without changing result semantics.

### 4. Distribution lifecycle is declarative and idempotent

Add installer/auditor logic with source and target roots, dry-run plan, copy/delete disposition, and safe path validation. Install repeats without changes; check is read-only; uninstall removes only files owned by the recorded manifest. Temporary `CODEX_HOME` tests are mandatory.

Complete-tree parity compares relative path sets, raw hashes, semantic hashes where allowed, and extra/missing files for `.agents/skills`, formal repository, shadow workspace, and installed copy. Current run receipts are excluded by explicit policy, not by accident.

### 5. Release is a two-phase verified operation

Local release readiness requires all five OpenSpec verification contracts, full tests, full model tier, 17/17 deep contracts, complete parity, and clean repository/privacy checks. After tag and GitHub release publication, rerun the release verification contract against the published tag/assets and record remote receipts. Only then mark release complete.

### 6. Documentation is generated from canonical inventories where practical

README English/Chinese skill tables and command references consume the suite and command metadata. `docs/concept.md` adopts the current "AI-agent skill suite powered by an executable check engine" positioning. Docs explain the three-layer status model and distinguish summary output from validation evidence.

## Risks / Trade-offs

- **[Risk] Full validation remains slow.** → Fast/focused tiers give development feedback; only full tier supports release claims.
- **[Risk] Parallel runners contend for shared resources.** → Default concurrency is conservative and manifest-gated; unsafe entries run serially.
- **[Risk] Uninstall deletes user files.** → Remove only paths recorded as installer-owned and unchanged from their installed hash; otherwise report conflict.
- **[Risk] Cross-platform line endings cause false parity failures.** → Raw equality remains required for release-owned files; semantic hash is reported separately and cannot mask raw mismatch where byte parity is required.
- **[Risk] Remote publication succeeds but post-check fails.** → Release remains incomplete and a corrective release is prepared; do not rewrite an immutable tag.

## Migration Plan

1. Add manifest/audit and register all current models.
2. Build the orchestrator and migrate the old runner to a thin compatibility command.
3. Add result projection and shorten example defaults.
4. Add installer/auditor/uninstaller with temporary-home tests and complete-tree parity.
5. Update bilingual docs and command examples from canonical metadata.
6. Run local full closure, bump version/changelog, sync/install, tag and publish.
7. Run post-publication verification and record final receipts.

Rollback before publication reverts the work package. After publication, use a new corrective version; never move or overwrite the published tag.

## Open Questions

- The final version number is selected at release time from the completed change impact and existing version history; the verification contract forbids publishing until that decision is recorded consistently in package, manifest, changelog, tag, and release metadata.
