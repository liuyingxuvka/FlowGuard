## Context

FlowGuard currently has four separate pieces:

1. the abstract model produces a `Trace`;
2. `replay_trace(...)` compares that trace with a production adapter;
3. `run_model_first_checks(...)` summarizes an optional conformance result;
4. Runtime Path Evidence compares declared nodes with observations.

The direct replay is sound when it is actually supplied, but the summary path
also accepts a caller-authored passing string. Runtime exact-path review uses
only the first observation for each node, so repeated nodes are lost. Model
Miss governs the repair process but does not retain an explicit task-local
base/candidate/decision record.

The implementation must coexist with a large unrelated in-progress change.
Core target files are currently clean; already modified `AGENTS.md`,
`flowguard/__init__.py`, and broad documentation are outside this change.

## Goals / Non-Goals

**Goals:**

- Make a production-conformance pass depend on a real replay report.
- Keep the production adapter independent from expected model outputs.
- Compare complete strict runtime paths, including repeated occurrences and
  occurrence-specific terminal/write/side-effect behavior.
- Freeze an immutable task-local prediction before replay.
- Preserve explicit base and candidate model identities and provide bounded
  accept, reject, and rollback transitions.
- Keep all new model revision behavior task-local and side-effect free.

**Non-Goals:**

- Automatically modify FlowGuard rules, thresholds, skills, or reusable model
  libraries.
- Store long-term learning, alter model weights, or promote one task's repair
  into a permanent default.
- Introduce a compatibility flag that restores status-only conformance passes.
- Install skills, release a package, modify user-level Codex files, or publish
  Git changes.

## Decisions

### 1. A report, not a status string, owns production conformance

`run_model_first_checks(...)` will continue to display non-passing
status-only values such as failed, blocked, skipped, or not-run. A status-only
value that normalizes to pass will become a blocker because it contains no
observed replay.

Alternative considered: remove `conformance_status` entirely. Rejected because
non-passing and skipped statuses are still useful for preserving visible
confidence gaps.

### 2. Prediction binding extends the existing replay owner

A new `TaskPredictionSnapshot` will contain one immutable expected `Trace`,
task/model/version identities, model fingerprint, falsifier, scenario id, and
an observation-boundary id. `replay_prediction(...)` will delegate to the
existing conformance engine and bind the prediction identity to the resulting
`ConformanceReport`.

Alternative considered: create a second replay engine. Rejected because
`conformance.py` already owns output/state/label/invariant comparison.

### 3. Revision state records identities, not arbitrary model code

`TaskModelVersion` identifies a model artifact by version, fingerprint, and
optional artifact reference. `TaskModelRevision` preserves a base version and
one distinct candidate, the mismatch that motivated it, changed model
elements, and required replay ids. It exposes immutable transitions:

- proposed → accepted, only after every required replay has current passing
  `TaskReplayEvidence` bound to the same task, model, and candidate fingerprint;
- proposed → rejected, retaining the base as active;
- accepted → rolled_back, restoring the base as active.

The helper performs no file writes and cannot modify FlowGuard's own rules.

Alternative considered: automatically copy or rewrite model files. Rejected
because task-local iteration must not become online Guard self-modification.

### 4. Exact runtime paths are occurrence-based

When `require_exact_path=True`, ordered contracts and current external
observations will be compared as complete sequences, sorted by their sequence
indices while preserving stable input order. Repeated node ids remain repeated.
Each expected occurrence is paired with its observed occurrence, so terminal,
state-write, and side-effect checks use the correct occurrence rather than all
observations sharing a node id.

When explicit runs are supplied, each current passing run is checked
independently. Uncontracted observations remain governed by the existing
`allow_uncontracted_nodes` policy.

Alternative considered: add a separate occurrence-id field. Rejected because
the existing `sequence_index` already supplies the required occurrence
identity.

### 5. Example adapters see inputs, not answers

The job-matching adapter will call production methods with only the real
function input. The production implementation will use its own deterministic
choice. Expected values remain exclusively on the comparison side.

## Risks / Trade-offs

- [Existing callers rely on status-only pass] → Fail visibly and document that
  callers must supply a replay report; do not add a fallback flag.
- [A caller constructs a prediction after privately observing the result] →
  The official API enforces freeze-before-observe ordering and immutable
  fingerprints, but cannot police observations performed outside FlowGuard;
  retain this as a claim boundary.
- [Multiple runtime runs are flattened accidentally] → Review each explicit
  `RuntimePathRun` independently and add repeat/multi-run regression tests.
- [Stricter write/side-effect equality breaks loose contracts] → Apply exact
  equality only in strict exact-path mode; ordinary node-boundary review keeps
  its existing allowed-set behavior.
- [Parallel work touches broad exports or skill files] → Avoid
  `flowguard/__init__.py`, `AGENTS.md`, and already modified broad docs; update
  only the clean conformance protocol reference.

## Migration Plan

1. Update callers that currently use `conformance_status=pass` to pass the
   actual `ConformanceReport`.
2. Keep status-only non-pass reporting unchanged.
3. Adopt `TaskPredictionSnapshot` and `replay_prediction(...)` when a task
   needs auditable prediction-before-observation binding.
4. Use `TaskModelRevision` only for current task artifacts; retain base model
   files at the referenced artifact location until the task closes.
5. If an accepted candidate regresses, record `rollback(...)` and restore the
   base artifact identified by the record.

## Open Questions

None for this bounded implementation. Long-term pattern promotion and
cross-task learning remain explicitly out of scope.
