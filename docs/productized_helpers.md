# Productized Helper Layer

FlowGuard's core remains small, while the public model-first entry is formal:

```text
FunctionBlock: Input x State -> Set(Output x State)

RiskIntent + MinimumModelContract + KnownBadProof
-> FlowGuardCheckPlan -> run_model_first_checks
```

The helper layer exists to make that path repeatable for AI coding agents. It
should not become a second formal system, but the model-first entry must still
name the protected error class, model completion evidence, prove a known-bad
case is caught, and close template reuse/harvest.

ContractExhaustionMesh is the canonical helper for expanding declared finite
boundaries into bad cases. It does not discover the whole world by magic. A
route must first declare the field, state/input boundary, same-class family,
payload contract, transition matrix, or parent/child closure token. Then
`review_contract_exhaustion()` creates stable bad-case ids, expected oracle
reactions, and downstream MTA/TestMesh/ModelMesh/Risk Ledger handoffs. This
replaces older patterns where each prompt hand-wrote "similar bug" examples
as if they were canonical coverage.

For broad/full claims, the route must also declare a `ContractCoverageUniverse`.
This is the generic list of what the matrix claims to cover: dimensions, axes,
interaction groups, payload contracts, code boundaries, generated case ids, and
coverage receipts. Missing items must either be projected into
ContractExhaustionMesh or explicitly scoped out with an owner route and reason.
When a bad-submitter rehearsal is needed, use generic `ContractFaultProfile`
rows derived from cases; FlowGuard does not need a product-specific fake actor.
When a real miss appears, feed it back through `ObservedProblemBackfeed` so the
matrix either proves same-class coverage or records a coverage gap.

For model-local Cartesian coverage, the declared boundary is `model_id` plus
finite axes and interaction groups. The report produces combination cases,
optional shard ids, and a model coverage receipt. That receipt proves only that
the local model boundary was exhausted; parent confidence still needs ModelMesh
to consume child receipt ids, TestMesh to close shard evidence, Model-Test
Alignment to bind generated obligations to tests, and Risk Evidence Ledger to
consume the final gates.

Matrix readiness is not whole-chain readiness. A generated case can be valid
and still require a separate composite handoff acceptance item before broad
done/release confidence. Those acceptance ids state which route owners must
consume the same case id together, so a single-point matrix pass cannot be
mistaken for full model-chain closure.

For the full public API layer map, see `docs/api_surface.md`. The exported
`API_SURFACE` grouping is descriptive only; it does not turn helpers, reports,
or internal evidence tools into required steps.

## Standard Property Factories

Use these when they match a common bug class:

- `no_duplicate_by(...)`: selected items are unique by key.
- `at_most_once_by(...)`: attempts, events, or side effects happen at most once per key.
- `all_items_have_source(...)`: downstream items trace to upstream source items.
- `no_contradictory_values(...)`: one key cannot accumulate mutually exclusive values.
- `cache_matches_source(...)`: cache entries agree with source-of-truth values.
- `only_named_block_writes(...)`: one state field is written only by its owner block.
- `require_label_order(...)`: one trace label appears before another.
- `forbid_label_after(...)`: a later forbidden label does not appear after an anchor label.

Each factory returns an ordinary `Invariant`. Failure messages include the
specific duplicate keys, missing source keys, contradictory values, mismatches,
unauthorized writes, or label positions, plus structured metadata for reports.
Factories also attach lightweight `property_classes` metadata, such as
`deduplication`, `at_most_once`, or `cache_consistency`. `audit_model(...)`
uses these tags before falling back to name/description heuristics, so custom
names do not have to include words like "duplicate" or "cache" to be recognized.

Custom invariants may add the same optional metadata directly:

```python
Invariant(
    "job_records_are_valid",
    "records have the expected domain shape",
    check_records,
    metadata={"property_classes": ("deduplication",)},
)
```

The metadata is helper information only. It is optional, unknown values are not
hard failures, and older `Invariant(name, description, predicate)` usage remains
valid.

## Counterexample Minimization

Use `minimize_failing_sequence(...)` after a violation when the failing input
sequence is longer than needed. The algorithm is deterministic and only tries
to delete inputs or contiguous chunks. It does not use random shrinking,
Hypothesis, SMT, LTL, probability, or an LLM API.

The returned `MinimizedCounterexample` keeps both:

- `original_sequence`
- `minimized_sequence`

If no shorter sequence preserves the failure, the status is
`no_reduction_found`.

## Model Quality Audit

Use `audit_model(...)` to expose obvious coverage gaps:

- missing repeated-input exploration for retry/dedup/idempotency risks;
- missing invariants;
- missing scenarios;
- missing cache consistency checks for cache risks;
- missing duplicate/idempotency checks for side-effect risks;
- missing progress checks for retry/queue/loop/waiting risks;
- conformance replay not run;
- skipped checks.

Severity rules:

- `error`: the model structure is unusable, such as a workflow with no blocks.
- `warning`: the model can run, but coverage or confidence has a gap.
- `suggestion`: useful improvement, but not a current check failure.

Warnings are not automatic failures. They define the boundary of what the model
has and has not checked. Skipped is not pass.

`audit_model(...)` can also consume a `RiskProfile`. RiskProfile risk classes
make the audit more targeted, for example warning about missing repeated-input
coverage for retry/deduplication risks or missing conformance evidence for a
`production_conformance` confidence goal. Unknown risk classes are recorded as
warnings rather than rejected.

## Adoption Evidence Audit

Use `audit_flowguard_adoption(root)` for read-only checks of existing
FlowGuard adoption evidence. It scans `.flowguard` Python files for stale
fallback markers such as `flowguard_package_available = False`, fallback
finite-runner comments, local replacement `Workflow` or finite-runner classes,
and current direct finite-runner calls that do not also bind the formal
CheckPlan and known-bad proof gate.

If the real package is importable but a current model still appears to use a
fallback, the report emits `stale_fallback_model` as a warning. If a current
model runs the finite engine without the formal gate, it emits a formal-entry
required finding. Historical fallback mentions in old
logs are kept visible as suggestions. These findings do not make the model fail
by themselves; they prevent overclaiming current FlowGuard adoption from stale
evidence.

For low-friction logging, the CLI can append start and finish entries:

```powershell
python -m flowguard adoption-start --task-id <id> --task-summary "<summary>" --trigger-reason "<reason>"
python -m flowguard adoption-finish --task-id <id> --task-summary "<summary>" --trigger-reason "<reason>" --command "<check command>"
```

The start command records `in_progress`; the finish command appends the final
entry. This is a reporting helper only. It does not replace model checks,
scenario review, conformance replay, or test execution.

## DevelopmentProcessFlow Front Door

Start with DevelopmentProcessFlow when a non-trivial request starts as plan
discussion, involves several skills/tools/plugins, or will continue through
staged edit/test/install/sync/release work. Internally it may call
`DevelopmentProcessSimulationRequest` and
`review_development_process_simulator(...)`, but the public owner route stays
`development_process_flow`. The internal helper returns ordered mode decisions:

- `plan_detailing`: rough plans need explicit rows before implementation.
- `agent_workflow`: skills, tools, side effects, gates, and skipped candidates
  need rehearsal before execution.
- `execution_freshness`: artifact versions, peer writes, validation evidence,
  install/shadow/git sync, and final claims need freshness review.

The helper does not replace the delegated mode owners. It points rough plans
to Plan Detailing, multi-skill workflows to AgentWorkflowRehearsal, and
execution-freshness claims back to DevelopmentProcessFlow.

## Plan Detailing Compiler

Use `PlanDetail` and `review_plan_detail(...)` when the user explicitly asks
for PlanDetailing or the development-process simulator delegates the
`plan_detailing` mode. The compiler does not generate the work by itself; it
reviews structured rows for goal, source evidence, risk surfaces, artifacts,
state, side effects, ordered steps, receipts, validation, failure branches,
rework gates, human questions, and final evidence claim scope.

Projection helpers connect the detailed plan to existing routes:

- `plan_detail_to_plan_intake(...)`
- `plan_detail_to_step_contracts(...)`
- `plan_detail_to_development_process(...)`
- `plan_detail_to_agent_workflow_plan(...)`

A plan-detail pass means the plan is detailed enough for downstream checks. It
does not prove the implementation, tests, replay, release, or done claim.

## Model Impact Freshness

Use `review_model_impact_freshness(...)` during FlowGuard framework upgrades or
installed-helper syncs that must account for existing `.flowguard` models. The
helper reviews:

- `ModelFreshnessRecord`: the model inventory row;
- `UpgradeImpact`: changed artifacts and FlowGuard semantic ids;
- `ModelImpactAssessment`: affected, not-impacted, deprecated, blocked, or
  unknown classification;
- `ModelReuseTicket`: evidence that a not-impacted model can reuse a previous
  result;
- `ModelRerunEvidence`: current rerun and update-review proof for affected
  models.

The helper is intentionally selective. It blocks blind reuse of old evidence,
but it also avoids forced reruns when a model has a valid reuse ticket and
same-output or fingerprint proof.

Use `TestResultReuseTicket` separately for old test results. A previous test
result can support Model-Test Alignment or TestMesh only when the ticket and
matching `ProofArtifactRef` prove unchanged command, test source, tested
artifact, dependencies, environment, result fingerprint, and covered scope.

## ExistingModelPreflight Angle Evidence

ExistingModelPreflight owns route-boundary doubt in an existing modeled
system. It may consume `review_model_angle_deliberations(...)` when an agent
needs to preserve candidate viewpoints before deciding whether to reuse,
extend, split, or scope a model. This is the answer to a common AI failure
mode: the agent follows the provided route list but does not ask whether the
current situation needs a different model viewpoint.

Each `ModelAngleDeliberation` row is intentionally free-form:

- `angle_name`: the possible viewpoint in plain language;
- `current_model_sees`: what the current model already covers;
- `current_model_misses`: what might still be invisible;
- `failure_if_ignored`: what can go wrong if that angle is skipped;
- `candidate_action`: reuse, extend, add child model, create new model, scope
  out, defer, or ask for human review;
- `owner_route_hint`: the route that should produce real evidence.

Known FlowGuard routes are hints, not the full imagination space. The angle can
be about fields, lifecycle, installation sync, release evidence, user policy,
runtime topology, AI workflow ordering, or another domain-specific surface.
The review only preserves the decision; ExistingModelPreflight or the owning
route still supplies the actual model, test, replay, or closure evidence.

The template remains an internal evidence scaffold:

```powershell
python -m flowguard model-angle-template --output .
python .flowguard/model_angle_deliberation/run_checks.py
```

## FlowGuard Self-Maintenance Mesh

Use `default_flowguard_self_maintenance_plan(...)` when FlowGuard itself feels
too heavy for AI agents to use directly. It fills the common route profiles,
API route groups, AI entry profiles, and field layer defaults before
`review_flowguard_self_maintenance(...)` runs. Specialist routes can still use
`default_flowguard_route_profiles()`, `default_ai_maintenance_profiles()`, and
`default_field_layer_profiles()` directly when they need to override fields.
The default plan keeps the first-read path thin:

- route profiles connect installed capabilities to trigger, minimal input,
  output, evidence owner, API group, template, skill, and next action;
- AI maintenance profiles start common work from fields, route graph,
  structure, or validation instead of from `__all__`;
- field layer profiles keep core fields visible, route-owned fields lazy,
  shared proof fields compact, display/metadata fields scoped, and
  compatibility-like fields disposition-bound;
- child reports preserve the closure contract shape for route graph, field,
  structure, validation, install/shadow sync, and final claim evidence.

This mesh is a parent check, not a new supervisor route. It can say a route is
missing, stale, skipped, or blocked, but the owner route still supplies the real
model/test/replay/structure/ledger evidence.

## AI Route Handoff Reports

`FlowGuardSummaryReport` includes a finding ledger and maintenance obligations.
Each non-pass ledger entry carries the existing owner route, action kind,
required input kinds, proof gap codes, suggested command text, and claim
effect. This lets AI agents continue through the existing route system instead
of guessing from prose.

Use `maintenance_scan_plan_from_summary_report(...)` to turn those report gaps
into a `MaintenanceScanPlan`. DevelopmentProcessFlow owns the post-change scan
decision: it consumes the scan output and points each unresolved item to
existing specialists such as DevelopmentProcessFlow, Model-Test Alignment,
Model Maturation, TestMesh, StructureMesh, or AgentWorkflowRehearsal, but the
scan helper itself does not run those routes or validate their evidence.

`DevelopmentProcessFlow` revalidation recommendations include the prior
producer route, proof-artifact requirement, freshness gap codes, and claim
scopes blocked until rerun. `existing_model_preflight_from_project(...)`
collects a lightweight project inventory into the existing preflight shape;
`review_existing_model_preflight(...)` remains the validator.

## Model Maturation Loop

Use `review_model_maturation_loop(...)` after code, tests, model-miss review,
Model-Test Alignment, ModelMesh, code-boundary review, or evidence-freshness
review produces a signal that the current model is too coarse, stale, or
disconnected. The helper reviews:

- `ModelMaturationSignal`: the route signal and the model/risk/evidence ids it
  came from;
- `ModelMaturationPlan`: the claim scope and whether a broad closure claim is
  being made;
- `ModelMaturationReport`: the decision, confidence, required model-upgrade
  actions, scoped signal ids, and maintenance obligations for later scans.

The helper keeps broad claims honest. It does not replace the owning route; it
decides whether that route's evidence requires a model update, parent
reattachment, child split, evidence refresh, or scoped claim.

## Scenario Matrix Builder

`ScenarioMatrixBuilder` scaffolds a small deterministic scenario set:

- single input: `[A]`, `[B]`
- repeated same input: `[A, A]`, `[B, B]`
- pairwise order: `[A, B]`, `[B, A]`
- ABA: `[A, B, A]`, `[B, A, B]`
- challenge routes: partial-failure retry, duplicate delivery, stale-state
  after change, delayed replay, and terminal replay shapes

Generated scenarios default to `needs_human_review`. They cover useful input
shapes, such as repeats and order swaps, but they are not business oracles. Add
explicit domain expectations before treating them as pass/fail evidence.

Use `.challenge_patterns()` when the goal is proactive bug discovery from an
existing FlowGuard model. The generated routes are still ordinary Scenario
Sandbox scenarios, carry `challenge` tags plus risk notes, and remain candidate
evidence until a domain expectation, replay, or test gives them an oracle. The
retry, deduplication, cache, and side-effect packs reuse this builder path so
pack-generated challenge routes stay inside the existing replay, alignment, and
ledger evidence chain.

For model-derived discovery, use
`synthesize_challenge_scenarios_from_report(...)` after a model-check report or let
`run_model_first_checks(...)` add the `model_derived_challenges` section when
auto-generated scenarios are enabled for retry, deduplication, cache, or
side-effect risks. Those scenarios are selected from actual FlowGuard evidence:
counterexample traces, dead or exception branches, repeated labels or blocks,
state revisits, interleaved replay, and risk-signaling trace text. This is
different from a generic `[A, B, A]` matrix row because the model report
explains why that route is worth testing.

## State Closure As ContractExhaustion Input

`StateClosurePlan`, `StateClosureDimension`, `StateClosureCase`, and
`review_state_closure(...)` make "all other values" explicit without changing
the finite model runner into an infinite-state engine. Use `closed_enumeration` only
when the listed values really are complete. Use `open_boundary` when other,
malformed, missing, old-schema, invalid-terminal, or externally unknown cases
may occur.

`run_model_first_checks(...)` runs this gate automatically. ContractExhaustionMesh
can also project StateClosure rows into canonical bad cases with
`state_closure_cases_to_contract_cases(...)`. If no explicit closure plan is
supplied, FlowGuard infers visible dimensions from external inputs and
dataclass fields such as `status`, `phase`, `kind`, `type`, `mode`, and
`schema_version`. Inferred unknown policies keep confidence scoped. Explicit
open boundaries pass only when unknown cases are rejected, blocked, isolated,
or routed to model maturation before side effects.

## Model Topology Hazard Review

`UsageIntent`, `TopologyDigest`, `TopologyHazardCandidate`,
`TopologyHazardReviewPlan`, and `review_topology_hazards(...)` make the
"experienced engineer" review automatic without turning it into a generic AI
checklist. The helper first reads model topology and usage intent, then
promotes only hazards tied to a concrete state, edge, side effect, terminal
state, old/new compatibility path, external boundary, shared writer, or
parent/child compression landmark.

`run_model_first_checks(...)` appends a `topology_hazard` section by default.
Unanchored AI concerns are observations only. Anchored unresolved hazards stay
visible as scoped or blocked confidence and name the owner route: Model
Maturation, Model-Test Alignment, DevelopmentProcessFlow, Architecture
Reduction, or Risk Evidence Ledger.

Use the template with:

```powershell
python -m flowguard topology-hazard-template --output .
python .flowguard/model_topology_hazard_review/run_checks.py
```

## Unified Summary Report

`FlowGuardSummaryReport` combines optional sections such as model check, audit,
state closure, topology hazard review, scenario review, progress, contract, conformance, and
not-run/skipped checks.

Status rules:

- Any invariant violation, dead branch, exception, contract failure, progress
  failure, scenario mismatch, or conformance failure should make the relevant
  section `failed`.
- If the finite model check passes but audit has warnings, overall status is
  `pass_with_gaps`.
- A `not_run` or `skipped_with_reason` conformance section is a confidence gap,
  not a hard failure and not a pass.

Use the summary in PR notes or agent replies to avoid overstating "FlowGuard
passed" when only the model checker ran.
`FlowGuardSummaryReport.maintenance_obligations` also turns non-pass gaps into
route-owned memory that future maintenance scans and risk ledgers can inherit.

## Mermaid Source Export

Mermaid export is an explicit reporting helper for situations where a diagram
will make a trace, counterexample, or reachable state graph easier to inspect.
It returns text source that can be copied into Markdown, GitHub, docs tooling,
or another renderer. It does not produce PNG-only output and does not change
default `format_text()` reports.

Available helpers:

- `trace_to_mermaid_text(trace)`: one representative model trace.
- `graph_to_mermaid_text(edges, states=..., initial_states=...)`: a generic
  state graph from `GraphEdge`-like objects.
- `loop_report_to_mermaid_text(report)`: the reachable graph from a
  `LoopCheckReport`.
- `mermaid_code_block(source)`: wrap source in a Markdown Mermaid fence.

Use this when the user asks for a diagram, when a counterexample needs visual
explanation, or when a loop/stuck-state review is easier to discuss as a graph.
For routine checks, prefer the normal text or JSON reports.

Run `python examples/mermaid_export_example.py` for a minimal end-to-end
example that prints a Markdown Mermaid code block.

## Runner and Domain Packs

`RiskProfile`, `FlowGuardCheckPlan`, and `run_model_first_checks(...)` provide
the low-friction formal path for AI agents:

1. Create a model if none exists yet, or update the existing model.
2. Start with the smallest inspectable boundary that still exposes the
   customer-relevant risk; do not reduce the model below the state and branches
   needed to simulate that risk.
3. Declare the intended risk boundary in `RiskProfile`, preferably with a
   `RiskIntent` that names failure modes, protected harms, model-critical
   state, adversarial inputs, hard invariants, and blindspots.
4. Bind a `MinimumModelContract`, template reuse/no-match review, at least one
   current `KnownBadProof`, and template harvest closure.
5. Use property factories or domain packs when they fit.
6. Run `run_model_first_checks(...)`.
7. Inspect minimized counterexamples when present.
8. Treat `pass_with_gaps`, `blocked`, `not_run`, and skipped sections as claim
   boundaries, not as pass evidence.

The runner is orchestration, not a new core checker. It calls existing helpers
and delegates finite exploration to the internal finite runner.

Because the runner delegates model exploration to the internal finite runner,
it inherits the default bounded `stderr` progress output. Do not add a second
runner-specific progress loop; silence progress with `FLOWGUARD_PROGRESS=0` or
the plan progress fields when needed.

Domain packs are small recipes:

- `DeduplicationPack`
- `CachePack`
- `RetryPack`
- `SideEffectPack`

They produce optional invariants and scenario scaffolds from selectors and key
functions supplied by the user or agent. They do not infer production code, add
hidden requirements, or replace explicit domain modeling.

## Starter Templates

FlowGuard includes small public templates that are safe to copy into another
project:

```powershell
python -m flowguard project-template --output .
python -m flowguard project-adoption-template --output .
python -m flowguard risk-intent-template --output .
python -m flowguard risk-template-library-template --output .
python -m flowguard plan-detailing-template --output .
python -m flowguard model-miss-template --output .
python -m flowguard model-test-alignment-template --output .
python -m flowguard development-process-flow-template --output .
python -m flowguard maintenance-scan-template --output .
python -m flowguard model-angle-template --output .
```

The project adoption template writes the target-project AGENTS block,
`.flowguard/project.toml`, and starter adoption notes with the FlowGuard GitHub
URL and version policy. The basic project template demonstrates validation,
rejection, duplicate input, source-trace invariants, completion evidence, and a
known-bad variant that must fail. The Risk Intent template shows how to bind a
`RiskIntent`, `RiskProfile`, template reuse review, minimum model contract,
current `KnownBadProof`, template harvest closure, and `FlowGuardCheckPlan`
before running `run_model_first_checks(...)`. The risk
template library template shows how to search packaged public templates,
reference the per-machine local template library, prepare a local candidate,
and close harvest as written, merged, duplicate-linked, or not-harvestable
without hard-coding a developer path. The plan-detailing template shows how to turn a
rough plan into explicit PlanDetail rows and broken variants before projecting
to PlanIntake, WorkflowStepContracts, and DevelopmentProcessFlow. The
model-miss template models the feedback loop
used when runtime, tests, replay, or manual validation finds a problem after a
FlowGuard pass. The model-test alignment template compares explicit
`ModelObligation` rows with plain `TestEvidence` rows so a project can see
whether model scenarios, invariants, hazards, transitions, or contracts have
matching current tests. The development process flow template models
non-trivial staged development or modification with validation, lifecycle
ordering, artifact overwrite, validation freshness, V-style validation pairs,
and minimum revalidation before safe continuation, done, or release claims.
The maintenance scan template shows how to summarize changed artifacts,
remembered maintenance obligations, skipped candidate routes, stale evidence,
and structure/reduction signals into required or suggested owner-route actions
before a broad FlowGuard claim. The model-angle template shows how to record
open-ended missing-viewpoint reasoning before trusting a single model boundary
or route decision.

These are scaffolds, not reusable business logic. Rename every state field,
input, output, invariant, and blindspot to match the target project before
claiming confidence.

The development process flow helper is the simulator front door and
execution-freshness owner. It can reference evidence produced by ModelMesh,
TestMesh, StructureMesh, Model-Test Alignment, LongCheck, or Conformance
Adoption through evidence ids and artifact-version metadata, but it does not
inspect or supervise those route owners.

## Maintenance Scan Router

Use the maintenance scan router after non-trivial FlowGuard-managed project
work when the question is "what maintenance route did this change make
necessary?":

```powershell
python -m flowguard maintenance-scan-template --output .
```

The scaffold writes:

- `.flowguard/maintenance_scan/run_scan.py`
- `docs/flowguard_maintenance_scan.md`

The helper is intentionally thin. It turns model/code/test drift, remembered
open obligations, state-closure gaps, model-angle gaps, stale evidence, skipped candidate routes,
reducible branches, large modules, mesh pressure, and slow or broad validation
into owner-route actions such as
Model-Test Alignment, DevelopmentProcessFlow, Architecture Reduction,
StructureMesh, ModelMesh, TestMesh, Model Maturation, or
AgentWorkflowRehearsal. It does not run those routes and a clear scan is not
validation evidence by itself.

## Maintenance Workflow Template

Use the optional maintenance workflow template for recurring multi-role agent
systems such as Sleep/Dream/Architect/Installer/Reviewer flows:

```powershell
python -m flowguard maintenance-template --output .
```

The scaffold writes:

- `.flowguard/maintenance_workflow/model.py`
- `.flowguard/maintenance_workflow/run_checks.py`
- `docs/flowguard_maintenance_workflow.md`

The template models common maintenance failure modes:

- duplicate actions on repeated maintenance runs;
- a task marked completed without an architect/reviewer report;
- publishing before install/runtime synchronization;
- adoption evidence replacing executable checks.

It is a scaffold. Rename the roles and state fields to match the project, and
delete or extend checks that do not fit. It is not a required layer for ordinary
FlowGuard models.
