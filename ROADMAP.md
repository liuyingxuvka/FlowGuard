# flowguard Roadmap

## 1. Core worldview

`flowguard` is a model-first function-flow engineering layer. It is not a
normal test framework, not a prompt-engineering tool, and not an LLM wrapper.
Its purpose is to make workflow behavior executable before production code is
written or changed.

The core mathematical object is a function block:

```text
F: Input x State -> Set(Output x State)
```

A block receives an abstract input and an abstract state, then returns every
possible output/new-state pair. The set may contain zero, one, or many results:

- zero results: a dead or non-productive branch that should be reported;
- one result: deterministic behavior for that input/state pair;
- many results: explicit branching behavior.

The model is deterministic and exhaustive inside finite bounds. It is not a
probability model. It does not run Monte Carlo, random sampling, or LLM calls.
If a behavior may produce several results, the model enumerates those results.

A workflow composes blocks:

```text
Workflow = F_C o F_B o F_A
```

Because every block can branch, a workflow forms an execution tree or reachable
state graph. `flowguard` checks paths and graph structure for:

- invariant violations;
- duplicate side effects;
- repeated processing without refresh;
- missing deduplication;
- missing idempotency;
- cache/source mismatch;
- wrong state ownership;
- downstream non-consumable outputs;
- missing or contradictory decisions;
- stuck states, closed loops, and unreachable success;
- production behavior that diverges from the abstract model.

The current review loop is:

```text
function-flow model
  -> deterministic scenario inputs
  -> human oracle
  -> observed model behavior
  -> expected-vs-observed review
  -> counterexample trace
  -> loop / stuck / unreachable-success review
  -> optional production conformance replay
```

Future work should strengthen this loop in this order:

1. freeze the current evidence baseline before each major upgrade;
2. define a roadmap-independent real software problem corpus;
3. prove value across multiple benchmark workflow types;
4. prove production conformance across those benchmark types;
5. add progress/fairness/temporal checks;
6. add contract composition and refinement checks;
7. only then harden packaging, CLI, pytest integration, and adoption tooling.

## 2. Current status

Phases 0 through 15 are complete. Every future upgrade should run both the
problem-intent corpus review and the real-model executable corpus review before
changing direction.

Phase 11 was sharpened from a sampled benchmark zoo into a full real-model
binding baseline. Every problem case now executes through a
workflow-family-specific model, and no case relies on a generic fallback.
Phase 11.1 deepened that baseline to 150 real model variants: 25 workflow
families with six variants each.

Phase 11.2 hardens the baseline into a durable regression test rig:

- every variant has at least eight executable cases;
- the current assignment gives each variant 13 to 15 cases;
- every family covers all required case kinds;
- every family covers the benchmark bug-class matrix;
- six priority non-job-matching families have scenario seed evidence;
- production conformance seed replay covers all 25 benchmark families plus
  `job_matching`.

Phase 12.5 freezes a stronger main benchmark baseline:

- `total_cases=2100`;
- `base_1500=1500`;
- `gap_500=500`;
- `pressure_100=100`;
- `real_model_cases=2100`;
- `generic_fallback_cases=0`;
- `known_limitation=0` after Phase 13 converted progress/fairness escape-edge
  pressure cases into explicit progress findings.

Phase 13 adds progress/fairness checks:

- escape-edge cycles without ranking or bounded progress are reported as
  `potential_nontermination`;
- missing forced progress is reported as `missing_progress_guarantee`;
- L13/L14-style cases are no longer merely known limitations.

Phase 14 adds contract composition and refinement:

- `FunctionContract`;
- trace contract checking;
- accepted input and output type checks;
- declared and forbidden write checks;
- postcondition checks;
- simple projection-refinement checks.

Phase 15 adds engineering hardening:

- versioned artifact schema helpers;
- thin `python -m flowguard` command wrappers;
- project template content helpers;
- pytest-style assertion helpers without external dependencies.

Phase 16 adds real adoption pilot support:

- project-local adoption logging;
- elapsed-time and command-result records;
- findings, counterexamples, skipped steps, friction points, and next actions;
- Skill rules for using flowguard in other projects without letting logs
  replace executable checks.

Phase 0 through Phase 7 delivered the MVP:

- core package structure;
- `FunctionResult`;
- `FunctionBlock`;
- `Workflow`;
- `Explorer`;
- `Invariant` and `InvariantResult`;
- `Trace` and `TraceStep`;
- `CheckReport`;
- `job_matching` example;
- broken duplicate-record and repeated-scoring models;
- unit tests;
- concept, modeling protocol, invariant examples;
- Codex Skill and AGENTS snippet.

Phase 8 delivered deterministic trace export and conformance replay:

- JSON-compatible trace and report export;
- replay adapter boundary;
- production observation/projection;
- conformance reports;
- `CorrectJobMatchingSystem`;
- broken duplicate-record production implementation;
- broken repeated-scoring production implementation.

Phase 9 delivered scenario sandbox and oracle review:

- `Scenario`;
- `ScenarioExpectation`;
- `run_exact_sequence`;
- `ScenarioRun`;
- `OracleReviewResult`;
- `ScenarioReviewReport`;
- expected-vs-observed status classification;
- job-matching S01-S15 correct and boundary scenarios;
- job-matching B01-B15 broken and meta scenarios.

Phase 10 delivered loop and stuck-state detection:

- reachable state graph construction;
- Tarjan SCC detection;
- bottom SCC detection;
- stuck-state detection;
- unreachable-success detection;
- terminal-with-outgoing-edge detection;
- `looping_workflow` L01-L14 review scenarios;
- explicit `known_limitation` handling for cycles with escape edges and no
  modeled progress guarantee.

Phase 10.5 delivers the evidence baseline and regression matrix:

- `EvidenceCaseResult`;
- `EvidenceBaselineReport`;
- unified status, group, and bug-class scorecard;
- current unit-test inventory;
- job-matching scenario review cases;
- job-matching conformance replay cases;
- job-matching model check cases;
- loop/stuck review cases;
- at least 100 structured evidence cases before Phase 11 starts.

Phase 10.6 delivers a roadmap-independent real software problem corpus:

- `ProblemCase`;
- `ProblemCorpus`;
- `ProblemCorpusReport`;
- real software problem taxonomy;
- deterministic 1500-case corpus;
- corpus quality runner;
- quality tests for case count, distribution, required fields, and duplicate IDs.

Important: Phase 10.6 case records describe real software problems. They do
not include Phase 11-15 roadmap mapping or current capability assessment.

Phase 10.7 extends the corpus with 500 gap-focused real software problem cases:

- identity merge/split/conflict;
- partial failure, atomicity, and compensation;
- ordering, deterministic interleavings, and duplicate delivery;
- permission, ownership, and module boundaries;
- time, expiry, scheduling, and delayed inputs;
- sync, reconciliation, and source-of-truth conflicts;
- schema, migration, and version compatibility;
- audit, privacy, compliance, and traceability;
- external integration acknowledgement and idempotency.

The expanded corpus contains 2000 deterministic cases: 1500 broad-coverage
cases plus 500 targeted gap cases. These records remain problem-space cases,
not future-phase assignments or current capability claims.

The current frozen main baseline extends that corpus with `pressure_100`,
bringing the total to 2100 deterministic cases. The pressure cases cover
bounded progress/fairness, eventual obligations, contract/refinement pressure,
and benchmark artifact stability.

Important distinction: the Phase 10.7 corpus quality report describes the
problem-intent matrix. It is not itself an executable-test report. Phase 10.8
adds the executable-test report.

Phase 10.8 delivers an executable corpus harness:

- iterate over the current `ProblemCase` records;
- run real flowguard checks for every case;
- produce expected-vs-observed status for each executed case;
- count `not_executable_yet` honestly, with the current target at zero;
- include trace or graph evidence where available;
- report total problem cases separately from executable behavior cases.

The current executable runner reports `total_cases=2100`,
`executable_cases=2100`, `not_executable_yet=0`, `coverage_complete=True`, and
`failure_cases=0`.

The current project has shown that, within finite deterministic abstract
models and explicit scenario catalogs, `flowguard` can catch many workflow-level
and side-effect-level bugs that AI coding agents commonly introduce:

- duplicate side effects;
- missing deduplication;
- repeated scoring or processing without refresh;
- wrong state owner;
- cache/source mismatch;
- downstream non-consumable output;
- missing decision;
- contradictory decision;
- idempotency failure;
- closed loop;
- stuck state;
- unreachable success.

The current project has not proven:

- complete production-system correctness;
- unbounded termination;
- all real business cases;
- complete fairness/progress proof for all cycles;
- all identity-conflict policies;
- conformance of every real implementation;
- correctness in a full formal-methods sense.

## 3. Guiding principles

- Math first, packaging later.
- Deterministic first, random later.
- Executable model, not prose.
- Expected vs observed, not just pass/fail.
- Human review is allowed and honest.
- Known limitations must be visible, not hidden.
- Do not weaken invariants to pass checks.
- Do not let adapter projection hide production bugs.
- Do not replace counterexample traces with summary strings.
- Every remaining upgrade must be measured against the frozen 2100-case
  baseline: write the expected improvement first, run the full benchmark after
  implementation, compare expected vs observed status deltas, and only then
  move to the next phase.
- Do not prioritize CLI, packaging, or release mechanics before benchmark value
  is proven.
- Do not skip benchmark breadth and jump directly to adoption tooling.
- Preserve the current core math:

```text
F: Input x State -> Set(Output x State)
```

## 4. Phase 11 - Full Real-Model Benchmark Binding and Mutation Scorecard

### Goal

Prove that `flowguard` is not only a `job_matching` toy example and not only a
generic corpus harness. Bind the full real software problem corpus to real
workflow-family-specific executable models.

Each benchmark family should include:

- a correct model;
- broken variants;
- scenario catalog;
- expected oracle;
- scenario review;
- optional loop review;
- optional conformance review;
- benchmark scorecard.

The required completion claim is not "some benchmark families exist." The
required completion claim is:

```text
total_cases = 2100
real_model_cases = 2100
generic_fallback_cases = 0
not_executable_yet = 0
failure_cases = 0
model_variant_total = 150
model_families_with_six_variants = 25
```

The Phase 11.2 hardening claim is stronger:

```text
variant_min_cases >= 8
variants_below_target = 0
families_missing_required_case_kinds = 0
families_missing_required_bug_classes = 0
benchmark_conformance_family_count = 25
production_conformance_family_count = 26
total_replays = 78
failures = 0
```

Multiple cases may share a model variant, but every case must bind to a
specific `variant_id`. A single generic `CorpusApply`-style template is not
enough, and 25 family-level model factories are no longer the mature target.

### Benchmark families

1. `cache_consistency`

   Validate stale cache, cache/source mismatch, output without source, and
   duplicate output on reprocess.

2. `retry_side_effect`

   Validate retry-created duplicate side effects, send-before-idempotency-key,
   duplicate send on retry, unbounded retry, and missing terminal status after
   a side effect.

3. `file_processing_pipeline`

   Validate repeated file processing, duplicate output write, parse output that
   downstream cannot consume, write without transform, and wrong state owner.

4. `task_queue`

   Validate double lease, complete without lease, completed task still queued,
   retry forever, and terminal semantics.

5. `llm_decision_pipeline`

   Model uncertain LLM output categories without calling an LLM API. Validate
   unknown dropped, unhandled category, repeat classification without refresh,
   accept-then-ignore conflict, and downstream routing completeness.

6. `state_owner_boundary`

   Validate module ownership boundaries, forbidden writes, and side effects
   without source traceability.

### Mathematical meaning

Phase 11 tests the portability of the existing function-flow model:

```text
F: Input x State -> Set(Output x State)
```

The question is whether the same abstraction can express all workflow families
in the 2100-case corpus and still expose the same bug classes through
deterministic exhaustive paths, scenario oracles, and loop checks.

### Engineering meaning

Phase 11 should answer:

- Is `flowguard` useful beyond `job_matching` and beyond a generic harness?
- Can all 2100 problem-intent cases be grounded in real domain models?
- Which bug classes are natural fits?
- Which bug classes require custom oracle checks?
- Which cases require `needs_human_review`?
- Which cases are known limitations until future math exists?

### Deliverables

- `flowguard/benchmark.py`
- workflow-family-specific real model specs for the 2100-case corpus
- real-model corpus runner
- `docs/benchmark_zoo.md`
- `BenchmarkCase`
- `BenchmarkResult`
- `BenchmarkSuite`
- `BenchmarkScorecard`
- mutation scorecard grouped by bug class

### Non-goals

- No CLI.
- No packaging.
- No external dependencies.
- No random testing.
- No Hypothesis.
- No production conformance expansion yet beyond optional examples.
- No attempt to prove unbounded correctness.

### Acceptance criteria

- All 25 workflow families in the 2100-case corpus have model specs.
- All 2100 cases bind to real domain model execution.
- `generic_fallback_cases=0`.
- All 25 workflow families have exactly six model variants.
- `model_variant_total=150`.
- Each model family has correct and broken variants through the bound cases.
- The runner outputs one unified scorecard.
- The scorecard shows expected pass, expected violation, caught violation,
  missing violation, human review, and known limitation counts.
- Results are grouped by bug class.
- Existing tests and examples still pass.
- No external dependencies, randomness, CLI, packaging, or release work.

## 5. Phase 12 - Production Conformance Benchmark

### Goal

Extend the benchmark zoo from abstract model checking into production
conformance replay. The question becomes:

```text
When real implementation behavior diverges from the abstract model, does
flowguard catch it?
```

Every benchmark should add:

- `CorrectProductionSystem`;
- `BrokenProductionSystem` variants;
- `ReplayAdapter`;
- representative traces;
- conformance replay report;
- aggregate conformance scorecard.

### Mathematical meaning

Phase 12 validates the replay relationship:

```text
abstract trace
  -> production replay
  -> projected observed state/output
  -> compare with expected abstract behavior
```

Real implementation state does not need to equal abstract state. It must be
observable through projection:

```text
pi(RealState) = AbstractState
```

Production behavior may have different internal structure, but its projected
behavior must not take steps forbidden by the abstract model.

### Engineering meaning

Phase 12 tests whether conformance replay is useful beyond one example. It
should expose broken production implementations such as stale cache, duplicate
send on retry, duplicate file output, double task lease, unknown decision drop,
and wrong module mutation.

### Recommended coverage

1. `cache_consistency` production conformance

   Broken production variants:

   - does not update cache;
   - uses stale cache;
   - outputs without source;
   - duplicates output.

2. `retry_side_effect` production conformance

   Broken production variants:

   - retry sends twice;
   - send happens before idempotency key;
   - terminal status is missing.

3. `file_processing_pipeline` production conformance

   Broken production variants:

   - same file writes output twice;
   - parse returns wrong type;
   - write occurs without transform.

4. `task_queue` production conformance

   Broken production variants:

   - double lease;
   - complete without lease;
   - completed task remains queued.

5. `llm_decision_pipeline` production conformance

   Broken production variants:

   - unknown category is dropped;
   - unhandled category;
   - repeated classification;
   - contradictory final action.

6. `state_owner_boundary` production conformance

   Broken production variants:

   - wrong module mutates wrong state;
   - adapter projection hides raw bug unless explicitly checked.

### Deliverables

- production systems for each benchmark;
- replay adapters for each benchmark;
- representative trace selection helpers;
- aggregate conformance report;
- conformance scorecard grouped by benchmark and bug class;
- documentation explaining refinement/simulation at an engineering level.

### Non-goals

- No real business systems.
- No database.
- No network services.
- No GUI.
- No complete formal proof.
- No automatic adapter generation.
- No projection that silently repairs production bugs.

### Acceptance criteria

- Each benchmark has at least one correct production implementation.
- Each benchmark has at least two broken production variants.
- Aggregate conformance report shows total, passed, and failed cases.
- Broken production variants are caught.
- Adapter/projection does not automatically deduplicate, normalize away, or
  repair real bugs.
- Docs explain refinement/simulation without overclaiming formal proof.
- Existing tests and examples still pass.

## 6. Phase 13 - Progress, Fairness, and Temporal Properties

### Goal

Add a stronger mathematical layer for workflows with cycles that have escape
edges but no guaranteed progress.

Phase 10 catches closed bottom SCCs:

```text
maybe -> rewrite -> maybe
```

But it does not prove progress for:

```text
maybe -> done
maybe -> rewrite
rewrite -> maybe
```

There is an escape to `done`, but the model may still allow infinite
`maybe -> rewrite -> maybe -> rewrite -> ...` behavior.

### Mathematical meaning

Phase 13 introduces progress/liveness-style checks while staying pragmatic:

- bounded progress properties;
- eventually properties over traces;
- ranking-function checks;
- potential non-termination for cycles with escape edges and no modeled
  progress.

Examples:

```text
if state enters maybe, it must reach done / needs_human / ignored within N steps
record(job) -> eventually decision(job)
lease(task) -> eventually completed / failed / needs_human
remaining_retries decreases
remaining_rewrites decreases
```

### Engineering meaning

Phase 13 should turn current `known_limitation` cases such as L13/L14 into
actionable findings like `potential_nontermination` or
`missing_progress_guarantee`.

It should help model:

- retry limits;
- rewrite limits;
- human review loops;
- queue progress;
- refresh cycles;
- tasks that must eventually settle.

### Deliverables

- `flowguard/progress.py` or `flowguard/temporal.py`
- `ProgressProperty`
- `EventuallyProperty`
- `BoundedEventuallyProperty`
- `RankingFunctionCheck`
- progress review report
- expanded `examples/looping_workflow`
- `docs/progress_properties.md`

### Non-goals

- No complete temporal-logic engine.
- No full LTL/CTL implementation.
- No unbounded formal liveness proof.
- No random testing.
- No external model checker.

### Acceptance criteria

- L13/L14 are no longer only `known_limitation`; they are at least flagged as
  `potential_nontermination` or `missing_progress_guarantee`.
- Good bounded retry passes.
- Bad unbounded retry fails.
- Good rewrite limit passes.
- Bad rewrite no-progress fails.
- Trace-based eventually properties can be checked.
- Ranking-function checks can identify monotonic progress or missing progress.
- Docs clearly state that this is not complete liveness proof.

## 7. Phase 14 - Contract Composition and Refinement

### Goal

Make function-block contracts more explicit without breaking the current
`FunctionBlock` API. The current model already has:

```text
Input x State -> Set(Output x State)
```

Phase 14 adds a richer contract layer around that core behavior.

### Mathematical meaning

Each block should be able to declare a `FunctionContract`:

- accepted input type;
- output type;
- preconditions;
- postconditions;
- reads;
- writes;
- forbidden writes;
- idempotency rule;
- traceability rule;
- failure modes;
- downstream compatibility;
- ownership constraints.

The composition question is:

```text
Does A's output satisfy B's input precondition?
Does B's output satisfy C's input precondition?
Does each state transition satisfy the block's own contract?
```

The refinement question is:

```text
pi(RealState) = AbstractState
```

and:

```text
each real step, after projection, is allowed by the abstract model
```

### Engineering meaning

Phase 14 should catch:

- output-input incompatibility;
- precondition/postcondition failure;
- forbidden state writes;
- side effect without source trace;
- idempotency contract violations;
- real code that does not refine the abstract model.

### Deliverables

- `FunctionContract`
- `ContractCheckReport`
- contract composition checker
- ownership checker
- traceability checker
- refinement/simulation helper
- `docs/contract_composition.md`
- `docs/refinement.md`

### Non-goals

- No rewrite of existing `FunctionBlock` models.
- No mandatory migration of every benchmark in one phase.
- No complex plugin system.
- No full formal verification system.

### Acceptance criteria

- Output-input compatibility can be checked.
- Preconditions and postconditions can be checked.
- Reads, writes, and forbidden writes can be checked.
- Idempotency contracts can be checked.
- Traceability contracts can be checked.
- Simple production refinement can be checked.
- Existing FunctionBlock API remains valid.
- Benchmarks can migrate incrementally.

## 8. Phase 15 - Engineering Hardening and Real Workflow Adoption

### Goal

Only after Phases 11-14 establish broader value and stronger math should
`flowguard` receive engineering hardening for real project adoption.

Phase 15 is primarily engineering and productization, not a new mathematical
core.

### Engineering meaning

Make `flowguard` stable and ergonomic for Codex and real repositories while
preserving the model-first discipline.

### Work areas

1. Stable trace schema and versioning

   - `schema_version`
   - `artifact_type`
   - `created_by`
   - `model_name`
   - `scenario_name`
   - `trace_id`
   - deterministic serialization
   - load/save backward compatibility

2. CLI

   Example command shapes:

   ```text
   python -m flowguard check ...
   python -m flowguard scenario-review ...
   python -m flowguard loop-review ...
   python -m flowguard benchmark ...
   python -m flowguard conformance ...
   ```

   CLI must wrap the Python API, not replace it.

3. pytest adapter

   Optional adapter for running scenario review, conformance replay, and
   benchmark scorecards in pytest.

4. project templates

   Provide:

   - `model.py`
   - `scenarios.py`
   - `run_checks.py`
   - `conformance.py`
   - `run_conformance.py`
   - `run_scenario_review.py`

5. Codex Skill hardening

   The skill should require:

   - model first;
   - scenario sandbox before production edits;
   - loop/progress checks when workflows can cycle;
   - production conformance after implementation;
   - explicit explanation when a step is skipped.

6. AGENTS.md snippet

   Provide reusable rules for other projects.

7. Packaging and release

   Consider only after internal validation is stable:

   - `pyproject.toml`
   - versioning
   - README
   - examples gallery
   - optional GitHub Actions

### Mathematical meaning

Phase 15 should not change the core math. It should preserve and expose the
modeling layers built in previous phases.

### Non-goals

- Do not trade mathematical clarity for CLI convenience.
- Do not hide `needs_human_review` or `known_limitation` in automation output.
- Do not make packaging the reason to freeze weak APIs too early.

### Acceptance criteria

- `flowguard` can be started quickly in a new project from templates.
- Codex can follow the Skill reliably.
- CLI can run core commands.
- pytest adapter is optional and usable.
- Trace schema is stable.
- Documentation is clear enough for real adoption.
- Engineering packaging does not weaken invariants or obscure limitations.

## 8.1. Phase 16 - Real Adoption Pilot and Usage Logging

### Goal

Make flowguard usable in other projects as a Codex Skill workflow while
recording real usage evidence for future optimization.

### Engineering meaning

Phase 16 adds a lightweight adoption record around the existing Python API and
Skill. It records:

- why flowguard was triggered;
- which model files were used;
- which checks ran;
- elapsed time;
- findings and counterexamples;
- skipped steps and reasons;
- friction points;
- next actions.

### Mathematical meaning

Phase 16 does not change the core model:

```text
F: Input x State -> Set(Output x State)
```

It records whether the existing model-first, scenario, conformance, progress,
and contract checks were actually used in real tasks. This helps decide which
future mathematical or engineering upgrades are justified by observed use.

### Deliverables

- `flowguard/adoption.py`;
- adoption log templates;
- Skill adoption protocol reference;
- real adoption documentation;
- tests for JSON, JSONL, Markdown, timing, and template behavior.

### Acceptance criteria

- Adoption entries are structured and JSON-serializable.
- Human-readable Markdown entries can be generated.
- JSONL and Markdown append helpers create parent directories.
- Skill instructions require logging real usage, skipped steps, timing,
  findings, counterexamples, friction, and next actions.
- Logging never substitutes for executable checks.

### Non-goals

- No telemetry service.
- No database.
- No GUI.
- No network upload.
- No packaging or release changes.
- No new mathematical checker.

## 9. Non-goals for now

- No GUI.
- No database.
- No LLM API.
- No Monte Carlo.
- No probabilistic modeling.
- No random testing before deterministic benchmark value is stable.
- No packaging before benchmark value is proven.
- No real production adoption before conformance benchmark is mature.
- No CLI before Phase 11 and Phase 12 prove the approach across multiple
  workflow types.
- No release work before the core math, scenario review, conformance benchmark,
  and progress/contract roadmap are stable.

## 10. Decision log

### Why Phase 10.5 comes before Phase 11

Phase 11 should expand `flowguard` into a benchmark zoo, but expansion only
matters if there is a stable baseline to compare against. Phase 10.5 freezes
the current evidence picture:

```text
what passes
what is expected to fail and is caught
what needs human review
what is a known limitation
what bug classes are currently covered
```

This prevents blind upgrades. A later phase should show a measurable change in
the scorecard, such as a new bug class being caught or a known limitation being
reduced, without regressing existing evidence.

### Why Phase 10.6 comes before Phase 11

Phase 10.5 tells us what the current implementation already covers. Phase 10.6
defines the broader real software problem space independently of the roadmap.
This avoids designing tests around the next implementation phase.

Phase 10.6 cases should answer:

```text
What real software workflow can fail?
What input and state shape exposes the failure?
What behavior is expected?
What behavior is forbidden?
What evidence would reveal the issue?
```

They should not answer:

```text
Which future phase owns this?
Can current flowguard already catch it?
```

Those are later analysis questions. The corpus itself is a problem-space map,
not a roadmap-derived capability map.

### Why Phase 10.7 expands the corpus before Phase 11

The first 1500 corpus cases provide broad structured coverage, but broad
coverage can underrepresent the most accident-prone situations in real
software: identity conflicts, partial commits, out-of-order events, permission
boundary changes, expiry windows, reconciliation conflicts, schema transitions,
audit/privacy traceability, and external acknowledgements.

Phase 10.7 adds 500 targeted cases for these weak spots before benchmark work
begins. This keeps the next development phase honest: future executable
benchmarks can be selected from a larger problem-space map instead of being
invented around whichever implementation happens to be easiest.

### Why Phase 10.8 comes before Phase 11

The corpus is valuable only if the project does not confuse problem intent with
execution evidence. Phase 10.8 is the correction layer: it turns corpus records
into executable expected-vs-observed checks and would explicitly mark any
unmapped cases as `not_executable_yet`.

This prevents a false conclusion that the full corpus passed when only the corpus
structure was validated. Phase 11 should build benchmark families only after
the executable corpus report is checked.

### Why Phase 11 uses the full corpus, not a subset

A sampled benchmark zoo would only prove that the selected cases work. It would
not answer whether `flowguard` can serve as a broad software-workflow
capability baseline. Phase 11 therefore binds the full corpus to real
workflow-family-specific models.

The required gate is:

```text
real_model_cases = 2100
generic_fallback_cases = 0
```

The implementation may share model factories across cases, but each factory
must be specific to its workflow family and must expose concrete block names,
state slots, model variants, and structural evidence. A generic executable
template remains useful for plumbing history, but it cannot be counted as a
real-model benchmark.

### Why pressure cases are in the main baseline

The `pressure_100` cases were added before the next mathematical upgrades so
future work is tested against pre-existing expectations. They are not a side
suite and should not be quietly dropped. The escape-edge progress cases started
as `known_limitation`; Phase 13 turned them into executable progress findings
instead of simply relabeling the status.

### Why Phase 11 comes before CLI

CLI would make `flowguard` easier to run, but it would not prove that the method
works beyond `job_matching`. Phase 11 must come first because benchmark breadth
is the next evidence question:

```text
Does the same function-flow method catch the same bug classes across different
workflow families?
```

Packaging a weak or narrow method would create tool-shaped confidence before
the model value is proven.

### Why Phase 12 follows Phase 11

Abstract benchmarks prove that the modeling method works across workflow types.
Production conformance benchmarks prove that real implementations can be
checked against those models. This sequence keeps the problem decomposed:

1. prove abstract modeling breadth;
2. prove production replay breadth.

### Why Phase 13 is a mathematical upgrade

Phase 10 detects closed bottom SCC loops and stuck states. Phase 13 addresses
progress and fairness cases where a cycle has an escape edge but no guarantee
that the escape will be taken. That is a stronger behavioral property, not a
packaging feature.

### Why Phase 14 is a mathematical and architectural upgrade

Phase 14 makes function contracts explicit and composable. It adds pre/post
conditions, ownership constraints, traceability rules, and refinement checks.
This strengthens what it means for one block, one workflow, or one production
implementation to satisfy the model.

### Why Phase 15 comes last

CLI, packaging, pytest adapters, templates, and release automation are useful
only after the modeling method has been validated across benchmark types,
production conformance, progress checks, and contract checks. Engineering
hardening should expose proven behavior, not compensate for missing evidence.

### Why Phase 16 records real adoption before further expansion

After Phase 15, the next risk is not another missing wrapper. The risk is
unclear real-world usefulness: whether agents actually trigger flowguard at the
right time, how long modeling takes, which checks are skipped, which
counterexamples matter, and which parts create friction. Phase 16 records those
facts in project-local logs so later improvements are based on observed use
rather than guesses.

The adoption log is evidence about usage quality. It is not a substitute for
model checks, scenario review, conformance replay, progress checks, or contract
checks.

### Why Phase 16.4 models the product boundary and Skill trigger

Real adoption showed that FlowGuard should not collect every external project
model as a reusable template. Each project benefits from a situational model for
the current behavior boundary. The public product should therefore stay small:
core package, modeling protocol, invariant patterns, Skill, AGENTS snippet,
minimal templates, lightweight logs, and examples.

The richer feedback system remains internal: benchmark corpus, private pilots,
KB feedback, daily review, and adoption review. Phase 16.4 models this boundary
so a future public GitHub release does not leak internal/private maintenance
artifacts or omit the Skill trigger that makes agents remember model-first
checks.

Phase 16.4 also models Skill trigger reliability. The key product risk is not
template volume; it is agents forgetting to use FlowGuard for risky architecture,
state, workflow, retry, cache, deduplication, idempotency, side-effect, or
module-boundary work, or overusing it on trivial tasks.

### Why Phase 13-15 require benchmark gates

The project now has a frozen 2100-case real-model baseline. Future upgrades
should be judged by whether they improve pre-existing expected-vs-observed
evidence, not by whether new implementation-specific tests pass. Each remaining
phase should therefore start with a recorded hypothesis, run the full baseline
after implementation, compare status deltas, and document whether the upgrade
actually reduced a limitation, exposed a better finding, or preserved existing
capability without regression.

This is especially important for Phase 13 and Phase 14:

- Phase 13 should reduce the current progress/fairness limitation by turning
  escape-edge cycles into explicit progress findings when appropriate.
- Phase 14 should move contract/refinement pressure from scenario-only evidence
  toward explicit contract checks.

If a phase does not improve the intended evidence category, it should be
reported honestly as incomplete or ineffective rather than renamed as success.

### Why the current core math should not be replaced

The value of `flowguard` comes from a small, stable abstraction:

```text
F: Input x State -> Set(Output x State)
```

This abstraction already supports branching, repeated inputs, invariant
checking, scenario oracle review, counterexample traces, conformance replay,
and reachable graph checks. Future phases should extend it with benchmarks,
progress properties, contracts, and refinement rather than replacing it with a
different test framework, prompt layer, random generator, or probabilistic
system.
