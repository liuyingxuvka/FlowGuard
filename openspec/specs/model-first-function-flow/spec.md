# model-first-function-flow Specification

## Purpose
This capability defines FlowGuard's default model-first route for turning ordinary behavior, state, and workflow questions into executable function-flow checks before implementation.
kernel deltas can be archived into a main spec.
## Requirements
### Requirement: model-first-function-flow exposes code structure recommendation
The `model-first-function-flow` Skill SHALL expose `code_structure_recommendation`
as a parallel route for direct code architecture recommendations and
model-derived implementation structure planning.

#### Scenario: Route is available
- **WHEN** the Skill route map is read
- **THEN** `code_structure_recommendation` is listed as a route beside
  `core_modeling`, `model_mesh_maintenance`, `test_mesh_maintenance`, and
  `structure_mesh_maintenance`

#### Scenario: Core modeling remains lightweight
- **WHEN** ordinary core modeling does not need implementation structure
  planning
- **THEN** the Skill does not require the code structure recommendation route

### Requirement: model-first-function-flow is a kernel, not the universal first stop
The `model-first-function-flow` Skill SHALL identify itself as the FlowGuard
kernel for general model-first applicability, ordinary behavior/state modeling,
unclear route selection, and cross-route coordination.

#### Scenario: Clear satellite match does not stop at kernel
- **WHEN** a task clearly matches a directly installed FlowGuard satellite
  skill
- **THEN** the kernel guidance says to use that satellite skill directly

#### Scenario: Kernel handles unclear or cross-route work
- **WHEN** the route is unclear, multiple FlowGuard routes may apply, or a core
  model is needed before selecting a narrower route
- **THEN** `model-first-function-flow` remains the appropriate starting point

### Requirement: model-first-function-flow routes staged development to DevelopmentProcessFlow
The `model-first-function-flow` Skill SHALL route non-trivial staged
development or modification tasks with validation to
`development_process_flow`, in addition to final done, archive, publish, and
release-readiness evidence checks.

#### Scenario: Kernel route map includes staged development
- **WHEN** the Skill Kernel route map is read
- **THEN** the `development_process_flow` trigger includes non-trivial staged
  development or modification, step ordering, touched artifacts, validation
  evidence, evidence freshness, peer writes, minimum revalidation, and V-style
  process confidence

#### Scenario: Kernel does not wait for final readiness
- **WHEN** the task has multiple meaningful development stages and validation
  but is not yet a release/archive/publish claim
- **THEN** the Skill Kernel guidance still routes the work to
  `development_process_flow`

### Requirement: Model-first checks consume field lifecycle boundaries
Model-first FlowGuard guidance SHALL surface field lifecycle coverage when a
model's state, input, output, schema, mode, or side-effect behavior depends on
software fields.

#### Scenario: Behavior field is missing from the model
- **WHEN** a field lifecycle row marks a field as behavior-bearing
- **AND** no model obligation, transition cell, state closure dimension, or
  scoped-out reason covers it
- **THEN** model-first review MUST report a model maturation gap before broad
  confidence

#### Scenario: Leaf field remains below the main model
- **WHEN** a field is fully accounted in a field lifecycle leaf row and has no
  behavior impact
- **THEN** model-first review MAY leave it outside the high-level state machine
  while keeping the scoped-out reason visible

### Requirement: Kernel routes bug repairs to existing model-miss ownership
The model-first kernel SHALL route non-trivial bug repairs through Existing
Model Preflight and Model-Miss Review when the repair may affect modeled
behavior, evidence, tests, code contracts, compatibility paths, or final
confidence.

#### Scenario: Non-trivial bug repair has route map entry
- **WHEN** the FlowGuard route map is read
- **THEN** bug repairs are visibly routed to existing model ownership preflight
  and Model-Miss Review before implementation-only work can claim completion

#### Scenario: Direct implementation remains narrow
- **WHEN** the bug is typo-only, formatting-only, or has no behavior/state/test
  confidence impact
- **THEN** the kernel may skip FlowGuard with a concrete reason

### Requirement: Model-first work derives three-way binding

The model-first FlowGuard kernel SHALL derive or request model obligations, code
contracts, and test evidence before claiming full FlowGuard confidence.

#### Scenario: Agent claims model coverage
- **WHEN** an agent claims that modeled behavior is covered
- **THEN** the claim must identify the model obligation ids, code contract ids,
  and test evidence ids, or report the missing links as gaps.

### Requirement: Model-first coverage claims derive transition obligations
The model-first FlowGuard kernel SHALL require transition coverage projection, or an explicit scoped-out reason, before broad claims that modeled behavior has matching test coverage.

#### Scenario: Broad coverage claim uses transition matrix
- **WHEN** a model-first workflow claims broad model-to-test coverage for state transitions
- **THEN** the workflow derives a transition coverage matrix and passes generated obligations to Model-Test Alignment or routes large evidence to TestMesh

#### Scenario: Transition matrix is scoped out
- **WHEN** a workflow intentionally does not derive a transition coverage matrix
- **THEN** the final claim MUST state the scoped-out reason and MUST NOT claim full transition-to-test coverage

### Requirement: Model-first summaries expose inheritable obligations
Model-first FlowGuard summaries SHALL expose anchored non-pass gaps as
maintenance obligations when those gaps require future owner-route work.

#### Scenario: Summary gap creates owner-route obligation
- **WHEN** `run_model_first_checks(...)` produces a state-closure,
  topology-hazard, conformance, scenario, contract, progress, skipped, or
  not-run gap that has a concrete model, input, state, code, test, or
  public-surface anchor
- **THEN** the summary MUST be able to expose a maintenance obligation for that
  gap
- **AND** the obligation MUST preserve the owner route needed to resolve it

#### Scenario: Clean pass has no open obligations
- **WHEN** all summary sections pass and no scoped or not-run confidence gap is
  present
- **THEN** the summary MUST NOT invent open maintenance obligations

### Requirement: Model-first checks run automatic topology hazard review

FlowGuard SHALL run a default model-topology hazard review inside
`run_model_first_checks(...)` before broad confidence is summarized.

#### Scenario: Topology hazard section is always present

- **GIVEN** a model-first check plan with a workflow
- **WHEN** `run_model_first_checks(...)` runs
- **THEN** the summary MUST include a `topology_hazard` section
- **AND** metadata MUST include the reviewed topology hazard plan and report.

#### Scenario: Unanchored AI concern cannot block confidence

- **GIVEN** a topology hazard candidate with a hard disposition
- **AND** the candidate has no concrete topology anchor
- **WHEN** `review_topology_hazards(...)` runs
- **THEN** the candidate MUST be reported as observation-only
- **AND** it MUST NOT block confidence.

#### Scenario: Anchored future-use hazard stays visible

- **GIVEN** the topology contains a repeatable side effect, external boundary,
  old/new compatibility path, coarse terminal, shared writer, or parent/child
  compression landmark
- **WHEN** no current evidence handles or scopes the derived hazard
- **THEN** the topology hazard report MUST return scoped or blocked confidence
- **AND** it MUST name the required owner route.

### Requirement: Topology hazard APIs are public helper APIs

FlowGuard SHALL expose topology hazard helper APIs through the public helper API
and route registry without adding them to the minimal core `Explorer` API.

#### Scenario: Route-scoped discovery includes topology hazard review

- **WHEN** callers inspect `FLOWGUARD_ROUTE_API`
- **THEN** a `model_topology_hazard_review` group MUST list the topology
  digest, usage intent, hazard candidate, report, inference, and review helper
  names.

### Requirement: Model-first checks run automatic state closure review

FlowGuard SHALL run a default state/input closure review inside
`run_model_first_checks(...)` before broad confidence is summarized.

#### Scenario: Inferred unknown policy scopes confidence

- **GIVEN** a model-first check plan with finite external inputs or finite
  dataclass state fields
- **WHEN** the caller does not provide an explicit state closure policy
- **THEN** FlowGuard MUST infer visible dimensions and representative unknown
  cases
- **AND** the summary MUST include a `state_closure` section with scoped
  confidence rather than treating the finite enumeration as a full pass.

#### Scenario: Explicit safe open boundary passes closure

- **GIVEN** a `StateClosurePlan` declares an `open_boundary` dimension
- **AND** representative unknown cases are supplied or generated
- **AND** the handling rejects, blocks, isolates, or routes unknown values before
  side effects
- **WHEN** `review_state_closure(...)` runs
- **THEN** the closure report MUST allow full state closure confidence for that
  dimension.

#### Scenario: Unsafe unknown handling blocks confidence

- **GIVEN** an open or unbounded closure dimension
- **WHEN** unknown values are accepted as normal flow or can cause side effects
  before resolution
- **THEN** the closure report MUST block confidence instead of returning a clean
  pass.

### Requirement: State closure APIs are public helper APIs

FlowGuard SHALL expose state closure helper APIs through the public helper API
and route registry without adding them to the minimal core `Explorer` API.

#### Scenario: Route-scoped discovery includes state closure

- **WHEN** callers inspect `FLOWGUARD_ROUTE_API`
- **THEN** a `state_closure` group MUST list the state closure helper types,
  constants, inference helper, and review helper.

### Requirement: Model-first routing begins with plan detailing for vague non-trivial work
The model-first-function-flow guidance SHALL route vague or under-specified non-trivial work through plan detailing before behavior modeling.

#### Scenario: Vague request uses plan detail first
- **WHEN** an agent receives a non-trivial request with only a rough idea or short plan
- **THEN** the model-first guidance directs the agent to create or review plan-detail rows before writing the core `Input x State -> Set(Output x State)` model

#### Scenario: Existing detailed plan can proceed directly
- **WHEN** the request already includes current structured plan-detail evidence
- **THEN** the model-first guidance may consume that evidence and continue to the smallest owning FlowGuard route

### Requirement: Model claims preserve plan-detail scope
The model-first-function-flow guidance SHALL preserve plan-detail scoped, missing, or human-review findings as model confidence boundaries.

#### Scenario: Plan detail is scoped
- **WHEN** plan-detail review reports scoped confidence
- **THEN** the model-first result cannot claim broader completion confidence until the scoped gap is closed by downstream evidence

### Requirement: model-first-function-flow teaches minimum valuable entry
The model-first-function-flow guidance SHALL teach a minimum valuable model
entry instead of a thin default path for non-trivial model creation and model
deepening work.

#### Scenario: Skill guidance names minimum valuable model
- **WHEN** an agent reads the model-first-function-flow skill
- **THEN** the default entry guidance requires a protected error class, modeled state, side effects, completion evidence, and a known-bad case

#### Scenario: Thin entry no longer controls default wording
- **WHEN** docs or installed skill guidance describe the default model-first path
- **THEN** they use minimum valuable model language and do not present a thin happy-path model as sufficient

### Requirement: model-first-function-flow routes template search and harvest
The model-first-function-flow guidance SHALL route new or deepened model work
through public/local template search before modeling and local candidate harvest
after reusable successful modeling.

#### Scenario: Search before modeling
- **WHEN** an agent starts a new or materially deepened model
- **THEN** the guidance requires public and local template search or an explicit scoped skip

#### Scenario: Harvest after reusable modeling
- **WHEN** a completed model introduces a reusable protected error class and known-bad case
- **THEN** the guidance instructs the agent to save or report a local candidate template

