## Why

FlowGuard has strong individual models and tests, but complete validation is slow, incompletely discovered, sometimes repository-mutating, and difficult to monitor, while skill installation and source/shadow/installed parity are not proven by one idempotent user-facing workflow. Validation and distribution need explicit manifests, safe execution tiers, concise output, and complete-tree synchronization before a release can be trusted.

## What Changes

- Add an explicit regression manifest covering every discovered FlowGuard model runner or an evidence-backed exclusion, including the currently omitted model without `run_checks.py` discovery.
- Add fast, focused, and full regression tiers with per-runner timeouts, progress events, filtering, sharding, bounded concurrency, output directories, cancellation, and a non-mutating default.
- Separate concise human summaries from stable JSON and full trace artifacts so default commands remain readable while preserving complete evidence.
- Add idempotent install, check, uninstall, and dry-run workflows for FlowGuard skills in temporary or real `CODEX_HOME` layouts.
- Compare complete source, formal-repository, shadow-workspace, and installed skill trees, including missing and extra files, with both raw and normalized semantic hashes.
- Make documentation bilingual and capability-complete, align product positioning, document the three-layer status model, and expose the safe validation/install command surface.
- Add a release closure workflow that reruns the full verification contract after local sync and again after GitHub tag/release publication; publication receipts are necessary but not sufficient.
- **BREAKING**: implicit `rglob("run_checks.py")` coverage, partial-file parity, repository-mutating default regressions, and branch-only release evidence cannot support full validation or release claims.

## Capabilities

### New Capabilities

- `flowguard-model-regression-orchestration`: Defines explicit model registration, execution tiers, timeout/progress/shard behavior, mutation policy, and terminal receipts.
- `flowguard-validation-command-surface`: Defines concise human output, canonical JSON, full artifacts, exit/status semantics, and composable suite validation commands.

### Modified Capabilities

- `flowguard-skill-suite-distribution`: Requires idempotent lifecycle commands and complete-tree source/shadow/installed parity before distribution claims.
- `long-check-observability`: Extends progress, timeout, cancellation, and final-receipt behavior to model regression shards and background execution.

## Impact

Affected surfaces include model regression scripts and manifests, validation CLIs, output/report schemas, installer/synchronization utilities, distribution tests, README and concept documentation, local installation, version/release workflows, and post-publication verification. This final change depends on the first, third, and fourth changes and consumes their inventory, contract, and receipt formats; it does not redefine route ownership or self-governance status semantics.
