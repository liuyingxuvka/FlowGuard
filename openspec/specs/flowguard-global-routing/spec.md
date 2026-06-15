# flowguard-global-routing Specification

## Purpose
This capability defines FlowGuard's Flowguard Global Routing behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Global routing prefers direct FlowGuard satellite skills
The global Codex FlowGuard guidance SHALL first check whether a direct
FlowGuard satellite skill clearly matches the task and SHALL prefer that direct
skill over `model-first-function-flow` when the match is clear.

#### Scenario: Staged development routes directly
- **WHEN** a task is non-trivial staged development or modification with
  validation, such as plan, edit, test, fix, and verify
- **THEN** the global guidance routes to `flowguard-development-process-flow`
  instead of treating `model-first-function-flow` alone as sufficient

#### Scenario: UI interaction routes directly
- **WHEN** UI controls, screens, menus, navigation, overlays, visible states,
  journey coverage, UI text hierarchy, or implementation click-through
  evidence are the main risk
- **THEN** the global guidance routes to `flowguard-ui-flow-structure`

#### Scenario: Model-test evidence routes directly
- **WHEN** model obligations, tests, code contracts, scenarios, invariants,
  hazards, or evidence coverage need direct comparison
- **THEN** the global guidance routes to `flowguard-model-test-alignment`

#### Scenario: Ambiguous routing uses kernel
- **WHEN** no direct satellite route clearly matches, several routes apply, or
  a core behavior/state model is needed before narrowing
- **THEN** the global guidance routes to `model-first-function-flow`

### Requirement: FlowGuard satellite routes are peers
The global guidance SHALL list FlowGuard satellite skills as peer routes and
SHALL NOT describe `model-first-function-flow` as the mandatory parent entry
for every FlowGuard task.

#### Scenario: Peer route table is visible
- **WHEN** a Codex agent reads the global FlowGuard section or repository
  AGENTS snippet
- **THEN** it sees a route table for `flowguard-development-process-flow`,
  `flowguard-ui-flow-structure`, `flowguard-code-structure-recommendation`,
  `flowguard-model-test-alignment`, `flowguard-test-mesh`,
  `flowguard-structure-mesh`, `flowguard-model-mesh`,
  `flowguard-model-miss-review`, and `model-first-function-flow`

#### Scenario: Kernel scope is bounded
- **WHEN** the `model-first-function-flow` skill guidance is read
- **THEN** it says the kernel owns ordinary behavior/state modeling, unclear
  route selection, and cross-route coordination, while clear direct satellite
  matches should use the matching satellite

### Requirement: Multi-skill workflow rehearsal enters the development-process simulator
The global Codex FlowGuard guidance SHALL route non-trivial tasks that may
require multiple installed skills, uncertain skill selection, cross-skill
ordering, external side effects, staged validation, or non-trivial completion
evidence to `flowguard-development-process-flow` first, recording
`agent_workflow` before any delegated `flowguard-agent-workflow-rehearsal`
review.

#### Scenario: Complex multi-skill task rehearses first
- **WHEN** a task may involve several installed Codex skills, plugins, tools,
  or staged validation paths
- **THEN** the global guidance selects `flowguard-development-process-flow`
  before execution begins
- **AND** the simulator delegates to `flowguard-agent-workflow-rehearsal` only
  when a full skill/tool workflow rehearsal is needed

#### Scenario: Fresh snapshot is part of routing
- **WHEN** the simulator delegates to `flowguard-agent-workflow-rehearsal`
- **THEN** the guidance requires a fresh current-machine skill snapshot for
  that invocation
- **AND** it forbids treating cached skill lists as current evidence

#### Scenario: Tiny tasks can skip rehearsal
- **WHEN** the task is a trivial read-only answer, formatting-only edit, direct
  command answer, or obvious low-risk single-skill task
- **THEN** the guidance may skip the `agent_workflow` simulator mode with a
  concrete reason

### Requirement: Global routing preserves existing routes while adding handoff continuation
Global FlowGuard routing SHALL preserve the existing direct satellite route
map and SHALL treat SummaryReport-to-MaintenanceScan-to-specialist output as a
continuation inside the existing route system, not a new parent route.

#### Scenario: Existing route remains owner
- **WHEN** a structured handoff recommends Model-Test Alignment,
  DevelopmentProcessFlow, ModelMesh, TestMesh, StructureMesh, Model
  Maturation, or AgentWorkflowRehearsal
- **THEN** the recommended existing route SHALL remain the owner of validation
  evidence and claim promotion

#### Scenario: Handoff is not a session runner
- **WHEN** the AI hot path describes the handoff sequence
- **THEN** it SHALL NOT introduce a new top-level session runner or require
  every task to pass through a parallel workflow

### Requirement: Installed route groups
FlowGuard global routing SHALL expose installed satellite routes as route groups with stable ids, trigger summaries, minimal inputs, primary outputs, evidence boundaries, and downstream handoffs.

#### Scenario: Specialist route has public helpers
- **WHEN** a specialist route exports public helpers, templates, docs, or installed skill guidance
- **THEN** the route SHALL have a corresponding route discovery group unless it is explicitly scoped out with a reason

### Requirement: Handoff continuity
Route groups SHALL express how SummaryReport, MaintenanceScan, ExistingModelPreflight, FieldLifecycleMesh, Model-Test Alignment, StructureMesh, TestMesh, ModelMesh, DevelopmentProcessFlow, Risk Evidence Ledger, and Closure Contract hand off to one another.

#### Scenario: Maintenance finding identifies a route owner
- **WHEN** a finding or maintenance obligation names a route owner
- **THEN** route discovery SHALL provide the minimal inputs and next-action path for that owner

### Requirement: Global routing includes model-angle deliberation
FlowGuard global routing SHALL expose model-angle deliberation as a lightweight
preflight companion for open-ended model sufficiency review.

#### Scenario: Route is selected
- **WHEN** a task may need another model angle beyond the current model boundary
- **THEN** routing guidance MUST point to model-angle deliberation before or during existing-model preflight

#### Scenario: Specialist route owns follow-up
- **WHEN** deliberation chooses a model update, child model, code boundary, freshness review, or human review
- **THEN** routing guidance MUST hand off to the existing owner route rather than adding a parallel session runner

### Requirement: Replacement defaults to disposition
FlowGuard global routing SHALL treat feature replacement, route migration,
field migration, prompt externalization, or compatibility cleanup as requiring
old-path and old-field disposition unless explicit compatibility intent is
declared.

#### Scenario: Replacement has no compatibility intent
- **WHEN** a user asks for a new path to replace old behavior
- **AND** the user does not explicitly request compatibility preservation
- **THEN** FlowGuard routing MUST require disposition evidence for old runtime
  paths, old fields, old tests, old prompt/config surfaces, and old public
  entrypoints before full done confidence

#### Scenario: Compatibility is explicit
- **WHEN** compatibility preservation is declared for a public API, old data,
  old schema, or external integration
- **THEN** FlowGuard routing MUST keep that compatibility surface visible and
  route it through the owner route for parity, migration, or rejection evidence

### Requirement: Global routing inherits open FlowGuard obligations
Global FlowGuard guidance SHALL make normal FlowGuard work inherit relevant open
maintenance obligations through existing routes instead of invoking a separate
technical-debt scanner.

#### Scenario: Existing obligation is part of route selection
- **WHEN** a non-trivial coding, prompt, skill, test, process, release, archive,
  or publish task touches a model, code path, test surface, or public entrypoint
  with open FlowGuard obligations
- **THEN** global routing MUST include those obligations in route selection
- **AND** it MUST route to the existing owner route named by the obligation

#### Scenario: No standalone technical-debt route
- **WHEN** a task asks FlowGuard to reduce technical-debt risk naturally during
  ordinary use
- **THEN** global routing MUST use existing FlowGuard routes such as
  maintenance scan, model maturation, Architecture Reduction, StructureMesh,
  Model-Test Alignment, DevelopmentProcessFlow, and Risk Evidence Ledger
- **AND** it MUST NOT require a separate technical-debt scanner route

### Requirement: FlowGuard-managed projects use maintenance scan before broad claims
Global FlowGuard routing SHALL present the maintenance scan as the compact default guardrail for FlowGuard-managed project work where changed artifacts may require model/code/test/structure upkeep.

#### Scenario: Non-trivial project work enters maintenance scan
- **WHEN** an agent works in a project with FlowGuard adoption records
- **AND** the task changes behavior, models, tests, structure, workflow guidance, release assets, or evidence-bearing artifacts
- **THEN** global routing MUST direct the agent to run or construct a maintenance scan before broad completion confidence
- **AND** the scan MUST route any resulting required actions to the existing specialist FlowGuard routes

#### Scenario: Tiny work can skip scan with reason
- **WHEN** the task is a tiny copy edit, formatting-only change, direct command answer, or read-only explanation
- **THEN** global routing MAY skip the maintenance scan with a concrete reason

### Requirement: Global routing does not duplicate satellite internals
Global FlowGuard routing SHALL name the selected route and hand off to the
owning satellite or reference without duplicating satellite-specific workflow
internals in multiple prompt surfaces.

#### Scenario: Reusable AGENTS guidance stays compact
- **WHEN** the reusable AGENTS snippet is read
- **THEN** it contains the global routing decision, hard gates, minimum
  valuable path, and compact route table
- **AND** it does not embed long helper inventories or route-specific prompt
  templates

#### Scenario: Route-specific detail is needed
- **WHEN** the selected route needs detailed helper APIs, hazard lists,
  examples, or prompt templates
- **THEN** the guidance points to the owning satellite reference or docs page
  instead of duplicating that detail in the global routing hot path

### Requirement: Global routing recognizes rough-plan expansion
FlowGuard global routing SHALL route non-trivial rough-plan expansion, plan completion, and "make this plan detailed" requests to the plan-detailing compiler.

#### Scenario: Rough plan routes to plan detailing
- **WHEN** a user asks to turn a vague idea or short plan into a detailed FlowGuard process plan
- **THEN** global routing selects the plan-detailing compiler before downstream FlowGuard routes

#### Scenario: Route still avoids trivial work
- **WHEN** the task is a tiny copy edit, direct command answer, or formatting-only change
- **THEN** global routing may skip plan detailing with a reason

### Requirement: Global routing uses a compact canonical decision table
Global FlowGuard guidance SHALL present one compact routing decision table for
ordinary AI use and SHALL avoid repeating long helper inventories in the hot
path.

#### Scenario: Agent reads reusable AGENTS guidance
- **WHEN** an agent reads `docs/agents_snippet.md`
- **THEN** it first sees task-size triage, the FlowGuard routing decision,
  minimum valuable path, hard gates, and a compact route table before any
  reference protocol detail

#### Scenario: Detailed route content is needed
- **WHEN** the selected route needs detailed protocol rules, helper API
  inventories, examples, or evidence ledgers
- **THEN** the guidance points to the matching skill reference or docs page
  instead of duplicating the full content in the AGENTS hot path

### Requirement: Duplicate route inventories are bounded
FlowGuard prompt tests SHALL prevent the kernel, AGENTS snippet, and satellite
skills from each carrying independent long-form route inventories.

#### Scenario: Route inventory grows in multiple hot paths
- **WHEN** tests detect duplicate long-form route/helper inventories across
  first-read prompt surfaces
- **THEN** they fail or require the extra detail to move behind the reference
  handoff before done/release confidence is claimed

### Requirement: Global routing sends rough plan discussions to the development-process simulator
Global FlowGuard routing SHALL send non-trivial plan discussions,方案 discussions,
acceptance-standard discussions, execution-step discussions, and AI-generated
outlines to `flowguard-development-process-flow` first as the
development-process simulator before implementation or final confidence routes.

#### Scenario: Plan discussion selects plan detailing
- **WHEN** a non-trivial user request asks to discuss, design, refine, or agree on a plan before execution
- **THEN** global routing selects `flowguard-development-process-flow` as the
  first process route
- **AND** records the `plan_detailing` simulator mode before delegating to
  `flowguard-plan-detailing-compiler` when full rows are needed

#### Scenario: Structured lifecycle review can use development process directly
- **WHEN** the user already provides structured lifecycle rows, artifact versions, validation evidence, and freshness rules
- **THEN** global routing may select `flowguard-development-process-flow` directly for lifecycle freshness review

### Requirement: Global routing composes simulator modes and delegated owners
Global FlowGuard routing SHALL compose DevelopmentProcessFlow,
PlanDetailing, and AgentWorkflowRehearsal by simulator mode and ownership
rather than exposing three competing first entries.

#### Scenario: Multi-skill plan composes routes
- **WHEN** a plan discussion produces structured PlanDetail rows and the work involves multiple skills, tools, agents, or side effects
- **THEN** global routing records `agent_workflow` in the simulator and hands
  the PlanDetail projection to AgentWorkflowRehearsal before execution

#### Scenario: Execution freshness composes routes
- **WHEN** the same plan enters implementation, validation, done, release, archive, or publish review
- **THEN** global routing records `execution_freshness` and uses
  DevelopmentProcessFlow for lifecycle freshness and claim support

### Requirement: Global routing blocks prose-only broad claims
Global FlowGuard routing SHALL prevent broad done, release, publish, archive, or production-confidence claims from relying only on prose plans when the task was non-trivial.

#### Scenario: Prose plan cannot support full completion
- **WHEN** a non-trivial plan discussion has no PlanDetail rows, workflow rehearsal handoff, or current lifecycle evidence
- **THEN** global routing keeps the final claim scoped or blocked until the missing structured evidence is created

### Requirement: Global routing uses public owner routes
Global FlowGuard routing SHALL present only public owner routes as direct
AI-facing route choices.

#### Scenario: Helper is consumed through owner
- **WHEN** a task needs model-angle review, similarity review, post-change
  maintenance scanning, state closure, or guard-family closure support
- **THEN** global routing MUST route the task through the public owner route
  that consumes that helper
- **AND** it MUST NOT list the helper as a competing generic first stop

#### Scenario: Route table stays compact
- **WHEN** reusable AGENTS guidance or the model-first kernel route map is read
- **THEN** it MUST show owner routes for ordinary AI selection
- **AND** it MUST describe delegated modes and feeders inside the owning route
  wording rather than as peer public entries

### Requirement: DevelopmentProcessFlow is the process hot path
Global FlowGuard routing SHALL use `development_process_flow` as the direct
route id for rough-plan, multi-skill, staged execution, install, sync, release,
archive, publish, and final process claims.

#### Scenario: Simulator id is internal
- **WHEN** a task needs the development-process simulator
- **THEN** routing MUST select `development_process_flow`
- **AND** `development_process_simulator` MUST be treated as an internal helper
  or mode selector, not as a separate public route id

### Requirement: ExistingModelPreflight owns angle and similarity consumption
Global FlowGuard routing SHALL use ExistingModelPreflight as the owner route
for current-model sufficiency, angle, and similarity evidence before selecting
or creating a boundary.

#### Scenario: Similarity is needed
- **WHEN** a task resembles another workflow or model
- **THEN** global routing MUST put similarity evidence into
  ExistingModelPreflight or a downstream owner
- **AND** it MUST NOT select model similarity as a standalone first-stop route

