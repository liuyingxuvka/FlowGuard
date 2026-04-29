# Flowguard Self-Review Model

This document records the first executable self-review of flowguard as a
product workflow.

The model is implemented in:

- `examples/flowguard_self_review/model.py`
- `examples/flowguard_self_review/orchestrator.py`
- `examples/flowguard_self_review/conformance.py`
- `examples/flowguard_self_review/run_self_review.py`
- `examples/flowguard_self_review/run_conformance.py`

Run it with:

```powershell
python examples/flowguard_self_review/run_self_review.py
python -m flowguard self-review
python examples/flowguard_self_review/run_conformance.py
python -m flowguard self-conformance
```

## Modeled Product Boundary

The model covers the product loop where an AI coding agent uses flowguard
before real project work:

```text
ProductTask
  -> VerifyFlowguardToolchain
  -> DecideFlowguardUse
  -> BuildOrUpdateFlowguardModel
  -> RunRelevantChecks
  -> GateProductionChange
  -> RecordAdoptionEvidence
```

Each block still follows:

```text
Input x State -> Set(Output x State)
```

The first self-review intentionally does not model every internal flowguard
module. It focuses on the highest-value adoption risks:

- a non-trivial project change does not trigger flowguard;
- the formal flowguard package is not connected in a target repository;
- an ad-hoc mini-framework is accepted as if it were full flowguard adoption;
- the model is not updated for a later architecture revision;
- required checks are skipped;
- conformance replay is missing for production-facing changes;
- daily adoption review is mistaken for executable validation;
- production work is approved despite a counterexample;
- adoption logs are not recorded;
- adoption evidence stays `in_progress` even though a task is treated as final.

## Invariants

The self-review model checks:

- `nontrivial_task_must_trigger_flowguard_or_toolchain_block`
- `model_artifact_must_match_task_revision`
- `formal_toolchain_required_for_full_adoption`
- `flowguard_model_required_before_approval`
- `required_checks_must_run_before_approval`
- `adoption_log_required_for_model_first_task`
- `adoption_log_status_must_match_task_outcome`
- `unresolved_counterexample_blocks_approval`
- `daily_review_cannot_replace_executable_checks`
- `no_duplicate_adoption_log_per_task_revision`

## Scenarios

Correct flow scenarios:

- new project architecture requires a model, checks, and adoption log;
- retry/dedup/idempotency work runs scenario, loop, and progress checks;
- production-facing changes run conformance replay;
- a second architecture revision reruns model checks;
- counterexamples block production work;
- trivial documentation work may skip flowguard with an explicit reason;
- missing formal toolchain blocks full adoption instead of allowing a substitute.

Broken variants:

- trigger skips architecture validation;
- conformance replay is omitted;
- adoption log is missing;
- stale model is reused across architecture revisions;
- counterexample is ignored and production is approved;
- daily review is used as a substitute for executable checks;
- missing formal flowguard package is hidden by a temporary substitute;
- unfinished adoption status is treated as final evidence.

## Current Result

The current self-review reports:

```text
total: 15
passed: 7
expected violations observed: 8
unexpected violations: 0
missing expected violations: 0
oracle mismatches: 0
```

This means the modeled product workflow can catch the intended failure modes in
this boundary.

## Conformance Replay

The self-review model now exports representative abstract traces and replays
them against a production-like mock orchestrator.

The replay covers:

- correct orchestrator behavior for representative adoption traces;
- a broken orchestrator that omits conformance replay for production-facing
  work;
- a broken orchestrator that hides a missing formal package behind an ad-hoc
  substitute.

Current conformance result:

```text
representative_traces: 3
correct_status: OK
broken no-conformance orchestrator: VIOLATION
broken toolchain-substitute orchestrator: VIOLATION
```

## Findings

The model confirms that flowguard is useful for its own adoption workflow:

- it catches missing model-first trigger behavior;
- it catches missing formal toolchain preflight in target repositories;
- it prevents temporary mini-frameworks from being counted as full adoption;
- it can replay self-review model traces against an orchestrator mock and catch
  implementation drift;
- it catches skipped production conformance;
- it catches missing adoption logs;
- it catches `in_progress` adoption evidence being treated as final;
- it catches stale model reuse after architecture revision;
- it catches approval with unresolved counterexamples;
- it distinguishes daily review from executable validation.

The model also exposes remaining product risks:

- there is no conformance adapter yet that proves real Codex sessions always
  trigger the global Skill correctly;
- adoption logs prove usage evidence exists, but they do not prove the model
  was actually correct unless commands are recorded and checked;
- daily automation reviews logs, but it cannot force future agents to use
  flowguard;
- this self-review models the adoption workflow, not every flowguard internal
  algorithm.

## Next Useful Self-Review Models

Future self-review should add models for:

- global Skill installation and update drift;
- daily automation result ingestion;
- real project template bootstrap;
- conformance between actual adoption logs and expected adoption protocol;
- failure handling when flowguard checks are slow, missing, or not runnable.
