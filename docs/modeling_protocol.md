# Modeling Protocol

This document is the `core_modeling` sub-protocol for the FlowGuard Skill
Kernel. The main Skill routes here for ordinary model-first work. Specialized
routes such as UI flow structure, code structure recommendation, model-test
alignment, ModelMesh, TestMesh, StructureMesh, DevelopmentProcessFlow,
model-miss review, conformance/adoption, long-check observability, and
framework upgrades live in their dedicated reference protocols.

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
- `model_test_alignment`: model obligations and ordinary tests both exist, and
  the risk is whether scenarios, invariants, hazards, transitions, contracts,
  or optional code external contracts have matching current test evidence. When
  real Python source/tests are in scope, first run or request conservative
  source audit evidence for the code and test rows.
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
  overlays, navigation ownership, and state/control/event ownership.
- `development_process_flow`: non-trivial staged development or modification
  with validation, development lifecycle ordering, artifact overwrite,
  validation evidence freshness, peer writes, V-style validation pairs, or
  minimum revalidation is the risky boundary. Use this sibling route to review
  lifecycle rows without supervising ModelMesh, TestMesh, StructureMesh, or
  Model-Test Alignment internals.

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

## 0.3 Check The Model-Test Alignment Trigger

Before trusting a claim that model coverage and test coverage agree, ask
whether the model obligations need a direct test-evidence alignment review.
Trigger Model-Test Alignment when a FlowGuard model has explicit scenarios,
invariants, hazards, state transitions, or input/output contracts and ordinary
tests are expected to prove those obligations. If the reviewed behavior also
depends on a public function, API, CLI, facade, adapter, persisted output, or
other externally visible code surface, include optional code external contract
rows in the same direct review.

Model-Test Alignment is not a mesh route. It does not split tests, split code,
split models, or read TestMesh, StructureMesh, or ModelMesh reports. It
compares `ModelObligation` rows, optional `CodeContract` rows, and
`TestEvidence` rows and reports missing evidence, missing or mismatched code
contracts, orphan tests, orphan code contracts, duplicate same-kind test
claims, duplicate code contract owners, internal-path-only tests,
model-code-test binding mismatches, stale/non-passing evidence, missing
required test kinds, and overclaimed model confidence.

When real Python code and tests are available, add conservative source audit
evidence before trusting the rows. The audit should parse AST-visible source
and test structure, generate or check code-contract evidence and
test-assertion evidence, and feed those rows into the same alignment review.
It is deliberately limited: it is not a perfect semantic proof for Python, does
not replace conformance replay, and must send dynamic, ambiguous, or complex
behavior to manual review.

Use `review_model_test_alignment(...)` for this direct comparison.

Use TestMesh only when the validation flow itself is large, slow, layered, or
needs parent/child suite ownership. Use StructureMesh only when a large script,
module, command, or API surface is being split. Use ModelMesh only when the
risk is parent/child model evidence or model partitioning.

Read
`.agents/skills/model-first-function-flow/references/model_test_alignment_protocol.md`
for the checklist and prompt template.

## 0.35 Check The Local Model Mesh Trigger

Before trusting prior green results, scan for existing local FlowGuard models,
runners, persisted result files, adoption logs, and replay/conformance
artifacts. If the project has three or more local FlowGuard models, or the
current decision spans multiple existing model boundaries, create or update a
local model mesh before making broad continue, release, completion, or
production-confidence claims. Also trigger mesh review when a single new or
legacy model is too large to inspect comfortably, such as an estimated or
observed state count above the configured threshold, a budgeted model group that
remains incomplete, or one model mixing several unrelated functional areas.

The mesh is a model-of-models. It should inventory child models and classify
their evidence tiers, freshness rules, dependencies, contracts, skipped checks,
and blindspots. Do not inline every child model's full state graph unless a
specific contradiction requires a narrow adapter.

For hierarchical modeling, treat the parent model as a total map and child
models as region maps. The mesh should check the partition map for complete
coverage, excessive sibling overlap, duplicate state-write ownership, duplicate
side-effect ownership, stale evidence, and split-review decisions for oversized
models. A child can become a parent and have its own local partition map and
mesh review when that child grows large enough to split again.

When the parent claims whole-flow confidence, also model the model-to-model
handoffs themselves. A `MeshClosureModel` records root entries, child outputs,
parent or sibling consumers, required joins, terminal dispositions, and
out-of-scope branches as finite FlowGuard-style obligations. Parent mesh green
confidence for whole-flow claims requires that closure model to pass; otherwise
the mesh is only evidence for partition, target split, reattachment, and
freshness.

Before a ModelMesh parent can trust the child-model layout, record a target
split derivation from the FlowGuard source model or model-of-models. The
derivation must name the source model, target child model ids, covered partition
items, state owner fields, side-effect owner fields, and rationale for the
split. A partition map alone is not enough parent confidence.

When a post-runtime miss is repaired in a local child model, route through
Model-Miss Review and the affected ModelMesh. The child-local pass is not
complete until the parent reattachment gate consumes the current child evidence
id and confirms the input, output, state, side-effect, and outgoing-contract
handoff still matches the parent flow.

Keep the current bug instance separate from the bug class. Model-Miss Review
owns classification and same-class representation or out-of-scope recording;
ModelMesh owns child-boundary propagation upward and affected sibling review
when the repair changes inputs, outputs, state ownership, side-effect
ownership, risk boundary, or outgoing guarantees. Background long-running
checks may support either route only after final artifacts and exit status
exist; progress is liveness, not pass evidence.

Read `docs/model_mesh_protocol.md` for the inventory fields, evidence tiers,
required hazards, prompt template, and completion standard. At minimum, the
mesh must catch abstract-only permission, hidden skipped live/replay checks,
stale result reuse, unregistered model evidence, cross-model contradictions,
hidden blockers, missing conformance, unrepresented model misses, sealed/private
body reads, stale installed skill/source copies, oversized mesh expansion, and
absence of a mesh when the model count or large-model threshold is met. For
child repairs, it must also catch child-local green evidence that was not
reattached to the parent.

## 0.4 Check The TestMesh Trigger

Before trusting a broad validation claim, ask whether tests need their own
parent/child hierarchy mesh. Trigger TestMesh when a large test script, suite,
or validation flow should split into child suites/scripts, when a suite is too
slow for routine work, mixes unrelated behavior or release gates, runs in the
background, hides skips or timeouts, or depends on stale result reuse.

The TestMesh is the test-side sibling of ModelMesh and StructureMesh: the
parent test gate is the total validation contract, while child suites or child test scripts own regions of that contract. The parent layer consumes child
ownership and evidence contracts instead of expanding every child test case,
fixture, or internal state route. A child suite can become its own parent gate
when it grows large enough to split again.

TestMesh does not run pytest, unittest, Playwright, shell commands, or manual
checks. Project adapters run the suites and pass `TestSuiteEvidence` into
FlowGuard. The parent gate lists `TestPartitionItem` entries for behavior,
state, module, command, side effect, invariant, or release boundaries.
`review_test_mesh(...)` checks coverage, ownership conflicts, freshness,
skipped visibility, timeout/failure status, background completion artifacts,
and routine-vs-release confidence.

Before TestMesh parent confidence, record a target split derivation from a
FlowGuard validation-structure model. The derivation must name the source
model, target child suites/scripts, covered partition items, state owner fields,
side-effect owner fields, and rationale for the split. A flat child-suite list
without derivation is not enough.

Read `docs/test_evidence_mesh.md` for the API sketch and
`.agents/skills/model-first-function-flow/references/test_mesh_protocol.md` for
the agent checklist.

## 0.45 Check The StructureMesh Trigger

Before trusting a large script or module split, ask whether the structure needs
its own parent/child ownership mesh. Trigger StructureMesh when functions,
state, config, side effects, public entrypoints, behavior contracts, or release
obligations are being split across child modules.

The StructureMesh is a structure-refactor evidence model for existing large
scripts or modules. It does not move code or parse source files. Before
ownership review, it requires a FlowGuard model-derived target child structure:
FunctionBlock-to-module, state-owner, side-effect-owner, facade, and validation
maps. Project adapters collect source inventory, model-derived target
structure, dependency edges, facade status, public entrypoint compatibility,
config/default changes, and parity evidence, then pass
`CodeStructureRecommendation`, `ModuleStructureEvidence`,
`PublicEntrypointEvidence`, and `StructurePartitionItem` objects into
`review_structure_mesh(...)`.

Read `docs/structure_mesh.md` for the API sketch and
`.agents/skills/model-first-function-flow/references/structure_mesh_protocol.md`
for the agent checklist.

## 0.47 Check The Code Structure Recommendation Route

Use the parallel code structure recommendation route when a user directly asks
for a code architecture recommendation, or when a functional model exists and
the next implementation step needs a module/function split plan. This route can
create or use a functional or hierarchical model, but it does not write
production code and it is not mandatory for every ordinary model-first task.

Read `docs/code_structure_recommendation.md` and
`.agents/skills/model-first-function-flow/references/code_structure_recommendation_protocol.md`
for the recommendation shape.

## 0.48 Check The UI Flow Structure Route

Use the parallel UI flow structure route when a UI's buttons, menus, controls,
screens, panels, overlays, navigation, information displays, state
availability, duplicate/overlapping controls, headings, labels, action text,
status/helper messages, error/recovery copy slots, complete app
launch-to-terminal journey coverage, or implemented/runnable UI click-through
evidence alignment need a model-first interaction flow before
visual design or frontend implementation. This route models the UI as
`UI event x UI state -> Set(UI output x UI state)`, reviews that interaction
model, reviews journey coverage and reachable visible-control/event ownership
when a complete app-level UI claim is made, validates feature/UI/click-through
evidence when an implemented UI claim is made, derives parent/child UI topology,
first-level persistent menus, second-level contextual regions, third-level
local controls, information-display ownership, stable layout positions, overlay
hierarchy, and explicit rationale for intentional redundancy, then derives the
UI text hierarchy blueprint from the reviewed structure.

Read `docs/ui_flow_structure.md` and
`.agents/skills/flowguard-ui-flow-structure/references/ui_flow_structure_protocol.md`
for the route shape.

## 0.49 Check The DevelopmentProcessFlow Route

Use the parallel development process route for non-trivial staged development
or modification work that has validation, such as plan, edit, test, fix, and
verify. Also use it when the question is whether a done, release, archive, or
publish claim still has current evidence after lifecycle steps changed
requirements, designs, models, code, tests, docs, adapters, or release
artifacts. This route models the development lifecycle itself as a stateful
process. It may reference sibling route evidence ids and covered artifact
versions, but it does not inspect or replace sibling routes.

Read `docs/development_process_flow.md` and
`.agents/skills/model-first-function-flow/references/development_process_flow_protocol.md`
for the lifecycle evidence shape.

## 0.5 Write A Risk Intent Brief

Before defining state or function blocks, write the short brief that tells the
model what accidents it is meant to expose. This is the agent's own preflight;
ask the user only when materially different risk priorities exist and the
protected harm cannot be inferred safely.

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

## 9. Run Explorer With Repeated Inputs

Choose:

- `external_inputs`
- `initial_states`
- `max_sequence_length`
- optional required labels or reachable predicates

Always include repeated-input exploration when duplicate side effects are possible. For one input and length two, the explorer must check both `[x]` and `[x, x]`.

Direct `Explorer(...)` runs emit bounded ten-step progress on `stderr` by
default, counted by top-level `initial_state x input_sequence` work units. This
helps agents distinguish a long serial run from a silent process, but it is not
pass/fail evidence and it does not change `CheckReport` semantics. Use
`progress_steps=0` or `FLOWGUARD_PROGRESS=0` when a strict environment requires
no progress output.

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

## 13.5 Handle Post-Runtime Model Misses

Treat a runtime, test, replay, log, or manual-validation failure that appears
after a FlowGuard pass as a model-miss review trigger until proven otherwise.
The earlier pass is still useful, but it is provisional evidence, not a reason
to patch and finish directly.

When this happens:

1. Reopen the model-first work and keep completion blocked while the model-miss
   obligation is open.
2. Build or inspect the finding ledger across invariant/model checks,
   model-quality audit, scenario or live-audit evidence, progress, contracts,
   conformance, skipped/not-run sections, and adoption evidence. The ledger is
   the coverage-first view used to avoid patching only the visible failure.
3. Classify why the prior model missed the issue with one of five practical
   categories: `boundary_missing`, `state_too_coarse`,
   `input_branch_missing`, `invariant_too_weak`, or `evidence_overclaimed`.
   Record unusual details in plain language instead of expanding the formal
   daily category list.
4. If the issue belongs in scope, represent it as executable evidence: scenario,
   invariant, replay adapter, representative trace, or a model boundary update
   for the observed issue, plus one same-class generalized bad case when
   practical.
5. Rerun the relevant model checks and confirm the old weakness plus the
   same-class case are now visible, or deliberately out of scope.
6. Validate the repair with the refined model plus the strongest practical
   production-facing evidence.
7. If the repair changed a child model under a parent ModelMesh, rerun the
   affected parent reattachment gate and keep the miss open until the parent
   consumes current child evidence.
8. If the child boundary changed, keep the miss open until ModelMesh has
   propagated the boundary review upward and reviewed affected sibling models
   or recorded why none are affected.
9. Do not use a background long-running check as closure until final artifacts
   and exit status exist; progress output is only liveness.
10. Record `Miss type`, `Generalized case`, and any parent reattachment decision
   in the adoption log, or the reason no generalized case was added, along with
   rerun commands, skipped checks, and residual blindspots.

A later green runtime check does not close a known model miss by itself. The
miss is closed only when it has been classified and represented in the model or
explicitly recorded as outside the modeled risk.

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

`FlowGuardSummaryReport.finding_ledger` flattens every section finding and
every non-pass section gap into a `FlowGuardFindingLedger`. Use that ledger
before FlowGuard/LiveFlowGuard framework upgrades, live failure triage, and
model-miss repair decisions. The repair choice should be explicit: fix the real
system, adjust the check flow, extend the model, or mark a boundary out of
scope. A point rule is acceptable only after the ledger shows it is the right
repair rather than the first visible patch.

Do not report model-level confidence as production confidence unless
conformance replay or another production-facing evidence source supports that
claim.

Recommended low-friction agent flow:

1. Create a model if none exists yet, or reuse/update the existing model.
2. Start with the smallest inspectable boundary that still exposes the customer
   risk.
3. Declare a lightweight `RiskProfile`.
4. Use standard property factories or domain packs when they fit.
5. Run `run_model_first_checks()` when available.
6. Inspect the finding ledger before choosing a repair path for framework
   upgrades, live failures, or model misses.
7. Inspect minimized counterexamples if any.
8. Treat `pass_with_gaps` as useful but limited confidence.
9. Do not claim production conformance unless conformance replay or equivalent
   real-code evidence exists.
10. Record skipped checks; skipped is not pass.

## Completion Checklist

- A Risk Intent Brief names failure modes, protected harms, model-critical
  state and side effects, adversarial inputs, hard invariants, and blindspots.
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
- Whole-flow parent confidence uses a mesh closure model to prove root entries,
  child outputs, joins, terminals, and out-of-scope branches close without
  expanding child internals.
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
- Post-FlowGuard runtime/test/replay/manual-validation failures trigger
  model-miss review before completion.
- FlowGuard/LiveFlowGuard upgrades and live-failure triage use a full finding
  ledger before point-rule patches.
- Known model misses are classified, represented in executable evidence or
  marked out of scope, rerun, and then validated with production-facing checks.
  In-scope misses add one same-class generalized bad case when practical.
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
