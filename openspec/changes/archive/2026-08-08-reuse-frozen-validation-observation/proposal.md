## Why

FlowGuard currently preserves strict evidence freshness, but several model-regression and model-revision operations rebuild and re-verify the same complete repository manifest, receipt inventory, child closure, and owner bundle many times inside one already frozen operation. On the current 51-model self-maintenance boundary this turns a logically bounded verification into many minutes of repeated work, consumes unnecessary AI/tool time, and obscures which checks are genuinely independent.

## What Changes

- Introduce one explicit invocation-local frozen validation observation that contains the exact repository-input manifest, receipt inventory, resolved owner contexts, and verified child identities needed by a bounded operation.
- Permit sibling owner aggregations and parent composition inside that same operation to reuse the exact observation instead of rebuilding the same global evidence graph per child or per owner.
- Preserve fail-closed behavior: unknown impact, stale source, changed receipt inventory, duplicate owner, missing child, non-terminal result, or fingerprint drift still blocks.
- Require one fresh post-operation observation before a parent, revision bundle, activation, or release claim becomes current; the fresh observation must match the frozen identities actually consumed.
- Keep reuse invocation-local and non-authoritative: no persistent cache, compatibility reader, fallback result, alternate receipt store, or cross-invocation trust is introduced.
- Make terminal reporting distinguish useful work (executed/reused owners) from verification overhead so later path-quality review can identify regressions without rerunning the operation.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `flowguard-model-regression-orchestration`: Parent composition reuses one exact frozen owner observation and performs one final freshness comparison instead of repeating full discovery and verification.
- `authoritative-model-system`: Model-revision owner evidence is produced and verified from one bounded frozen child closure, with one fresh final identity check before activation.
- `validation-evidence-gates`: Invocation-local observation reuse is explicitly non-authoritative and must preserve every existing evidence rejection boundary.

## Impact

Affected implementation is concentrated in validation ownership, full model-regression parent composition, model-revision owner-evidence production/verification, and their focused tests and self-model bindings. Public model, receipt, activation, and failure semantics remain strict; the expected observable change is substantially less repeated scanning and verification time for the same frozen inputs.
