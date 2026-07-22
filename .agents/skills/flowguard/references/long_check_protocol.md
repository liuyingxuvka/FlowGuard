# Long Check Observability Protocol

Use this protocol for long-running FlowGuard checks, model regressions, test
suites, simulations, or release validations that should run in the background.

## Artifact Contract

Default to the repository's declared evidence root. Current FlowGuard model
and full-validation commands retain complete stdout/stderr once as
deterministic gzip objects below `objects/sha256/`. Each descriptor records
logical hash/bytes, storage hash/bytes, compression, encoding, media type,
object path, and only a bounded diagnostic tail. The run also writes:

- one terminal `report.json` or `result.json`;
- child `receipt.json` files where the runner defines them;
- one immutable `evidence-run.json` after terminal output is durable;
- one scope-local `CURRENT.json` binding updated only after the run manifest.

For a target-owned long check that does not use FlowGuard's evidence writer,
retain equivalent complete stdout/stderr, exit, metadata, and terminal result
artifacts. Do not require redundant raw, combined, and parsed full-payload
copies when one complete verifiable stream object exists.

## Completion Evidence

Before reporting a long check as complete, inspect the actual artifacts and
report:

- log root;
- stdout/stderr object paths and logical/storage identities;
- exit code;
- latest update time;
- completion status;
- whether the result was newly executed or reused from a valid proof.

A path-only report, an in-progress log, or a missing exit artifact is not
completion evidence.

Do not treat a background long-running check as pass evidence just because it
has started, is still writing progress, or has a recent timestamp. Until the
final artifacts above exist and match the current risk boundary, other routes
may cite the run only as in-progress liveness.

## Progress Is Not Pass/Fail

Formal `run_model_first_checks(...)` runs inherit bounded finite-runner progress
on `stderr`. Treat progress as liveness/observability only. It does not change
pass/fail semantics.

Distinguish inherited formal-runner progress from project-specific or legacy custom
runners. A custom runner that bypasses the formal path may only emit a final
report until it implements its own progress signal. Do not describe final report
sections as live progress; final summaries become completion evidence only
after the exit and log artifacts exist.

## Proof Reuse

If the exact same abstract model, scenarios, oracle, invariants, risk boundary,
and task revision already passed and none of those inputs changed, it is
acceptable to reuse that result instead of rerunning only for ceremony. Mention
reuse briefly and keep stale evidence visible.
For tests, reuse only a completed result with final exit/status/result artifacts
plus a current `TestResultReuseTicket` and `ProofArtifactRef`. Progress output
is liveness only, not reusable pass evidence.

## Persistent Evidence Lifecycle

Audit and GC planning are read-only. A current exact plan may quarantine only
still-unreachable runs. Restore remains available until a separately explicit
purge revalidates current and pinned evidence and deletes one exact quarantine.
Ordinary validation never invokes persistent cleanup. Historical directories
without the current run manifest remain visible as `legacy_unmanaged`; file
recency never promotes them to current evidence.
