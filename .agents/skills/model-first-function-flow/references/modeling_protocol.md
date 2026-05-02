# Modeling Protocol

Use this protocol before implementing non-trivial behavior involving workflows, state, retries, deduplication, idempotency, caching, or module boundaries.

## 0. Write A Risk Intent Brief

Before defining state or function blocks, write the short brief that tells the
model what accidents it is meant to expose. Ask the user only when materially
different risk priorities exist and the protected harm cannot be inferred
safely.

Answer these questions before creating or editing the model:

- Which failure modes are we trying to prevent?
- What protected harms would happen if those failures slipped through?
- Which state fields, side effects, confirmations, durable records, or external
  commitments must be modeled or the failure would be invisible?
- Which adversarial inputs, repeated inputs, retries, partial successes,
  ordering changes, concurrent actions, or exception branches must be simulated?
- Which hard invariants must never be weakened merely to pass checks?
- What blindspots remain because the model is intentionally smaller than the
  real workflow?

When using the optional runner path, put the brief into `RiskProfile` through a
`RiskIntent` or equivalent `risk_intent` mapping. Direct `Explorer(...)` usage
remains valid; still keep the brief in the model file, adoption note, or review
summary so reviewers can see why the model includes the chosen state, inputs,
scenarios, and invariants.

## 1. Identify External Inputs

List the finite abstract inputs that can enter the workflow. Use behavior classes, not full production payloads.

Examples:

- A new job.
- The same job repeated.
- A low-signal item.
- A retry after partial progress.

## 2. Identify Abstract Finite State

Model only state that affects future behavior or invariants. Use hashable immutable values such as frozen dataclasses, tuples, strings, integers, booleans, and frozensets.

Do not use live databases, files, network calls, clocks, random values, or LLM calls.

## 3. Identify Function Blocks

Split the workflow into named function blocks. Each block should correspond to one behavioral boundary, such as scoring, recording, decisioning, validation, cache lookup, or persistence.

Each block must represent:

```text
Input x State -> Set(Output x State)
```

## Model Fidelity Requirement

Treat the model as a falsifiable simulator of the real workflow, not as ground
truth. Before trusting model findings, compare representative traces with real
code paths, logs, tests, user workflows, or production conformance evidence when
available.

Choose the smallest model that is faithful enough for the current risk. Include
the control-flow branches, state writes, retry/cache/deduplication behavior,
terminal paths, exceptions, and side effects that could affect the bug class
under review.

If a trace is impossible, suspicious, or misses known production behavior,
revise the model, scenario oracle, or replay adapter first, then rerun the
checks. Do not report model-level confidence as production confidence until
conformance evidence supports it.

## 4. Define Possible Outputs

For each block, enumerate every output class the block may produce. If a score can be `low`, `medium`, or `high`, return all possible score outputs for that abstract input and state.

Do not hide possible outcomes in comments or prose.

## 5. Define State Reads and Writes

For each block, document:

- `reads`: state fields that affect the result.
- `writes`: state fields the block may change.

This exposes state ownership and prevents the model from spreading writes across the wrong modules.

Before trusting an invariant over a state field, make a state write inventory.
Search the production code for every writer of fields such as
`recommendation_status`, `output_status`, `analysis_json`, cache values, queue
status, retry counters, and side-effect records. Record which writers are
modeled and which are skipped with reasons.

## 6. Define Idempotency

Write down what happens if the same input reaches the same block again.

Examples:

- A cached job score should be reused.
- A duplicate record should return `already_exists`.
- A retry should not create a second side effect.

## 7. Define Failure Modes

Model expected failures explicitly. A block may return zero results, but that creates a reportable dead branch. If a branch is supposed to terminate, model it as a terminal output or a consumed output rather than letting it disappear.

Unexpected exceptions should be reported structurally, not swallowed.

## 8. Define Invariants

Write hard invariants over state and trace. They should describe guarantees that must hold on every explored path.

Examples:

- No duplicate records.
- No repeated scoring without refresh.
- Every application record has a cached score.
- No contradictory final decisions.
- No hidden second source of truth.

Do not weaken invariants merely to make checks pass.

## 9. Run Explorer With Repeated Inputs

Choose:

- `external_inputs`
- `initial_states`
- `max_sequence_length`
- optional required labels or reachable predicates

Always include repeated-input exploration when duplicate side effects are possible. For one input and length two, the explorer must check both `[x]` and `[x, x]`.

## 10. Inspect Counterexamples

When a report fails, read the counterexample trace. A useful trace shows:

- external input sequence;
- each function block;
- function input and output;
- old state and new state;
- labels and reasons.

The trace should make the failing architecture visible without guessing.

## 11. Revise Model or Architecture

If the counterexample shows a real design bug, change the model and intended architecture. If it shows the model is incomplete, fix the model. Then rerun the checks.

Do not replace executable modeling with prose.

## 12. Only Then Implement Production Code

After the model passes, implement production code against the modeled behavior. Use the model to guide unit tests and code review.

Production implementation should preserve:

- the same state ownership boundaries;
- the same idempotency behavior;
- the same deduplication behavior;
- the same downstream object compatibility;
- the same invariants.

## 13. Replay Production Code Against Model Traces

After production code is implemented or modified, add conformance replay when feasible.

Conformance replay should be the default next check when the production logic
has multiple state write points, database or durable side effects,
runtime/cleanup/finalizer paths, production-confidence claims, or adapter
projection. If replay is skipped in those cases, record why and report
model-level confidence only.

The intended order is:

1. Model check first.
2. Implement production code second.
3. Conformance replay third.

Export representative model traces with `Trace.to_dict()` or `Trace.to_json_text()`. Write a replay adapter that maps each abstract `TraceStep` to the real production call. The adapter should project production state and output into abstract observations.

Do not require real internal state to equal abstract state directly. Use projection:

- production output -> abstract observed output;
- production state -> abstract observed state;
- production branch behavior -> observed label.

The production behavior must conform to model expectations or the model must be explicitly revised. Do not silently diverge from the model.

## 14. Run Scenario Sandbox Review

Before connecting a model to larger production workflows, run scenario review when the task involves:

- repeated input;
- retries;
- refresh;
- queues;
- reprocessing;
- human review loops;
- uncertain AI decisions;
- caching;
- deduplication;
- side effects.

Write scenarios with explicit human expectations. Expected violations in broken models should be successful review outcomes when flowguard observes the intended violation. Use `needs_human_review` when the model exposes a policy gap that should not be falsely treated as proven.

## 15. Run Loop / Stuck-State Review

When a workflow has retry, rewrite, waiting, refresh, queue, or human-review cycles, build a reachable state graph and run loop checks.

Look for:

- stuck non-terminal states;
- bottom SCCs with no terminal or success state;
- unreachable required success states;
- terminal states with outgoing transitions;
- cycles with escape edges that require future fairness/progress modeling.

Do not claim bottom-SCC detection proves universal termination for cycles that have escape edges. Mark those as `known_limitation` or model a progress rule explicitly.

## 16. FlowGuard Framework Upgrades

For FlowGuard framework upgrades, benchmark claims, or broad capability claims,
use the repository-level `docs/framework_upgrade_checks.md` reference when it
is available. Do not require the internal benchmark suite for ordinary project
bug fixes.

## Completion Checklist

- A Risk Intent Brief names failure modes, protected harms, model-critical
  state and side effects, adversarial inputs, hard invariants, and blindspots.
- The model uses only the Python standard library.
- Inputs and state are finite and hashable.
- Every block returns all possible branches.
- Zero-result and non-consumable paths are reportable.
- Repeated external inputs are explored.
- Invariant violations include counterexample traces.
- Correct models pass.
- Broken variants fail for the intended reason.
- Representative traces can be exported for audit or replay.
- Production implementations have conformance replay adapters when feasible.
- Production replay either conforms to the model or documents why the model changed.
- Scenario reviews compare expected and observed outcomes.
- Broken-model scenarios produce expected violations rather than ordinary failures.
- Loop/stuck review is run for workflows with retries, refresh, waiting, or reprocessing.
- Evidence baseline is run before major upgrades and after the upgrade changes land.
- Real software problem corpus quality review is run before major upgrades to keep the broader problem space visible.
- Executable corpus review is run before major upgrades when the task claims corpus behavior-test coverage.
- Real-model corpus review is required before claiming broad flowguard capability across the 2100-case corpus.
- Benchmark hardening review is required before claiming the test rig is a durable product-grade baseline.
- Progress/fairness checks are required when a workflow has a cycle with an
  escape edge but no ranking or bounded-progress guarantee.
- FunctionContract checks are required when input/output compatibility,
  forbidden writes, ownership, traceability, or projection refinement is the
  risk being modeled.
- Thin CLI, pytest, schema, and template helpers must preserve structured
  expected-vs-observed reports rather than hiding review status.
- Reports distinguish problem-intent case count, executable case count, evidence baseline count, and unit-test inventory count.
- Real project adoptions record status, trigger reason, elapsed time, commands run,
  findings, counterexamples, skipped steps, friction points, and next actions
  in an adoption log.

## Real Adoption Logging

When using flowguard in another project, keep a project-local adoption record:

- `.flowguard/adoption_log.jsonl` for machine-readable entries;
- `docs/flowguard_adoption_log.md` for a human-readable log.

Use `flowguard.adoption.AdoptionTimer` to time the session and
`AdoptionCommandResult` to record checks. The log should explain why the skill
was triggered, which model files changed, which checks ran, what was found,
what was skipped, and what should happen next.

Use status values honestly:

- `in_progress`: the adoption work has started but is not final;
- `completed`: the model-first work is finished and executable checks were recorded;
- `blocked`: a real blocker remains;
- `skipped_with_reason`: a step was intentionally skipped and the reason is recorded;
- `failed`: a command, model check, conformance replay, or oracle review failed.

This log is not a substitute for executable modeling. Its purpose is to make
real usage reviewable so future flowguard work can improve the parts that were
slow, confusing, or insufficient.
