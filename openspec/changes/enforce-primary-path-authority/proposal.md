## Why

AI-assisted maintenance can leave long-lived fallback paths, compatibility
wrappers, backup field reads, helper routes, and silent "A failed, B succeeded"
runtime behavior. FlowGuard already has pieces that detect old-path
disposition, business-path hazards, runtime evidence gaps, field lifecycle
gaps, ContractExhaustionMesh coverage, TestMesh evidence, and Risk Evidence
Ledger closure, but those controls are distributed rather than enforced as one
default rule.

This change makes the intended policy explicit: for each business intent,
FlowGuard must identify one primary runtime authority, fail closed when that
path fails, and force every alternate or compatibility surface to be deleted,
blocked, migrated, delegated to the primary path, or proven as a thin bounded
facade.

## What Changes

- Add a new `primary-path-authority` capability that reviews business intent,
  primary runtime ownership, fallback candidates, failure policy, disposition,
  coverage receipts, and final findings.
- Require runtime evidence to preserve primary-path failure and fallback
  invocation signals instead of allowing silent alternate success.
- Extend business-path topology review so duplicate or alternate authorities
  for the same business intent are visible and block broad confidence.
- Tie old path, alias, wrapper, helper route, compatibility facade, old field,
  backup cache, migration, and manual recovery surfaces to explicit
  disposition values.
- Require model-scoped Cartesian coverage for the primary-path authority
  boundary: declared finite axes, interaction groups, generated case ids,
  oracles, shard ids, coverage receipts, and downstream TestMesh/Risk Ledger
  consumption.
- Add public API, CLI template, route registry, docs, and Codex skill guidance
  so new projects inherit the rule without the user repeating it manually.
- Keep existing compatibility only when explicitly classified and currently
  evidenced as external facade, manual recovery, or migration-only. Automatic
  "primary failed -> alternate returns success" behavior is rejected.

## Capabilities

### New Capabilities
- `primary-path-authority`: Declares and checks the one-business-intent,
  one-primary-runtime-authority rule; classifies fallback candidates;
  verifies fail-closed behavior; and exposes coverage, TestMesh, and risk
  ledger handoff ids.

### Modified Capabilities
- `runtime-path-evidence`: Runtime observations must record primary failure,
  fallback invocation, and fallback success masking signals for path-sensitive
  claims.
- `risk-evidence-ledger`: Final done/release/full confidence rows can require
  primary-path authority and its Cartesian coverage receipts.
- `contract-exhaustion-mesh`: Primary-path authority plans must be able to
  declare finite axes and interaction groups that produce canonical
  no-fallback combination cases.
- `test-evidence-mesh`: Parent test gates must consume primary-path Cartesian
  coverage shards through child suite evidence.
- `architecture-reduction`: Compatibility/fallback/helper surfaces must be
  reduced or given explicit non-authoritative disposition before broad claims.
- `field-lifecycle-mesh`: Old, renamed, alias, compatibility, and backup fields
  must not remain as hidden fallback reads without a closing disposition.
- `post-runtime-model-miss-review`: Bug repair closure must repair the primary
  path instead of adding or preserving alternate success paths.
- `flowguard-api-registry`: The new route must be discoverable through grouped
  public APIs and starter APIs without exposing internal helpers as route
  owners.
- `flowguard-codex-skill-satellites`: Agent-facing skills must prompt agents
  to enumerate runtime paths, classify compatibility surfaces, reject silent
  fallback, and require Cartesian coverage before broad confidence.
- `development-process-flow`: Staged implementation, install sync, and final
  claims must treat primary-path authority evidence as a freshness-sensitive
  validation gate.

## Impact

- Adds a core module, public APIs, route registry entries, CLI/template output,
  OpenSpec artifacts, FlowGuard self-model evidence, and tests for primary path
  authority.
- Updates runtime path evidence, topology hazard review, risk evidence ledger,
  architecture reduction, field lifecycle, and model-miss review integrations.
- Adds ContractExhaustionMesh coverage-universe tests and TestMesh child-shard
  tests for the no-fallback matrix.
- Updates AGENTS/docs/skill prompts and requires installed skill/local package
  sync verification after implementation.
