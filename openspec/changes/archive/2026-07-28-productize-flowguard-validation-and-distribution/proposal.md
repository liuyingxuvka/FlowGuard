## Why

FlowGuard has strong individual models and tests, but complete validation is slow, incompletely discovered, sometimes repository-mutating, and difficult to monitor, while skill installation and source/shadow/installed parity are not proven by one idempotent user-facing workflow. Validation and distribution need explicit manifests, safe execution tiers, concise output, and complete-tree synchronization before a release can be trusted.

## What Changes

- Add an explicit regression manifest covering every discovered FlowGuard model runner or an evidence-backed exclusion, including the currently omitted model without `run_checks.py` discovery.
- Add fast, focused, and full regression tiers with per-runner timeouts, progress events, filtering, sharding, bounded concurrency, output directories, cancellation, and a non-mutating default.
- Separate concise human summaries from stable JSON and full trace artifacts so default commands remain readable while preserving complete evidence.
- Add idempotent install, check, uninstall, and dry-run workflows for FlowGuard skills in temporary or real `CODEX_HOME` layouts.
- Compare complete source, formal-repository, shadow-workspace, and installed skill trees, including missing and extra files, with both raw and normalized semantic hashes.
- Make documentation bilingual and capability-complete, align product positioning, document the three-layer status model, and expose the safe validation/install command surface.
- Add a release closure workflow that freezes version, documentation, OpenSpec
  state, current model authority, and the installed consumer projection before
  exactly one final full parent gate. Commit, tag, and publication follow that
  gate; published verification compares immutable identities without rerunning
  heavy producers.
- Replace unconditional full-suite re-execution with a FlowGuard-native,
  content-addressed owner plan. Each validation owner or model is classified as
  `execute`, `reuse_current`, or `blocked` against one frozen source,
  toolchain, environment, check-inventory, and obligation snapshot.
- Compose a passing parent from independently verified exact-current terminal
  receipts, including a mixture of receipts produced in the current run and
  reusable receipts from earlier runs. Parent failure MUST preserve successful
  child receipts whose functional inputs remain current.
- Separate per-model instance identity from the model-system snapshot revision
  and Git provenance so a local model input change does not replace unrelated
  model identities while the sole-head CAS and whole-revision transaction stay
  authoritative.
- Replace release mtime freshness with two non-interchangeable frozen
  manifests: `ValidationInputManifest` owns exact functional validation inputs,
  while `ReleaseTreeManifest` owns the exact source-only Git tree. Bind the
  full parent receipt to both identities and compare commit, tag, and GitHub
  Release against the release-tree identity.
- Publish this breaking productization release as source-only `v0.64.0` with
  zero uploaded release assets.
- **BREAKING**: implicit `rglob("run_checks.py")` coverage, partial-file parity, repository-mutating default regressions, and branch-only release evidence cannot support full validation or release claims.
- **BREAKING**: global mtime freshness, Git-HEAD-derived child identity,
  run-local-only parent composition, and fallback-to-run-all for unknown impact
  mappings are removed from the current validation path.

## Capabilities

### New Capabilities

- `flowguard-model-regression-orchestration`: Defines explicit model registration, execution tiers, timeout/progress/shard behavior, mutation policy, and terminal receipts.
- `flowguard-validation-command-surface`: Defines concise human output, canonical JSON, full artifacts, exit/status semantics, and composable suite validation commands.

### Modified Capabilities

- `flowguard-skill-suite-distribution`: Requires idempotent lifecycle commands and complete-tree source/shadow/installed parity before distribution claims.
- `long-check-observability`: Extends progress, timeout, cancellation, and final-receipt behavior to model regression shards and background execution.

## Impact

Affected surfaces include model regression scripts and manifests, validation
CLIs, owner-impact planning, immutable receipt storage and verification,
model-system instance identity, output/report schemas,
installer/synchronization utilities, distribution tests, README and concept
documentation, local installation, version/release workflows, and
post-publication verification. This final change depends on the first, third,
and fourth changes and consumes their inventory, contract, and receipt formats;
it does not redefine route ownership or self-governance status semantics.
