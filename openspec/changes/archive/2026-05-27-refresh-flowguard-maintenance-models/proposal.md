## Why

Recent FlowGuard self-audit found maintenance candidates that were already
implemented in the source tree but still appeared as active architecture
reduction or structure simplification candidates. That makes future agents
spend time re-proving completed work and can blur the release confidence
boundary between source changes, shadow workspace cleanup, and install sync.

## What Changes

- Treat implemented architecture-reduction candidates as closed evidence or
  historical context, not as current ready-to-execute candidates.
- Keep shadow-only duplicate `.flowguard` cleanup inside the local sync and
  release-readiness evidence boundary instead of reporting it as package
  behavior evidence.
- Require release confidence for this maintenance pass to include current
  model checks, focused/full regressions, editable install verification, and
  shadow workspace verification.

## Impact

- Affects `.flowguard` maintenance models and their run artifacts.
- May affect release metadata and local install/shadow sync.
- Does not intentionally change public FlowGuard runtime behavior, CLI
  commands, public imports, or model APIs.
