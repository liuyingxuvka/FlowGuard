# Conformance Testing

FlowGuard first checks the abstract model. Phase 8 adds a second step: replaying representative abstract traces against production code through an adapter.

## Model Checking vs Conformance Testing

Model checking answers:

```text
Does the abstract model violate its invariants?
```

Conformance testing answers:

```text
Does the real implementation behave like the passing abstract trace?
```

A passing model does not prove production code is correct. The production implementation can still forget a deduplication check, mutate the wrong state, score a job twice, or emit an output that no downstream code expects. Conformance replay connects the model to implementation behavior and helps calibrate whether the model is faithful enough to the real workflow.

If replay or real-world evidence diverges from the abstract trace, first decide whether the production code is wrong, the replay adapter is hiding behavior, or the model is too coarse. Refine the model or adapter and rerun the checks before treating the model result as production confidence.

## Default Replay Triggers

"When feasible" should not mean "usually skipped." After a model passes,
conformance replay should be the default next check when the production boundary
has any of these traits:

- multiple functions, jobs, or methods can write a state field named by an
  invariant;
- the change includes database writes or other durable side effects;
- runtime, cleanup, repair, or finalizer paths can update the same state;
- the model result will be reported as production confidence rather than
  model-level confidence;
- adapter projection is required to compare production state with abstract
  state.

If replay is skipped in one of these cases, record why it was skipped and what
confidence remains. A skipped replay is not a pass.

## Trace Export

A model trace records:

- external input sequence;
- function name;
- function input;
- function output;
- old abstract state;
- new abstract state;
- label;
- reason.

`Trace.to_dict()` and `Trace.to_json_text()` export this information as JSON-compatible data. Complex objects are exported through dataclass fields when possible and through a safe `repr()` fallback when not.

`CheckReport.to_dict()` and `CheckReport.to_json_text()` export traces, violations, dead branches, exceptions, reachability failures, and explored input sequences.

The export is meant to be deterministic, readable, auditable, and saveable. It is not meant to perfectly deserialize every arbitrary Python object.

## Replay Adapter

Production code rarely has the same state shape as the abstract model. A replay adapter bridges the two.

The minimal adapter methods are:

```python
class ReplayAdapter:
    def reset(self, initial_state):
        ...

    def apply_step(self, step):
        ...

    def observe_state(self):
        ...

    def observe_output(self):
        ...
```

`apply_step()` maps an abstract `TraceStep` to the corresponding production call. It returns a `ReplayObservation` or lets FlowGuard call `observe_state()` and `observe_output()` afterward.

## Projection and Observation

Conformance replay should not require production state to equal abstract state directly. Production state may use mutable lists, dictionaries, ORM objects, caches, database rows, or service-local fields.

The adapter should project production behavior into abstract observations:

- `observed_output`: the production output represented in abstract output terms.
- `observed_state`: the production state represented in abstract state terms.
- `label`: the replayed behavior branch.

FlowGuard compares these projections to the expected trace step. This keeps conformance focused on behavior, not internal implementation layout.

Projection is part of the simulator boundary. It may simplify production state,
but it must not invent missing behavior or erase raw evidence that matters for
the current risk. If projection makes an impossible or buggy production path look
valid, the adapter is unsound and must be refined before the replay result is
trusted.

## Rules

The default conformance rules are intentionally small:

- projected state matches the expected abstract `new_state`;
- projected output matches the expected abstract output;
- observed label matches the expected label;
- adapter exceptions become violations.

The caller may also pass invariants. In the job-matching example, invariants catch duplicate application records and repeated scoring on projected production state.

## Job-Matching Example

The job-matching example includes:

- `CorrectJobMatchingSystem`: uses score cache, deduplicates records, and follows model decisions.
- `BrokenDuplicateRecordSystem`: appends duplicate `application_records`.
- `BrokenRepeatedScoringSystem`: appends duplicate `score_attempts` even when the score cache has the job.
- `JobMatchingReplayAdapter`: maps `ScoreJob`, `RecordScoredJob`, and `DecideNextAction` trace steps to production method calls and projects production state back to the abstract `State`.

Run it with:

```powershell
python examples/job_matching/run_conformance.py
```

The correct implementation passes. The duplicate-record implementation fails with a duplicate `application_records` violation. The repeated-scoring implementation fails with a repeated `score_attempts` violation.

## FlowGuard Self-Review Example

FlowGuard also has a conformance replay for its own adoption workflow:

- `CorrectFlowguardOrchestrator`: production-like mock orchestrator for Skill
  adoption flow;
- `BrokenNoConformanceOrchestrator`: omits conformance replay for
  production-facing work;
- `BrokenToolchainSubstituteOrchestrator`: hides a missing formal package behind
  an ad-hoc substitute;
- `FlowguardSelfReviewReplayAdapter`: maps self-review trace steps to the
  orchestrator methods and projects state/output back to the abstract model.

Run it with:

```powershell
python examples/flowguard_self_review/run_conformance.py
python -m flowguard self-conformance
```

This is not user-facing product behavior. It is a regression guard that checks
whether the model-first adoption protocol still matches the orchestrator logic
that future agents are expected to follow.

## Limits

Phase 8 is intentionally narrow:

- deterministic only;
- no random generation;
- no Hypothesis yet;
- no probability model;
- no Monte Carlo;
- adapter must be written by the user;
- model fidelity depends on the adapter and scenario oracle;
- not a complete formal proof;
- not a replacement for unit tests;
- best suited for workflow-level and side-effect-level deviations.

Conformance replay is most useful after a model passes and before or during production implementation. If production behavior intentionally differs from the model, update the model explicitly rather than silently diverging. A model that omits relevant production behavior should be treated as incomplete, not as proof that the implementation is safe.

## Relationship To Scenario And Loop Review

Conformance replay checks production behavior against representative traces. Scenario review checks whether a catalog of human expectations matches what flowguard observes. Loop review checks graph-level stuck states and non-terminating components.

For workflows with repeated inputs, retry, refresh, queues, reprocessing, human review, uncertain decisions, caching, deduplication, or side effects, use the sequence:

1. Model check.
2. Scenario sandbox review.
3. Loop/stuck-state review if cycles or waiting states exist.
4. Production implementation.
5. Conformance replay.

Do not let adapter projection hide raw production bugs. If raw production state contains duplicate side effects but projection deduplicates them, the adapter is unsound and needs review.
