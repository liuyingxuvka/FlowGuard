# Modeling Protocol

Use this protocol before implementing non-trivial behavior involving workflows, state, retries, deduplication, idempotency, caching, or module boundaries.

## 0. Choose The Lightest Mode

Before changing files, separate three situations:

- `read_only_audit`: inspect an existing project without changing production
  code. Run import preflight, existing FlowGuard models/replays when present,
  adoption evidence review, and stale fallback checks. Do not create a new model
  solely because the task is read-only.
- `model_first_change`: production behavior may change. Build or update the
  smallest useful model before editing production code.
- `model_maintenance`: existing `.flowguard` models, replay adapters, or
  adoption evidence appear stale. Update those artifacts before making claims
  from them.

If real FlowGuard is importable but a current `.flowguard` Python model still
claims `flowguard_package_available = False`, uses a fallback explorer, or
defines local replacement `Explorer`/`Workflow` classes, record a
`stale_fallback_model` warning. This is a confidence gap, not a hard failure.

Keep the API surface boundary clear:

- core modeling uses `FunctionBlock`, `FunctionResult`, `Invariant`,
  `Workflow`, and `Explorer`;
- modeling helpers reduce boilerplate, but direct `Explorer` use remains valid;
- reporting helpers explain gaps and skipped work, but warnings are not hard
  failures;
- evidence and benchmark helpers are mainly for FlowGuard maintenance and
  upgrade validation, not ordinary project gates.

See `docs/api_surface.md` for the public API layer map.

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
For every field named by the invariant, search the production code for all
writers of that field and record whether each writer is modeled, intentionally
skipped, or outside the current boundary.

Examples:

- `recommendation_status`
- `output_status`
- `analysis_json`
- cache/source-of-truth fields
- queue or retry status fields

If a field has multiple production writers, cleanup jobs, runtime repair paths,
or finalizers, missing one writer is a model-fidelity gap. It is not an
automatic FlowGuard runtime failure, but it must be visible before claiming
production confidence. See `docs/state_write_inventory.md` for the lightweight
table format.

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

When the bug class matches a common pattern, prefer the standard property
factories in `flowguard.checks` over hand-written boilerplate. Examples include
`no_duplicate_by`, `at_most_once_by`, `all_items_have_source`,
`no_contradictory_values`, `cache_matches_source`,
`only_named_block_writes`, `require_label_order`, and `forbid_label_after`.
These factories still return ordinary `Invariant` objects. They are helper
building blocks, not a required modeling layer.
They also attach optional `property_classes` metadata, such as
`deduplication`, `at_most_once`, or `cache_consistency`, so `audit_model(...)`
can recognize common property types without relying only on invariant names.
Custom invariants can add the same metadata when useful, but metadata is not
required and unknown values are not hard failures.

For common risks, optional domain packs can reduce boilerplate:
`DeduplicationPack`, `CachePack`, `RetryPack`, and `SideEffectPack`. A pack only
uses selectors and key functions you provide. It does not infer state, enforce
a model shape, or become a required structure.

For recurring multi-role maintenance systems, such as
Sleep/Dream/Architect/Installer/Reviewer flows, the optional maintenance
template can reduce setup time:

```powershell
python -m flowguard maintenance-template --output .
```

It scaffolds repeated-action, missing-report, and install-sync checks. Rename
the roles and state fields before treating it as project evidence.

## 9. Run Explorer With Repeated Inputs

Choose:

- `external_inputs`
- `initial_states`
- `max_sequence_length`
- optional required labels or reachable predicates

Always include repeated-input exploration when duplicate side effects are possible. For one input and length two, the explorer must check both `[x]` and `[x, x]`.

When using the optional orchestration path, put the intended coverage boundary
in a `RiskProfile`, then create a `FlowGuardCheckPlan` and call
`run_model_first_checks(plan)`. The runner performs audit, optional scenario
scaffolding, Explorer, counterexample minimization, scenario review, optional
progress/contract/conformance sections, and a unified summary. This is a
convenience path, not the only valid way to run FlowGuard.

## 10. Inspect Counterexamples

When a report fails, read the counterexample trace. A useful trace shows:

- external input sequence;
- each function block;
- function input and output;
- old state and new state;
- labels and reasons.

The trace should make the failing architecture visible without guessing.

If the failing external input sequence is longer than needed, use
`minimize_failing_sequence` or `minimize_report_counterexample` to produce a
smaller deterministic reproduction. Minimization should preserve the original
counterexample in the report; a shortened trace is easier to review, but it
does not replace the original evidence.

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

Conformance replay should be the default next check when any of these are true:

- the invariant depends on a state field with multiple production write points;
- the production change has database writes or other durable side effects;
- runtime, cleanup, repair, or finalizer paths can reach the same state;
- the model result will be used to claim production behavior, not just
  model-level behavior;
- adapter projection is needed to compare model state with real state.

If replay is skipped in one of these cases, record the reason explicitly and
report the result as model-level confidence only.

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

For retry, deduplication, cache, idempotency, queue, or side-effect risks,
`ScenarioMatrixBuilder` can scaffold a small deterministic set of high-value
scenarios: single input, repeated same input, pairwise order, and ABA. Generated
scenarios default to `needs_human_review` unless you provide a domain
expectation. They cover input shapes, not business correctness, so they do not
silently become pass/fail claims.

## 15. Run Loop / Stuck-State Review

When a workflow has retry, rewrite, waiting, refresh, queue, or human-review cycles, build a reachable state graph and run loop checks.

Look for:

- stuck non-terminal states;
- bottom SCCs with no terminal or success state;
- unreachable required success states;
- terminal states with outgoing transitions;
- cycles with escape edges that require future fairness/progress modeling.

Do not claim bottom-SCC detection proves universal termination for cycles that have escape edges. Mark those as `known_limitation` or model a progress rule explicitly.

## 16. Run The Evidence Baseline Before Upgrades

Before starting a major flowguard upgrade, run the evidence baseline:

```powershell
python examples/evidence_baseline/run_baseline.py
```

Use it as an upgrade-readiness check. The baseline records:

- unit-test inventory;
- scenario review outcomes;
- conformance replay outcomes;
- model-check outcomes;
- loop/stuck review outcomes;
- bug-class scorecard.

An upgrade should improve or preserve the expected-vs-observed scorecard. Do not silently convert `needs_human_review` or `known_limitation` into `pass`. Do not accept new `unexpected_violation`, `missing_expected_violation`, or `oracle_mismatch` cases without a clear reason.

## 17. Keep The Real Software Problem Corpus In View

Before major flowguard framework upgrades, also run the real software problem corpus quality review:

```powershell
python examples/problem_corpus/run_corpus_review.py
```

The corpus quality review checks the problem-intent matrix. It is not the same as executable behavior testing. Reports must keep this distinction explicit:

```text
Problem-intent corpus: 2100 cases
Executable corpus review: 2100 executable cases, 0 not_executable_yet
Real-model corpus review: 2100 real_model_cases, 0 generic_fallback_cases
Evidence baseline: <N> evidence cases
Unit-test inventory: <U> test entries
```

For Phase 10.8 and later, also run:

```powershell
python examples/problem_corpus/run_executable_corpus_review.py
```

The executable corpus review must run real flowguard checkers, such as `Workflow + ScenarioReview + Invariant` or `LoopCheck`. Do not count a corpus case as executable if it only has prose fields or string evidence.

For Phase 11 and later capability claims, executable coverage is still not enough. The report must also show:

```text
real_model_cases: 2100
generic_fallback_cases: 0
model_variant_total: 150
model_families_with_six_variants: 25
```

The main corpus includes `pressure_100`, which is intentionally part of the
baseline before the next mathematical upgrades. Preserve `known_limitation`
for pressure cases that current checks cannot prove, rather than converting
them to `pass`.

The baseline freeze rules are documented in
`docs/benchmark_baseline_contract.md`.

This means each case is bound to a workflow-family-specific domain model with concrete block names, state slots, model variants, and structural evidence. A generic corpus template can remain useful for plumbing checks, but it is not a valid capability baseline.

For durable product-grade benchmark claims, also run:

```text
python examples/problem_corpus/run_benchmark_hardening.py
```

The hardening review must report:

```text
variant_min_cases >= 8
variants_below_target: 0
families_missing_required_case_kinds: 0
families_missing_required_bug_classes: 0
benchmark_conformance_family_count = 25
production_conformance_family_count = 26
total_replays = 78
failures = 0
```

This prevents the benchmark from becoming broad but shallow. A variant should
not count as mature if it was only touched once.

The corpus is not a roadmap mapping and not a current capability assessment. It defines real software workflow problems independent of future phase ownership.

Use it to keep future work grounded in broad software structures:

- cache and materialized views;
- retry and side effects;
- file pipelines;
- queues and leases;
- approval and human review;
- permissions and sessions;
- payments and inventory;
- deployment and configuration rollout;
- audit and traceability;
- classifier routing without API calls.

Do not add future phase ownership, current support status, or implementation assignment fields to corpus cases. Those belong in later reports, not in the problem case itself.

## 18. Use Quality Audit and Summary Reports As Helpers

`audit_model` provides a lightweight `ModelQualityAuditReport` for obvious
coverage gaps. It is intentionally heuristic and warning-oriented. A warning
means "this is a confidence boundary", not "the model failed". A suggestion is
an improvement idea. Only structural problems such as a workflow with no blocks
should be treated as audit errors.

Use a `FlowGuardSummaryReport` when you need to present model check, audit,
scenario review, progress, contract, conformance, and skipped/not-run sections
together. If Explorer passes but audit warns, the overall status should be
`pass_with_gaps`, not plain `pass`. If production conformance is not run, record
`not_run` or `skipped_with_reason`; skipped is not pass.

Do not report model-level confidence as production confidence unless
conformance replay or another production-facing evidence source supports that
claim.

Recommended low-friction agent flow:

1. Start with the smallest useful FlowGuard model.
2. Declare a lightweight `RiskProfile`.
3. Use standard property factories or domain packs when they fit.
4. Run `run_model_first_checks()` when available.
5. Inspect minimized counterexamples if any.
6. Treat `pass_with_gaps` as useful but limited confidence.
7. Do not claim production conformance unless conformance replay or equivalent
   real-code evidence exists.
8. Record skipped checks; skipped is not pass.

## Completion Checklist

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
- ModelQualityAudit warnings, missing conformance, skipped checks, and not-run
  sections are reported as confidence boundaries rather than hidden or
  mislabeled as passes.
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
