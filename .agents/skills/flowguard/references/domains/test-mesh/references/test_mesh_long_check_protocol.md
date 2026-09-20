# TestMesh Long-Check Protocol

Load this file for long, background, bounded-system, timeout, cancellation, or
progress-producing checks.

## Liveness Versus Result

PID, process existence, logs, heartbeats, partial counters, and progress files
prove liveness only. Passing evidence requires terminal status, exit code,
result artifact, exact covered ids, and current fingerprints.

Bind definition/request/slice/component/compiled-model/scheduler/bound/
truncation/trace identities through existing
`ProofArtifactRef.artifact_fingerprints`. Add no generic system-specific receipt
field unless a proven representation gap exists.

## Timeout And Cancellation

After timeout, cancellation, or interruption, confirm the entire descendant
process tree is zero before accepting evidence or starting another owner.
Cleanup-unconfirmed evidence is blocked and non-reusable. Preserve failed,
not-run, and partial coverage visibly.

## Background Completion

A background child is terminal only when its exit and result artifacts exist,
the result is non-progress, and all declared outputs/fingerprints verify. The
parent may continue unrelated work, but cannot claim the child passed early.
