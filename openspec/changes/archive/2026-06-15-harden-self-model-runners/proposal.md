## Why

FlowGuard 0.48.0 hardened the public AI entry path, but FlowGuard's own
`.flowguard/*/run_checks.py` scripts can still call `Explorer(...)` directly.
That leaves a maintenance gap: adoption audit can warn about direct Explorer
usage, but self-owned model evidence has not fully moved to the formal
`FlowGuardCheckPlan` path with current known-bad proof.

## What Changes

- Add a reusable formal workflow-suite runner for repository self-models.
- Upgrade current `.flowguard` runner scripts that call `Explorer(...)`
  directly to use the formal runner.
- Keep `Explorer` as the internal finite engine behind the runner, not the
  script-level entrypoint.
- Keep historical fallback/compatibility records visible while preventing
  current self-model runner evidence from looking like a direct Explorer path.

## Impact

- Current `.flowguard` runner scripts must prove expected-bad workflows or
  explicit handled-bad labels before broad self-maintenance confidence.
- Adoption audit should no longer report direct Explorer warnings for current
  `.flowguard` runner scripts.
- Existing model state machines remain behavior-preserving; the upgrade changes
  the evidence entry path, not the modeled workflows.
