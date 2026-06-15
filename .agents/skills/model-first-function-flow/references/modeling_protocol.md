# Modeling Protocol

This document is the `core_modeling` sub-protocol for the FlowGuard Skill
Kernel. The main Skill routes here for ordinary model-first work. Specialized
routes such as UI flow structure, code structure recommendation, model-test
alignment, model topology hazard review, ModelMesh, TestMesh, StructureMesh,
DevelopmentProcessFlow, model-miss review, conformance/adoption, long-check
observability, and framework upgrades live in their dedicated reference
protocols.

Use this protocol before implementing non-trivial behavior involving workflows, state, retries, deduplication, idempotency, caching, or module boundaries.

## 0. Choose The Lightest Mode

Before changing files, separate three situations:

- `read_only_audit`: inspect an existing project without changing production
  code. Run import preflight, existing FlowGuard models/replays when present,
  adoption evidence review, and stale fallback checks. Do not create a new model
  solely because the task is read-only.
- `model_first_change`: production behavior may change. Build or update the
  fit-for-risk model before editing production code. If no FlowGuard model
  exists yet, create one from the current plan or adapt the model template.
- `model_maintenance`: existing `.flowguard` models, replay adapters, or
  adoption evidence appear stale. Update those artifacts before making claims
  from them.
- `layered_boundary_proof`: parent model confidence depends on child models and
  leaf real-code boundary evidence. Join parent coverage, child disjointness,
  child reattachment, and leaf boundary-matrix rows before claiming the parent
  stayed inside its model.
- `model_test_alignment`: model obligations and ordinary tests both exist, and
  the risk is whether scenarios, invariants, hazards, transitions, or contracts
  have matching current test evidence.
- `model_topology_hazard_review`: a locally green model topology may imply
  future-use hazards before broad done/release/publish confidence. Read the
  topology and usage intent, then promote only hazards with concrete anchors.
- `test_mesh_maintenance`: validation is too large, broad, stale-prone, or
  layered to trust as one flat test command or script. Build a TestMesh that
  partitions parent test confidence into child-suite/script ownership and
  evidence contracts.
- `structure_mesh_maintenance`: structure refactoring is the risky boundary.
  Build a StructureMesh that partitions a large script, package, module,
  command, or API surface into child-module ownership and compatibility
  evidence contracts.
- `code_structure_recommendation`: implementation structure is unclear or the
  user asks for a code architecture recommendation. Use or create a FlowGuard
  functional model, then recommend module boundaries, ownership maps, facades,
  side-effect adapters, and validation boundaries without writing production
  code.
- `ui_flow_structure`: UI interaction behavior itself needs modeling before
  layout or visual design. Build or review the UI interaction model first,
  then derive parent/child UI topology, menu levels, stable placements,
  overlays, navigation ownership, state/control/event ownership, and the UI
  text hierarchy blueprint for headings, labels, action text, state/status
  messages, helper text, and error/recovery copy slots.
- `development_process_flow`: non-trivial staged development or modification
  with validation, development lifecycle ordering, artifact overwrite,
  validation evidence freshness, peer writes, V-style validation pairs, or
  minimum revalidation is the risky boundary. Use this sibling route to review
  lifecycle rows without supervising ModelMesh, TestMesh, StructureMesh, or
  Model-Test Alignment internals.
- `model_maturation_loop`: later model-miss, model-test, state-closure,
  ModelMesh, code-boundary, or freshness evidence says the model itself is too
  coarse, stale, disconnected, or only supports a scoped claim. Translate that
  signal into a model-upgrade action before broad confidence is claimed.
- `development_process_flow_post_change_scan`: after non-trivial
  FlowGuard-managed work, DevelopmentProcessFlow consumes changed artifacts,
  remembered maintenance obligations, stale evidence, skipped routes, and
  split/reduction signals, then sends each unresolved item to its existing
  owner route.

If real FlowGuard is importable but a current `.flowguard` Python model still
claims `flowguard_package_available = False`, uses a fallback finite runner, or
defines local replacement `Workflow` or finite-runner classes, record a
`stale_fallback_model` warning. This is a confidence gap, not a hard failure.
If a current `.flowguard` model calls the internal finite runner directly without a
`FlowGuardCheckPlan`, `RiskIntent`, `MinimumModelContract`, and
`KnownBadProof`, record `direct_runner_formal_entry_required` and upgrade the
model before making a complete FlowGuard claim.

## 0.2 Enter The Process Simulator For Rough Plans

When the request is non-trivial but still a rough idea, short plan, or
AI-generated outline, enter `flowguard-development-process-flow` first as the
development-process simulator and record `plan_detailing` before writing the
behavior model. Delegate to PlanDetailing when full rows are needed. Create
`PlanDetail` rows for goal, sources, risk surfaces, artifacts, state surfaces,
side effects, ordered steps, receipts, validation, failure branches, rework
gates, human-review questions, freshness rules, and final evidence. Run
`review_plan_detail(...)` and keep scoped or missing rows visible.

After delegated detail review, project rows with `plan_detail_to_plan_intake(...)`,
`plan_detail_to_step_contracts(...)`,
`plan_detail_to_development_process(...)`, and
`plan_detail_to_agent_workflow_plan(...)` as needed. A plan-detail pass means
the plan is detailed enough to proceed; it is not implementation or production
confidence.

Keep the API surface boundary clear:

- core modeling primitives use `FunctionBlock`, `FunctionResult`, `Invariant`,
  and `Workflow`;
- formal model-first entry uses `FlowGuardCheckPlan`,
  `run_model_first_checks`, `RiskIntent`, `MinimumModelContract`,
  `KnownBadProof`, template reuse/no-match review, and template harvest closure;
- reporting helpers explain gaps and skipped work, but warnings are not hard
  failures;
- evidence and benchmark helpers are mainly for FlowGuard maintenance and
  upgrade validation, not ordinary project gates.

See `docs/api_surface.md` for the public API layer map.

## 0.25 Create Or Evolve The Model Script

FlowGuard does not require an existing production implementation or an existing
model script. It does require the real `flowguard` package to be connected
before claiming FlowGuard adoption. When that import preflight passes and no
model exists yet, create one from the current plan or adapt the included model
template. The model script is the executable design artifact that makes the
proposed workflow inspectable.

The first model should be small enough to review, but it does not have to be
the shortest possible script. It should be fit for the customer's risk: include
the state, branches, retries, side effects, ordering constraints, and invariants
needed to make the important failure modes visible. When later work reveals new
risks, revise, strengthen, or connect the model instead of treating the first
version as final.

When creating or materially updating a FlowGuard model file, put a short
**Risk Purpose Header** at the top of the model. It should identify FlowGuard
and link to `https://github.com/liuyingxuvka/FlowGuard`, then explain which
workflow the model reviews, which concrete bugs or invalid states it guards
against, when future agents should run or update it, and the companion command
that runs the checks. Keep this as a lightweight model header; do not add
manifest files or extra project scaffolding unless the task separately requires
them.

## 0.3 Satellite Route Handoffs

Keep the kernel small. When one of these signals is present, stop expanding the
case here and load the direct satellite route or the compact handoff stub named
below. Satellite details stay in the satellite-owned reference.

| Signal | Route | Load next |
| --- | --- | --- |
| Model obligations and ordinary tests both need current evidence parity. | Model-Test Alignment | `.agents/skills/flowguard-model-test-alignment/references/model_test_alignment_protocol.md` |
| Three or more local models, an oversized model, stale child evidence, or a parent/child model claim. | ModelMesh | `.agents/skills/flowguard-model-mesh/references/model_mesh_protocol.md` |
| Model, test, mesh, miss, or code-boundary evidence says the model is too coarse or stale. | Model maturation loop | Stay in this protocol and use `review_model_maturation_loop(...)`; then rerun the owning route. |
| Changed artifacts, remembered maintenance obligations, stale evidence, or skipped routes need owner-route review. | Maintenance scan router | Use `review_maintenance_scan(...)`; then rerun the owner route. |
| Validation is large, slow, layered, backgrounded, stale-prone, or parent/child suite-owned. | TestMesh | `.agents/skills/flowguard-test-mesh/references/test_mesh_protocol.md` |
| A large script, module, command, API, facade, config, or public entrypoint split needs structure ownership evidence. | StructureMesh | `.agents/skills/flowguard-structure-mesh/references/structure_mesh_protocol.md` |
| The next step is an implementation structure recommendation rather than code edits. | Code Structure Recommendation | `.agents/skills/flowguard-code-structure-recommendation/references/code_structure_recommendation_protocol.md` |
| UI controls, screens, overlays, navigation, display ownership, or copy hierarchy need interaction modeling. | UI Flow Structure | `.agents/skills/flowguard-ui-flow-structure/references/ui_flow_structure_protocol.md` |
| Model topology suggests future-use hazards before broad confidence. | Model Topology Hazard Review | `.agents/skills/flowguard-model-topology-hazard-review/references/topology_hazard_protocol.md` |
| Plan/edit/test/fix/verify ordering, artifact versions, peer writes, freshness, done, release, archive, or publish confidence is the risky boundary. | DevelopmentProcessFlow | `.agents/skills/flowguard-development-process-flow/references/development_process_flow_protocol.md` |
| Runtime, tests, replay, logs, or manual validation failed after FlowGuard confidence. | Model-Miss Review | `.agents/skills/flowguard-model-miss-review/references/model_miss_protocol.md` |

Kernel-side files such as
`.agents/skills/model-first-function-flow/references/model_mesh_protocol.md`
are handoff stubs only. They preserve legacy reference paths, but the detailed
protocol lives with the satellite skill.

## 0.5 Write A Minimum Valuable Risk Intent

Before defining state or function blocks, write the short brief that tells the
model what accidents it is meant to expose. This is the agent's own preflight;
ask the user only when materially different risk priorities exist and the
protected harm cannot be inferred safely.

Answer these questions before creating or editing the model:

- Which failure modes are we trying to prevent?
- Which protected error class should this model make impossible or visible?
- Which public packaged or local per-machine risk templates match this risk?
  Record used template ids, or record a no-match reason.
- How will this model record template harvest closure after validation: write a local
  candidate, merge an existing template, duplicate-link an existing template,
  or record an accepted not-harvestable reason?
- What protected harms would happen if those failures slipped through?
- Which state fields, side effects, confirmations, durable records, or external
  commitments must be modeled or the failure would be invisible?
- Which completion evidence proves the workflow is actually done?
- Which useful business path is being proven: path id, business intent,
  trigger, expected terminal, state writes, side effects, equivalent/exclusive
  paths, old-path disposition, and evidence ids?
- Which adversarial inputs, repeated inputs, retries, partial successes,
  ordering changes, concurrent actions, or exception branches must be simulated?
- Which representative known-bad implementation or trace should fail?
- Which hard invariants must never be weakened merely to pass checks?
- What blindspots remain because the model is intentionally smaller than the
  real workflow?

The first/default model should be a minimum valuable model, not a happy-path
stub. It can stay small, but it needs state, side effects or completion
evidence, and at least one known-bad case with current proof that the broken
variant fails unless the claim is explicitly scoped.
Search packaged public templates and the per-machine local template library
before generating a new or materially deepened model. Before a complete claim,
record template harvest closure: write a local candidate, merge an existing template,
duplicate-link an existing template, or record an accepted not-harvestable
reason. Missing closure means the model is not fully done.

Put the brief into `RiskProfile` through a `RiskIntent` or equivalent
`risk_intent` mapping, bind the minimum model contract and known-bad proof on
the `FlowGuardCheckPlan`, and run `run_model_first_checks(plan)`. Direct
Direct finite engine calls remain internal execution primitives, not the formal
entry for non-trivial model creation.

When the workflow has multiple useful routes or old/new alternatives, pass the
same business path identity into topology hazard review, model similarity, and
runtime path evidence. A node-level pass is not enough if the real code may have
proved the wrong business path.

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
required. Unknown input/state values are handled by the automatic state-closure
gate in `run_model_first_checks(...)`; undeclared policy scopes confidence and
unsafe handling blocks it.

For common risks, optional domain packs can reduce boilerplate:
`DeduplicationPack`, `CachePack`, `RetryPack`, and `SideEffectPack`. A pack only
uses selectors and key functions you provide. It does not infer state, enforce
a model shape, or become a required structure.

For neutral starter scaffolds, the public CLI can print or write templates:

```powershell
python -m flowguard project-template --output .
python -m flowguard risk-intent-template --output .
python -m flowguard model-miss-template --output .
python -m flowguard code-structure-recommendation-template --output .
python -m flowguard structure-mesh-template --output .
```

Treat them as starting points only. Rename the state, inputs, outputs,
invariants, and blindspots to match the real workflow before claiming
confidence.

For recurring multi-role maintenance systems, such as
Sleep/Dream/Architect/Installer/Reviewer flows, the optional maintenance
template can reduce setup time:

```powershell
python -m flowguard maintenance-template --output .
```

It scaffolds repeated-action, missing-report, and install-sync checks. Rename
the roles and state fields before treating it as project evidence.

## 9. Run The Formal Check Plan With Repeated Inputs

Choose:

- `external_inputs`
- `initial_states`
- `max_sequence_length`
- optional required labels or reachable predicates

Always include repeated-input exploration when duplicate side effects are possible. For one input and length two, the explorer must check both `[x]` and `[x, x]`.

The formal runner delegates finite exploration to the internal model runner,
which emits bounded progress on `stderr` by default, counted by top-level
`initial_state x input_sequence` work units. This helps agents distinguish a
long serial run from a silent process, but it is not pass/fail evidence and it
does not change report semantics. Use plan progress settings or
`FLOWGUARD_PROGRESS=0` when a strict environment requires no progress output.

Put the intended coverage boundary in `RiskProfile`, create a
`FlowGuardCheckPlan`, bind the minimum model contract, known-bad proof, template
reuse/no-match review, and harvest closure, then call
`run_model_first_checks(plan)`. The runner performs the minimum model review,
known-bad proof review, audit, optional scenario scaffolding, finite model run,
counterexample minimization, scenario review, optional
progress/contract/conformance sections, and a unified summary.

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

An unchanged abstract run does not need to be repeated just because production
code was edited. If the same model, scenarios, oracle, invariants, risk
boundary, and task revision already passed, it is acceptable to reuse that
result and spend the post-edit check on focused tests, conformance replay, or
other production-facing evidence. Rerun the abstract model when its inputs
changed, previous evidence is unavailable or stale, a counterexample or design
revision needs confirmation, the user asks for a refresh, or a quick rerun
would materially help confidence.

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

## 13.5 Handle Bug Repairs And Post-Runtime Model Misses

Treat a non-trivial bug repair, or a runtime, test, replay, log, or
manual-validation failure that appears after a FlowGuard pass, as a model-miss
review trigger until proven otherwise. The earlier pass is still useful, but it
is provisional evidence, not a reason to patch and finish directly.

When this happens:

1. Reopen the model-first work and keep completion blocked while the model-miss
   obligation is open.
2. Run existing-model preflight when the bug is inside an existing modeled
   system, then build or inspect the finding ledger across invariant/model checks,
   model-quality audit, scenario or live-audit evidence, progress, contracts,
   conformance, skipped/not-run sections, and adoption evidence. The ledger is
   the coverage-first view used to avoid patching only the visible failure.
3. Classify why the prior model missed the issue with one of the practical
   categories: `boundary_missing`, `code_boundary_mismatch`,
   `state_too_coarse`, `input_branch_missing`, `invariant_too_weak`, or
   `evidence_overclaimed`.
   Record unusual details in plain language instead of expanding the formal
   daily category list.
4. Backpropagate the root cause into the previous plan/model/test gap when a
   prior green claim existed: previous claim, observed failure, supported cause,
   `would_have_failed_if`, new plan/model/test item, and closure evidence.
5. If the issue belongs in scope, represent it as executable evidence: scenario,
   invariant, replay adapter, representative trace, or a model boundary update
   for the observed issue, plus one same-class family seed or finite boundary
   routed through ContractExhaustionMesh when practical.
6. If the miss involves a field, schema key, config flag, prompt/config field,
   payload column, or persisted attribute, run or update FieldLifecycleMesh so
   the root-cause field, ContractExhaustionMesh field cases, and any old/replaced field are
   visible.
7. Add observed-regression and contract-exhaustion case test evidence, then run Model-Test
   Alignment to verify the repaired obligation, owner code contract, and tests
   cover the same behavior. Behavior-bearing field projections should feed the
   same alignment rows.
8. If old, fallback, compatibility, alternate paths, or old fields remain
   reachable, record whether they are deleted, blocked, migrated, delegated to
   a repaired contract or replacement field, same-contract repaired, or
   explicitly out of scope with a reason.
9. Rerun the relevant model checks and confirm the old weakness plus the
   ContractExhaustionMesh case is now visible, or deliberately out of scope.
10. Validate the repair with the refined model plus the strongest practical
   production-facing evidence.
11. If the repair changed a child model under a parent ModelMesh, rerun the
   affected parent reattachment gate and keep the miss open until the parent
   consumes current child evidence.
12. If the child boundary changed, keep the miss open until ModelMesh has
   propagated the boundary review upward and reviewed affected sibling models
   or recorded why none are affected.
13. Run the model maturation loop over the miss classification, alignment rows,
   mesh rows, and freshness rows. If it reports state, branch, invariant,
   same-class, child reattachment, or obligation gaps, upgrade the model or keep
   the final claim scoped.
14. Do not use a background long-running check as closure until final artifacts
   and exit status exist; progress output is only liveness.
15. Record `Miss type`, `Root cause backpropagation`, `Generalized case`,
   field lifecycle/projection/disposition evidence when fields are involved,
   owner code contract, observed/contract-exhaustion case tests, legacy path disposition, and
   any parent reattachment decision in the adoption log, or the reason no
   generalized case was added, along with rerun commands, skipped checks, and
   residual blindspots.

A later green runtime check does not close a known model miss by itself. The
miss is closed only when it has been classified, represented in the model or
explicitly recorded as outside the modeled risk, and tied to current
model-code-test and process-freshness evidence.

## 14. Run Scenario Sandbox Review

Before connecting a model to larger production workflows, run scenario review when the task involves:

- repeated input;
- retries;
- refresh;
- queues;
- reprocessing;
- human review loops;
- uncertain AI decisions;
- repeated rejected AI packets or missing-field/no-body repair attempts;
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
For retry, rejection, or AI-packet repair loops, a progress rule must explain
why the next packet changes or why the route blocks. If the same rejected input
can be emitted again without repair feedback, progress, or a blocker, treat the
trace as a stuck-loop counterexample and route parent/child handoffs through
ModelMesh closure when a mesh is involved.

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

Use a `FlowGuardSummaryReport` when you need to present minimum-model,
known-bad proof, template harvest, model check, audit, scenario review,
progress, contract, conformance, and skipped/not-run sections together. If
the finite model check passes but a formal gate blocks or audit warns, the overall status
should not be treated as plain `pass`. If production conformance is not run,
record `not_run` or `skipped_with_reason`; skipped is not pass.

`FlowGuardSummaryReport.finding_ledger` flattens every section finding and
every non-pass section gap into a `FlowGuardFindingLedger`. Use that ledger
before FlowGuard/LiveFlowGuard framework upgrades, live failure triage, and
model-miss repair decisions. The repair choice should be explicit: fix the real
system, adjust the check flow, extend the model, or mark a boundary out of
scope. A point rule is acceptable only after the ledger shows it is the right
repair rather than the first visible patch.

`FlowGuardSummaryReport.maintenance_obligations` turns non-pass gaps into
route-owned memory. Pass relevant prior obligations to `review_maintenance_scan(...)`;
anchored open items touched by a change reopen their owner route, while
unanchored observations remain visible memory rather than hard gates.

Do not report model-level confidence as production confidence unless
conformance replay or another production-facing evidence source supports that
claim.

Recommended low-friction agent flow:

1. Create a model if none exists yet, or reuse/update the existing model.
2. Start with the smallest inspectable boundary that still exposes the customer
   risk.
3. Declare `RiskProfile` with a minimum valuable `RiskIntent`.
4. Bind `MinimumModelContract`, current `KnownBadProof`, template reuse/no-match
   review, and template harvest closure.
5. Use standard property factories or domain packs when they fit.
6. Run `run_model_first_checks()`.
7. Inspect the finding ledger before choosing a repair path for framework
   upgrades, live failures, or model misses.
8. Inspect minimized counterexamples if any.
9. Treat `pass_with_gaps`, `blocked`, skipped, stale, or `not_run` sections as
   claim boundaries.
10. Do not claim production conformance unless conformance replay or equivalent
   real-code evidence exists.
11. Record skipped checks; skipped is not pass.

## Completion Checklist

- A minimum valuable Risk Intent names failure modes, protected error classes,
  protected harms, model-critical state and side effects, completion evidence,
  adversarial inputs, known-bad cases, hard invariants, used public/local
  templates or a no-match reason, and blindspots.
- The model includes current known-bad proof evidence showing a representative
  broken path fails for the protected error class.
- If no model existed before FlowGuard applied, an AI-created model script now
  captures the relevant customer risk instead of waiting for a preexisting
  script.
- Existing models are revised or connected when new failure modes make the old
  boundary too weak.
- Projects with three or more local FlowGuard models have a model mesh, or an
  explicit reason why the current narrow task does not rely on cross-model
  evidence.
- The model mesh, when required, inventories child models, evidence tiers,
  freshness, dependencies, skipped checks, live/conformance adapters, and
  cross-model contradictions before broad continue/release/completion claims.
- Child model repairs under a parent mesh pass the parent reattachment gate, or
  the stale/missing/drifted handoff remains a visible blocker.
- Large script or module splits have a StructureMesh, or an explicit reason why
  the current narrow task does not rely on parent/child refactor evidence.
- The StructureMesh, when required, inventories function, state, config,
  side-effect, public-entrypoint, facade, model-derived target structure,
  dependency, parity, and release-scope ownership before broad refactor or
  compatibility claims.
- Direct code architecture recommendations, when requested, include a source
  FlowGuard functional model, target modules, ownership maps, validation
  boundaries, and rationale instead of only prose.
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
- Non-trivial bug repairs and post-FlowGuard runtime/test/replay/manual
  failures trigger model-miss review before completion.
- FlowGuard/LiveFlowGuard upgrades and live-failure triage use a full finding
  ledger before point-rule patches.
- Known model misses are classified, represented in executable evidence or
  marked out of scope, rerun, and then validated with production-facing checks.
  In-scope misses add one ContractExhaustionMesh same-class or finite-boundary
  case when practical.
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
