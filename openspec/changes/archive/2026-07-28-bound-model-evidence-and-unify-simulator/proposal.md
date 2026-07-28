## Why

FlowGuard's executable model sources are small, but full validation currently retains the same child payload in raw stdout, a child result, and the parent result; repeated local release runs therefore grow to hundreds of megabytes and obscure which artifact is authoritative. Model execution is also exposed through dozens of model-local wrappers rather than one user-facing simulator command.

## What Changes

- Add one public `python -m flowguard simulator` entrypoint that selects registered models from the canonical regression manifest and preserves each model's native runner as the sole model-specific execution owner.
- Replace nested full-payload duplication in aggregate validation with bounded child summaries, hashes, artifact references, and deterministic compressed stdout/stderr sidecars.
- Add an explicit evidence lifecycle with a current-head record, read-only audit and garbage-collection planning, quarantine-only apply, and separately authorized purge.
- Keep historical evidence immutable and recoverable during quarantine; ordinary validation never silently deletes persistent evidence.
- Clarify that `.flowguard/**/model.py` and native runners are executable model source, while `.flowguard/evidence`, local worktrees, build outputs, and release receipts are generated state rather than additional models.
- Preserve existing model-local runners as internal/native adapters until separate equivalence evidence proves a wrapper can be contracted; the unified simulator does not create a second execution implementation.

## Capabilities

### New Capabilities

- `flowguard-model-simulator`: One manifest-backed public command for listing and executing one or more registered FlowGuard models through their native runners.
- `flowguard-validation-evidence-lifecycle`: Compact, content-addressed validation artifacts with current-head, audit, explicit quarantine, and separately authorized purge semantics.

### Modified Capabilities

- `long-check-observability`: Durable stdout/stderr remain complete but may be stored as deterministic compressed sidecars with hashes and bounded diagnostics instead of repeated raw text copies.
- `flowguard-evidence-receipts`: Repository evidence storage gains explicit reachability, current-head, quarantine, and purge boundaries without changing receipt freshness authority.

## Impact

- Affects `flowguard` CLI routing, model-regression orchestration, canonical validation result serialization, the full skill-suite runner, release-verification readers, evidence documentation, and tests.
- Adds no third-party runtime dependency and does not change the canonical model manifest or any model's domain semantics.
- The parent validation JSON becomes intentionally compact; consumers must use child status/summary/receipt/artifact references rather than expecting a nested copy of every child payload.
