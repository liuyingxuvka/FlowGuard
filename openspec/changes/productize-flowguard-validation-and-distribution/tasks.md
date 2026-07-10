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

## 7. Run Local Full Closure

- [x] 7.1 Run the complete pytest suite and fix all failures without weakening hard or known-bad assertions.
- [x] 7.2 Run manifest audit and the full model tier in non-mutating mode, preferably as monitored background work, until every required model has a current terminal pass receipt.
- [ ] 7.3 Run the unified full validation, all five OpenSpec verification contracts, 17/17 SkillGuard checks, project audit, self-review/conformance, complete-tree parity, and privacy/repository-boundary checks.
- [x] 7.4 Re-run any evidence invalidated by final edits and require zero required stale, skipped, not-run, pass-with-gaps, partial, or unconsumed receipts.

## 8. Version And Synchronize

- [x] 8.1 Select the next semantic version from the completed impact and update package metadata, project manifest, managed adoption block, changelog, README/version references, and release notes consistently.
- [x] 8.2 Build/check the package, refresh the editable local installation, install/check all seventeen local Codex skills, and prove source/formal/shadow/installed complete-tree parity.
- [ ] 8.3 Commit the completed changes in reviewable units, confirm a clean working tree, and create the immutable release tag only after `check.release.local` passes.

## 9. Publish And Post-Verify

- [ ] 9.1 Push the release commit and tag to the configured GitHub repository and create the new GitHub Release with notes and required assets.
- [ ] 9.2 Run `check.release.remote` against the published tag/assets and rerun the full release verification contract after publication.
- [ ] 9.3 If remote verification fails, keep release closure incomplete and prepare a new corrective version; do not move or overwrite the published tag.
- [ ] 9.4 Record local and remote receipts, final residual risk, skipped checks, claim boundary, and released version; only then mark the productization change and overall release complete.
