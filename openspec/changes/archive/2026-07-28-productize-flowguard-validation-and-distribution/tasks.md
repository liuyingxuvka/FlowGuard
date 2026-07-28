## 1. Confirm All Prerequisite Governance

- [x] 1.1 Verify the adoption, topology, skill-contract, and evidence-bound self-governance changes and their verification contracts are current and passing.
- [x] 1.2 Record the canonical suite, route, contract, receipt-schema, and full-self-governance hashes consumed by productization.

## 2. Build Complete Model Regression Inventory

- [x] 2.1 Add `.flowguard/model-regression-manifest.json` and register every discovered model directory/executable entry, including the model currently omitted by `run_checks.py` discovery.
- [x] 2.2 For each model declare runner, tier, timeout, shard safety, mutation policy, watched inputs, expected artifacts, and an explicit verified exclusion when not executable.
- [x] 2.3 Add `tests/test_model_regression_manifest.py` for missing/extra model records, omitted executable main, invalid runner, unjustified exclusion, and discovery/manifest parity.

## 3. Implement Safe Observable Regression Orchestration

- [x] 3.1 Implement `flowguard/model_regressions.py` and refactor `scripts/run_flowguard_model_regressions.py` to use the manifest with fast/focused/full tiers, filters, shards, bounded jobs, and output directory.
- [x] 3.2 Run every child with per-runner timeout, isolated stdout/stderr/artifacts, cancellation, progress events, and terminal evidence receipt.
- [x] 3.3 Enforce non-mutating default by snapshotting tracked state and rejecting undeclared writes; serialize unsafe/shared-output models.
- [x] 3.4 Add `tests/test_model_regression_orchestrator.py` and `tests/test_long_check_observability.py` for timeout, cancellation, missing terminal, unsafe parallelism, tracked mutation, tier claim boundary, and background progress.

## 4. Productize Validation Output

- [x] 4.1 Add one canonical validation-result model and stable exit/status codes for pass, fail, blocked, invalid input, timeout/cancelled, and internal error.
- [x] 4.2 Make default human output concise while preserving complete traces in explicit artifacts or `--full`; keep `--json` encoding-stable and localization-neutral.
- [x] 4.3 Implement/update `scripts/check_flowguard_skill_suite.py` to compose project audit, inventory, 17 SkillGuard checks, self-governance, models, tests, OpenSpec, and distribution without flattening child receipts.
- [x] 4.4 Add `tests/test_validation_command_surface.py`, including large-output, JSON-only, partial-status, skipped-required-check, and one-child-failure fixtures.

## 5. Implement Idempotent Distribution Lifecycle

- [x] 5.1 Implement distribution ownership metadata and `flowguard/distribution_sync.py` for safe source/target planning, path validation, hash comparison, conflict handling, and complete relative-tree inventory.
- [x] 5.2 Implement `scripts/install_flowguard_skills.py` install, check, uninstall, dry-run, temporary-home lifecycle, and configured-target parity modes.
- [x] 5.3 Compare complete source, formal repository, shadow workspace, and installed trees, reporting missing/extra/raw/semantic mismatch and explicit receipt exclusions separately.
- [x] 5.4 Add `tests/test_distribution_sync.py` and `tests/test_skill_installer.py` for repeated install, read-only check, safe uninstall, modified-user-file conflict, extra obsolete file, reference layout, and partial-file false parity.

## 6. Align Documentation And User Experience

- [x] 6.1 Generate or parity-check English and Chinese seventeen-skill tables so Behavior Commitment Ledger and all routes appear in both languages.
- [x] 6.2 Update README and `docs/concept.md` to the current skill-suite-plus-executable-engine positioning and explain the three-layer governance status.
- [x] 6.3 Document fast/focused/full validation, concise/JSON/full output, background monitoring, install/check/uninstall/dry-run, evidence artifacts, and claim boundaries.
- [x] 6.4 Add documentation/command examples tests that fail on stale skill membership, version, or unsupported arguments.

## 7. Freeze Exact Owner And Impact Identities

- [x] 7.1 Define the canonical governed-source, toolchain, environment-policy,
  check-inventory, obligation-inventory, dependency, and execution-owner
  fingerprints for every unified-suite child.
- [x] 7.2 Implement a fail-closed component-to-owner impact graph with exact
  affected closure; unmapped or ambiguous functional inputs block and never
  fall back to run-all.
- [x] 7.3 Add plan-only output with one `execute`, `reuse_current`, or
  `blocked` disposition and reason per owner, with zero producer execution.

## 8. Implement Immutable Receipt Resolution And Composition

- [x] 8.1 Add native receipt producers/adapters for model regression, full
  pytest, and every unified-suite child using one canonical immutable schema.
- [x] 8.2 Independently recompute current context before reuse, including
  source, request, dependencies, toolchain, environment, owner, inventory,
  obligations, terminal result, result artifact, and content hash.
- [x] 8.3 Compose a parent across current-run and prior-run exact-current
  receipts, preserving successful child receipts after sibling or parent
  failure.
- [x] 8.4 Enforce single-flight execution for identical owner identities and
  block reuse after timeout/cancellation/interruption until descendant cleanup
  is confirmed.

## 9. Make Model Reuse Local And Exact

- [x] 9.1 Direct-migrate model instance identity to local model, runner,
  declared-input, purpose, and consumed-tool identities; keep global source
  revision and Git revision only at snapshot provenance.
- [x] 9.2 Add per-model receipt resolution so a full model gate executes only
  stale/missing affected models and composes all current model receipts.
- [x] 9.3 Preserve the sole observed head, whole `ModelRevisionSet`, affected
  relation/sibling closure, immutable records, and pointer-last CAS activation.
- [x] 9.4 Remove the old global-subject-in-every-instance identity path with
  no compatibility or dual-reader success route.

## 10. Bind Release Freshness To Two Manifests

- [x] 10.1 Implement `ValidationInputManifest` with exact owner-scoped
  functional source, current model-authority closure, request, toolchain,
  environment, inventory, obligation, dependency, consumer-install, and owner
  identities; exclude evidence outputs unless explicitly consumed.
- [x] 10.2 Implement `ReleaseTreeManifest` with every source-only tag-tree
  relative path, Git mode, raw content/blob identity, version `0.64.0`, and
  zero-uploaded-asset policy; block required-public ignored or untracked files.
- [x] 10.3 Bind the final parent receipt to both manifest fingerprints while
  comparing commit, tag, and GitHub Release only to `ReleaseTreeManifest`;
  never collapse or substitute the two manifests.
- [x] 10.4 Remove mtime and run-local-only authority after shadow coverage
  parity passes; do not retain fallback logic.

## 11. Direct-Migrate Historical Residuals

- [x] 11.1 Remove the active verification-contract bridge that invoked retired
  `python -m flowguard spec-check-run`; the current full validation owner plan
  is the sole execution authority.
- [x] 11.2 Audit the active/archive duplicate provider-work-package history and
  record only this change's read-only WorkContext disposition; do not migrate
  or edit the other active change and do not restore a provider execution or
  receipt bridge.
- [x] 11.3 Close this productization change's residuals honestly and leave
  independently owned active-change status with its owner.

## 12. Prove Physical Execution Reduction

- [x] 12.1 Add invocation-count tests proving an identical second full run
  starts zero heavy producers and one local owner/model change executes only
  its exact affected closure.
- [x] 12.2 Prove one child failure/repair reruns only that child, parent failure
  preserves successful receipts, and concurrent identical requests start one
  producer.
- [x] 12.3 Prove mtime-only, log/report/receipt, and pointer-output changes do
  not stale source evidence, while content/toolchain/environment/check
  inventory changes expand the exact declared closure.
- [x] 12.4 Prove unknown mappings, stale heads, tampered receipts, environment
  mismatch, missing descendants cleanup, and tag/receipt/content mismatch
  block.
- [x] 12.5 Record executed/reused/blocked counts, actual invocations, wall
  time, and avoided-work estimates without using telemetry as freshness input.

## 13. Freeze, Run Once, Tag, And Publish

- [x] 13.1 Run shadow owner-plan coverage comparison, activate the direct
  current path and remove legacy/fallback authority.
- [x] 13.2 Run focused tests, affected models, SkillGuard author supervision
  for managed skill edits, and independent receipt/tamper
  verification; fix every in-scope failure before release freeze.
- [ ] 13.3 Select the sole current model-authority head and complete selected
  revision closure, affected-sibling review, and pointer-last activation before
  release freeze.
- [x] 13.4 Apply version `0.64.0` consistently across package/project metadata,
  managed records, bilingual docs, changelog, skills, and release notes, and
  finalize the source-only zero-uploaded-asset policy.
- [x] 13.5 Strict-validate, sync, and freeze this productize OpenSpec change;
  do not migrate or edit any other active change.
- [x] 13.6 Compile the final consumer projection, refresh the editable package
  and installed seventeen-skill suite, and prove
  source/formal/shadow/installed complete-tree parity.
- [ ] 13.7 Freeze `ValidationInputManifest`, `ReleaseTreeManifest`, and the
  exact owner plan only after tasks 13.1–13.6 are complete; any later change to
  either manifest invalidates the release gate.
- [ ] 13.8 Run exactly one final full parent gate for the frozen manifest pair,
  executing only stale or missing owners and reusing independently verified
  exact-current receipts; require zero source mutation and complete terminal
  coverage.
- [ ] 13.9 After the gate passes, permit only explicitly excluded evidence
  outputs, compare the staged tree to `ReleaseTreeManifest`, create the release
  commit and immutable `v0.64.0` tag, and make no source-bearing edits.
- [ ] 13.10 Push the release commit and tag, publish a source-only GitHub
  Release with zero uploaded assets, and perform read-only remote
  tag/tree/version/receipt/install comparison with zero heavy producer
  execution; mismatch keeps closure incomplete and requires a corrective
  version.
