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
- Make affected-only validation executable rather than advisory while retaining
  exact freshness and fail-closed behavior.
- Preserve one immutable proof chain from two frozen manifest identities
  through child receipts, parent composition, commit, tag, and GitHub Release.

**Non-Goals:**

- Redefine suite membership, route owners, prompt contracts, or receipt semantics.
- Replace pytest, FlowGuard's formal runner, or SkillGuard.
- Restore the retired OpenSpec provider/work-package receipt bridge.
- Keep a compatibility reader, dual identity, mtime fallback, or automatic
  run-all fallback for unmapped inputs.
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

### 5. Release has one final execution gate and a lightweight publication phase

All source-bearing release decisions finish before the final gate: package and
project version `0.64.0`, changelog and release documentation, OpenSpec state,
the selected current model-authority head and revision closure, the compiled
consumer projection and installed-skill parity, and the source-only zero-asset
publication policy. The release owner then freezes the validation-input and
release-tree manifests plus the exact owner plan.

Exactly one final full parent gate runs for that frozen pair. It executes only
stale or missing owners, reuses independently verified exact-current receipts,
and MUST NOT mutate either manifest. After it passes, the release owner compares
the staged tree to the frozen release tree, creates the commit and immutable
`v0.64.0` tag, pushes them, and publishes a source-only GitHub Release with zero
uploaded assets. Published verification is a read-only comparison of receipt,
commit, local/remote tag, release target, tree, version, and asset count; it
MUST NOT rerun the heavy validation producers.

### 6. Documentation is generated from canonical inventories where practical

README English/Chinese skill tables and command references consume the suite and command metadata. `docs/concept.md` adopts the current "AI-agent skill suite powered by an executable check engine" positioning. Docs explain the three-layer status model and distinguish summary output from validation evidence.

### 7. A frozen owner plan controls real execution

Before starting a child command, the unified validator freezes the exact
`ValidationInputManifest`, including functional source identities, current
model authority, toolchain, environment, check inventory, obligation inventory,
dependency graph, installed consumer projection, and one execution owner per
check. It independently resolves and verifies prior receipts, then assigns each
owner exactly one disposition:

- `execute`: no exact-current terminal-success receipt exists;
- `reuse_current`: an independently verified receipt matches every functional
  identity and covered obligation;
- `blocked`: the owner, input mapping, dependency, environment, or receipt
  identity is missing, ambiguous, stale, or invalid.

`--plan-only` materializes this plan and executes no validation producer.
Unknown or unmapped inputs block. They never silently widen to run-all.

### 8. Parent validation composes receipts across runs

The full parent gate proves coverage of the frozen owner inventory, not that
every child process started in the current invocation. The parent may compose
current-run and earlier exact-current terminal receipts after independent
current-context verification. A failed parent does not revoke successful child
receipts. After a focused repair, only owners whose functional identities
changed execute again.

Equivalent concurrent requests use single-flight ownership: one producer runs
and other callers wait for and independently verify its immutable receipt.
Timeout, cancellation, or interruption remains non-reusable until the complete
descendant process tree is confirmed stopped.

### 9. Model identity is local; snapshot identity is global

A model instance fingerprint contains only the logical model id, model content,
runner, declared local inputs, purpose binding, and schema/tool identities that
the instance actually consumes. Git revision and the union of all model inputs
are snapshot-level provenance and MUST NOT be copied into every model instance
fingerprint.

The observed snapshot still has one global source revision, one sole head, and
one atomic `ModelRevisionSet`. A candidate local change replaces only the
affected model instances and declared relation closure; activation remains a
whole-revision CAS transaction. The migration is direct-to-current with no
dual reader or old-identity success path.

### 10. Release freshness uses two explicit content manifests

`ValidationInputManifest` is the functional-validation boundary. For every
owner it records exact governed source/content identities, the selected current
model-authority head and revision closure, request and purpose, toolchain,
environment policy and observed environment, check and obligation inventories,
dependencies, consumer projection/install identity, and execution owner.
Logs, reports, receipts, progress files, adoption records, and pointer writes
are outputs unless an owner explicitly declares their content as a functional
input.

`ReleaseTreeManifest` is the publication boundary. It records every canonical
relative path in the source-only tag tree together with Git mode and raw
content/blob identity, plus release version and the zero-uploaded-asset policy.
It detects missing, extra, ignored, or untracked files that are declared
required for the public release. It does not absorb local-only environment,
toolchain, installed-projection, or receipt identities.

The full parent receipt binds both manifest fingerprints. The release commit,
local and remote tags, and GitHub Release target compare against
`ReleaseTreeManifest`; child receipt reuse compares against
`ValidationInputManifest`. The two manifests MUST NOT be collapsed or treated
as substitutes. Filesystem mtimes never decide freshness: mtime-only touches do
not invalidate evidence, while content changes invalidate the exact affected
identity even when mtimes are preserved. A post-freeze change invalidates the
old parent gate and requires a new manifest pair and parent composition, but
only owners in the declared affected closure execute again.

### 11. Shadow comparison precedes current-path replacement

Before enabling affected-only execution as the sole current route, fixtures
compare the new plan with the declared legacy full inventory. Any missing
owner, obligation, dependency, or impact edge blocks activation. Once coverage
parity is demonstrated, the unconditional execution path and mtime freshness
authority are removed rather than retained as fallbacks.

## Risks / Trade-offs

- **[Risk] A stale receipt is reused incorrectly.** → Recompute current context
  independently and require exact source, request, dependency, toolchain,
  environment, owner, inventory, and obligation identities.
- **[Risk] An impact edge is missing.** → Unknown or unmapped inputs block the
  plan; shadow comparison must prove declared inventory coverage before the
  old unconditional path is removed.
- **[Risk] Full validation remains slow.** → Fast/focused tiers give development feedback; full closure composes exact-current receipts and executes only stale or missing owners.
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
6. Add the owner-plan/receipt resolver and parent composition path, then prove
   legacy-inventory coverage in shadow fixtures.
7. Direct-migrate model identity and release freshness to their content-bound
   current forms; remove old mtime, Git-child, and run-local-only authority.
8. Run invocation-count, tamper, environment, pointer, and concurrent-owner
   acceptance tests.
9. Finish every source-bearing change, set version `0.64.0`, finalize bilingual
   docs/changelog/release notes, freeze the productize OpenSpec state, select
   the current model-authority head and revision closure, compile/install the
   consumer suite, and prove complete-tree parity.
10. Freeze `ValidationInputManifest`, `ReleaseTreeManifest`, and the owner plan,
    then run exactly one final full parent gate with affected-only execution and
    exact-current receipt reuse.
11. Without changing either manifest, compare the staged tree, create the
    release commit and immutable `v0.64.0` tag, push both, and publish a
    source-only GitHub Release with zero uploaded assets.
12. Perform read-only remote tag/tree/release/receipt comparison without heavy
    re-execution and record the terminal publication receipt.

Rollback before publication reverts the work package. After publication, use a new corrective version; never move or overwrite the published tag.

## Open Questions

- None for release identity or ordering: this change targets source-only
  `v0.64.0`, and every source-bearing release identity is frozen before the
  unique final full gate.
