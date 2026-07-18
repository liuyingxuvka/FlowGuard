# Conformance And Adoption Protocol

Use this protocol when FlowGuard evidence must support production confidence,
install readiness, local sync, shadow workspace sync, or release preparation.

## Conformance Replay Trigger

Conformance replay should be the default next check when any of these are true:

- the invariant depends on a state field with multiple production write points;
- production code has database writes or durable side effects;
- runtime, cleanup, repair, or finalizer paths can update the same state;
- the result will be reported as production confidence rather than model-level
  confidence;
- adapter projection is required to compare real state with abstract state.

If replay is skipped in one of these cases, record why and report model-level
confidence only. A skipped replay is not a pass.

## Prediction Before Observation

For task-local model iteration, freeze the model prediction before the replay
adapter can observe production behavior:

1. preserve the current task model as version `v1`;
2. freeze the expected trace, a concrete falsifier, and the observation
   boundary in a `TaskPredictionSnapshot`;
3. cross the observation boundary once by running production through
   `replay_prediction`;
4. compare the independent observations with the frozen trace;
5. when the mismatch shows that the task model is incomplete, create a
   candidate `v2` without overwriting `v1`.

The prediction and report must retain the prediction fingerprint and task-model
fingerprint. A text field such as `conformance_status=pass` is not production
evidence and must block production confidence when no current
`ConformanceReport` is present.

## Independent Replay Adapter

The production adapter receives a `ReplayInput`, not the expected `TraceStep`.
It may receive the external input, function name, and function input needed to
call production. It must not receive the model's expected output, expected new
state, label, or reason. Those oracle values remain inside FlowGuard and are
used only after production returns an observation.

If the production implementation is nondeterministic, select or declare the
production policy independently and compare it with the matching modeled trace.
Do not pass the desired model branch into production to make replay pass.

For an exact runtime-path claim, compare every occurrence in order for each run.
Do not collapse repeated node ids to their first occurrence or flatten several
runs together. Bind occurrence-specific terminal, state-write, and side-effect
expectations whenever they are declared.

## Candidate Task Model Decision

A task-model correction remains a candidate until every declared replay passes:

- the new failure case that triggered the correction;
- the old normal and error cases affected by the change;
- any task-local holdout declared for the candidate.

Each declared replay must be represented by `TaskReplayEvidence` built from a
current `ConformanceReport`. The evidence must pass and must bind the same task,
model, and candidate-model fingerprint. A list of replay ids or a status-only
claim cannot accept the candidate.

Accepting the candidate makes `v2` active for this task. Rejecting it keeps
`v1` active. Rolling back an accepted candidate restores `v1`. Ordinary task
iteration must not rewrite FlowGuard core code, default thresholds, global
templates, or permanent rules.

## Install And Sync Evidence

Before reporting a FlowGuard Skill or release as ready, verify the relevant
runtime copies:

- source checkout import;
- editable/local install metadata;
- installed Codex Skill files;
- shadow workspace source sets when a local workspace mirrors FlowGuard;
- Git version and GitHub version only when the user has authorized publication.

For shadow workspaces, sync whole source sets instead of cherry-picking only a
few files. At minimum verify imports and focused tests from the shadow root.

## Adoption Evidence

For real project usage, record:

- trigger reason;
- modeled workflow or risk;
- model files;
- commands run and pass/fail status;
- findings and counterexamples;
- skipped or deferred steps with reasons;
- friction points;
- next actions.

Preferred local records:

- `.flowguard/adoption_log.jsonl`;
- `docs/flowguard_adoption_log.md`.

The CLI helpers `adoption-start` and `adoption-finish` can create structured
entries, but logging does not replace executable validation.

## Release Sync

When GitHub publication is authorized, version metadata, changelog, README,
tag, pushed branch, and GitHub release should agree. If the user asks to pause
GitHub publication, stop before tag, push, and release creation while keeping
local validation and sync evidence complete.
