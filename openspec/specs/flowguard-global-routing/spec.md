# flowguard-global-routing Specification

## Purpose
This capability defines FlowGuard's Flowguard Global Routing behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Global routing prefers direct FlowGuard satellite skills
The global Codex FlowGuard guidance SHALL first check whether a direct
FlowGuard satellite skill clearly matches the task and SHALL prefer that direct
skill over the general public `flowguard` kernel when the match is clear.

#### Scenario: Staged development routes directly
- **WHEN** a task is non-trivial staged development or modification with
  validation, such as plan, edit, test, fix, and verify
- **THEN** the global guidance routes to `flowguard-development-process-flow`
  instead of treating the general `flowguard` kernel alone as sufficient

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
- **THEN** the global guidance routes to the public `flowguard` kernel, which
  may select its internal model-first workflow

### Requirement: FlowGuard satellite routes are peers
The global guidance SHALL list FlowGuard satellite skills as peer routes and
SHALL NOT describe the public `flowguard` kernel as the mandatory parent entry
for every FlowGuard task.

#### Scenario: Peer route table is visible
- **WHEN** a Codex agent reads the global FlowGuard section or repository
  AGENTS snippet
- **THEN** it sees a route table for `flowguard-development-process-flow`,
  `flowguard-ui-flow-structure`, `flowguard-code-structure-recommendation`,
  `flowguard-model-test-alignment`, `flowguard-test-mesh`,
  `flowguard-structure-mesh`, `flowguard-model-mesh`,
  `flowguard-model-miss-review`, and `flowguard`

#### Scenario: Kernel scope is bounded
- **WHEN** the public `flowguard` skill guidance is read
- **THEN** it says the kernel owns ordinary behavior/state modeling, unclear
  route selection, and cross-route coordination, while clear direct satellite
  matches should use the matching satellite

### Requirement: Multi-skill workflow rehearsal enters the development-process simulator
The global Codex FlowGuard guidance SHALL route non-trivial tasks that may
require multiple installed skills, uncertain skill selection, cross-skill
ordering, external side effects, staged validation, or non-trivial completion
evidence to `flowguard-development-process-flow` first, recording
`agent_workflow` before its owner-internal rehearsal review.

#### Scenario: Complex multi-skill task rehearses first
- **WHEN** a task may involve several installed Codex skills, plugins, tools,
  or staged validation paths
- **THEN** the global guidance selects `flowguard-development-process-flow`
  before execution begins
- **AND** the owner selects its internal `agent_workflow` mode only when a full
  skill/tool workflow rehearsal is needed

#### Scenario: Fresh snapshot is part of routing
- **WHEN** the owner selects its internal `agent_workflow` mode
- **THEN** the guidance requires a fresh current-machine skill snapshot for
  that invocation
- **AND** it forbids treating cached skill lists as current evidence

#### Scenario: Tiny tasks can skip rehearsal
- **WHEN** the task is a trivial read-only answer, formatting-only edit, direct
  command answer, or obvious low-risk single-skill task
- **THEN** the guidance may skip the `agent_workflow` simulator mode with a
  concrete reason

### Requirement: Installed route groups
FlowGuard global routing SHALL expose installed satellite routes as route groups with stable ids, trigger summaries, minimal inputs, primary outputs, evidence boundaries, and downstream handoffs.

#### Scenario: Specialist route has public helpers
- **WHEN** a specialist route exports public helpers, templates, docs, or installed skill guidance
- **THEN** the route SHALL have a corresponding route discovery group unless it is explicitly scoped out with a reason

### Requirement: Handoff continuity
Route groups SHALL express how SummaryReport findings, typed maintenance obligations, ExistingModelPreflight, FieldLifecycleMesh, Model-Test Alignment, StructureMesh, TestMesh, ModelMesh, DevelopmentProcessFlow, ModelMaturation, Risk Evidence Ledger, and Closure Contract hand off directly to one another.

#### Scenario: Maintenance finding identifies a route owner
- **WHEN** a finding or maintenance obligation names a current route owner
- **THEN** route discovery SHALL provide the minimal typed inputs and next-action path for that owner
- **AND** no retired routing intermediary is inserted

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
Global FlowGuard guidance SHALL make normal FlowGuard work inherit relevant open maintenance obligations through their existing owners instead of invoking a separate technical-debt or maintenance-scan route.

#### Scenario: Existing obligation is part of route selection
- **WHEN** a non-trivial coding, prompt, skill, test, process, release, archive, or publish task touches a model, code path, test surface, or public entrypoint with open FlowGuard obligations
- **THEN** global routing MUST include those exact obligations in route selection
- **AND** it MUST route each obligation directly to its named current owner

#### Scenario: No standalone technical-debt route
- **WHEN** a task asks FlowGuard to reduce technical-debt risk naturally during ordinary use
- **THEN** global routing MUST use current owners such as ModelMaturation, Architecture Reduction, StructureMesh, Model-Test Alignment, DevelopmentProcessFlow, and Risk Evidence Ledger
- **AND** it MUST NOT require a separate technical-debt scanner or scan-plan conversion route

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
- **AND** records and executes its internal `plan_detailing` mode when full
  rows are needed

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
Global FlowGuard routing SHALL present only current public owner routes as direct AI-facing choices and SHALL pass typed findings, canonical relation handoffs, state-closure gaps, and guard-closure evidence through those owners.

#### Scenario: Helper is consumed through owner
- **WHEN** a task has a canonical relation, post-change finding, state-closure gap, or guard-family closure contribution
- **THEN** global routing MUST route it through the public owner that decides and validates that evidence
- **AND** it MUST NOT list the carrier or feeder as a competing generic first stop

#### Scenario: Retired route identity is requested
- **WHEN** routing input names Model Angle Deliberation, Maintenance Scan, or standalone Model Similarity as a current route
- **THEN** route selection fails visibly or reports the retired identity
- **AND** it MUST NOT reinterpret the old name as an alias for a current owner

#### Scenario: Route table stays compact
- **WHEN** reusable AGENTS guidance or the model-first kernel route map is read
- **THEN** it MUST show owner routes for ordinary AI selection
- **AND** it MUST describe only current delegated modes and feeders inside their owning route wording

### Requirement: DevelopmentProcessFlow is the process hot path
Global FlowGuard routing SHALL use `development_process_flow` as the direct
route id for rough-plan, multi-skill, staged execution, install, sync, release,
archive, publish, and final process claims.

#### Scenario: Simulator id is internal
- **WHEN** a task needs the development-process simulator
- **THEN** routing MUST select `development_process_flow`
- **AND** `development_process_simulator` MUST be treated as an internal helper
  or mode selector, not as a separate public route id

### Requirement: Canonical Route Ownership Projection
The global route registry SHALL be authoritative for stable route id, route role, entry policy, canonical owner skill, and typed next actions. Kernel route indexes, skill metadata, and generated route documentation MUST match that registry.

#### Scenario: Kernel route map names a different owner
- **WHEN** the kernel route projection disagrees with the registry's canonical owner
- **THEN** route-parity validation fails and identifies both owner values

#### Scenario: Prompt route id is stale
- **WHEN** a skill prompt declares a route id absent from the registry
- **THEN** route-parity validation fails before SkillGuard certification

### Requirement: Internal Ownership For Cross-Cutting Helpers
Primary Path Authority SHALL be an internal route owned by Behavior Commitment Ledger. Risk Evidence Ledger, FlowGuard self-maintenance, and Risk Template Library SHALL be kernel-owned internal routes unless a future specification promotes one to an independently invocable public skill. PlanDetailing and AgentWorkflow SHALL remain delegated modes owned by DevelopmentProcessFlow.

#### Scenario: Primary Path Authority is routed
- **WHEN** a path-sensitive commitment requires Primary Path Authority evidence
- **THEN** the handoff resolves to the BCL-owned internal PPA route and not to DevelopmentProcessFlow as a substitute public owner

#### Scenario: Kernel risk route is selected
- **WHEN** the kernel selects Risk Evidence Ledger for final claim gating
- **THEN** the target resolves as a kernel-owned internal route and does not require a nonexistent public skill

### Requirement: Default Replacement Of Legacy Handoffs
After migration, bare-string handoffs and legacy alias targets MUST NOT remain as an alternate successful routing path. Legacy input MAY produce a typed migration diagnostic but SHALL NOT be executed successfully.

#### Scenario: Legacy bare string is supplied
- **WHEN** a caller supplies an untyped historical next-action string
- **THEN** the system returns a migration error naming the required typed target and does not follow the legacy path

### Requirement: Summary reports and typed findings hand off directly to current owners
Global FlowGuard routing SHALL send each SummaryReport finding, maintenance obligation, model-depth gap, structure finding, and reduction candidate directly to the one current route that owns its decision and evidence. No intermediate MaintenanceScan or ModelAngle route SHALL be required to translate, repeat, or approve that handoff.

#### Scenario: A typed finding already names its owner
- **WHEN** a SummaryReport or current evidence record names DevelopmentProcessFlow, ModelMaturation, Architecture Reduction, StructureMesh, Model-Test Alignment, ModelMesh, TestMesh, or another current specialist
- **THEN** global routing provides that owner with the finding's exact source, scope, affected identities, evidence status, and unresolved gaps
- **AND** it MUST NOT create an intermediate scan plan or deliberation report

#### Scenario: A model-depth gap is discovered
- **WHEN** current coverage is missing a state, branch, child, boundary, finite case, binding, or evidence dimension
- **THEN** routing records the gap in TaskCoverageDemand and sends one typed contribution to ModelMaturation
- **AND** it MUST NOT require a separate open-ended angle inventory

### Requirement: ExistingModelPreflight owns current-owner lookup before boundary choice
Global FlowGuard routing SHALL use ExistingModelPreflight to resolve exact current blueprint, commitment, surface, and owner identities before a boundary is reused, extended, split, reduced, or created. Canonical relation handoffs MAY inform that bounded decision, but no standalone similarity or deliberation route SHALL own it.

#### Scenario: A task resembles another modeled behavior
- **WHEN** a current canonical relation connects the affected behavior to another model, surface, owner, or mechanism
- **THEN** ExistingModelPreflight consumes that relation inside the exact affected owner closure
- **AND** the selected downstream owner remains responsible for its decision and proof

#### Scenario: No current relation or owner exists
- **WHEN** owner lookup or canonical relation evidence is absent, stale, ambiguous, or blocked
- **THEN** preflight preserves the gap or enters explicit non-authoritative adoption discovery
- **AND** routing MUST NOT launch a free-form similarity or angle search as a substitute for current authority

### Requirement: FlowGuard-managed project changes propagate through affected owners
For non-trivial FlowGuard-managed project work, global routing SHALL derive the affected current owners from changed artifacts, commitments, blueprint bindings, and canonical topology, then route each typed obligation directly to its owner before broad completion confidence.

#### Scenario: A changed artifact affects current obligations
- **WHEN** behavior, models, tests, structure, workflow guidance, release assets, or evidence-bearing artifacts change
- **THEN** DevelopmentProcessFlow records the affected owner set and each owner receives its typed obligation
- **AND** broad confidence waits for current owner evidence rather than an intermediate maintenance-scan receipt

#### Scenario: Tiny work has no affected modeled obligation
- **WHEN** a task is a tiny copy edit, formatting-only change, direct command answer, or read-only explanation
- **THEN** routing MAY record that no non-trivial affected owner was triggered
