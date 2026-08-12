# development-process-flow Specification

## Purpose
This capability defines how FlowGuard uses one development-process simulator
front door for plan discussion, multi-skill workflow setup, staged edits,
validation, install sync, shadow sync, release evidence, and done claims so
later work cannot reuse stale proof.
DevelopmentProcessFlow deltas can be archived into a main spec.
## Requirements
### Requirement: DevelopmentProcessFlow is the development-process simulator front door
The public `flowguard` kernel SHALL route
`development_process_flow` as the first process route for non-trivial rough
plan discussion, multi-skill workflow setup, lifecycle ordering, artifact
overwrite, validation freshness, minimum revalidation, and V-style lifecycle
confidence.

#### Scenario: Route is listed beside sibling routes
- **WHEN** the Skill route map is read
- **THEN** `development_process_simulator` and `development_process_flow` are
  listed beside `core_modeling`,
  `model_test_alignment`, `model_mesh_maintenance`, `test_mesh_maintenance`,
  and `structure_mesh_maintenance`

#### Scenario: Route does not supervise sibling routes
- **WHEN** DevelopmentProcessFlow references evidence produced by TestMesh,
  StructureMesh, ModelMesh, Model-Test Alignment, LongCheck, or Conformance
  Adoption
- **THEN** the Skill guidance says it may use the sibling evidence id and
  freshness metadata but MUST NOT inspect, replace, or supervise that sibling
  route's internal review

### Requirement: DevelopmentProcessFlow triggers for staged work with validation
FlowGuard SHALL present DevelopmentProcessFlow as the route for any
non-trivial staged development or modification task where step ordering,
touched artifacts, validation evidence, evidence freshness, peer writes, or
minimum revalidation affects whether the agent can safely continue or claim
done.

#### Scenario: Rough plan trigger enters simulator
- **WHEN** an agent is asked to discuss, refine, or accept a non-trivial rough
  plan
- **THEN** the Codex-facing guidance enters `flowguard-development-process-flow`
  first
- **AND** it records and executes the owner's internal `plan_detailing` mode

#### Scenario: Multi-skill trigger enters simulator
- **WHEN** a task may require several Codex skills, tools, plugins, external
  actions, or skipped-skill consequences
- **THEN** the Codex-facing guidance enters `flowguard-development-process-flow`
  first
- **AND** it records and executes the owner's internal `agent_workflow` mode

#### Scenario: Staged implementation trigger
- **WHEN** an agent is asked to complete a non-trivial task with staged actions
  such as plan, edit, test, fix, and verify
- **THEN** the Codex-facing DevelopmentProcessFlow guidance says to use
  `flowguard-development-process-flow` during planning

#### Scenario: Not reserved for release readiness
- **WHEN** a task is not yet at release, archive, publish, or final readiness
  but has multiple meaningful development stages and validation
- **THEN** the DevelopmentProcessFlow guidance still treats the route as
  applicable

#### Scenario: Trivial work can skip
- **WHEN** the task is a single-step typo, formatting-only edit, or pure
  explanation with no meaningful validation or artifact freshness risk
- **THEN** the guidance permits skipping DevelopmentProcessFlow with a clear
  reason

### Requirement: DevelopmentProcessFlow exposes internal simulator modes
FlowGuard SHALL keep one Codex front-door skill for development process work
while exposing named internal simulator modes for plan detail, agent workflow,
and execution freshness.

#### Scenario: Single front door wording
- **WHEN** the satellite skill and route documentation are read
- **THEN** they describe direct use of `flowguard-development-process-flow` as
  the front door
- **AND** they name `plan_detailing`, `agent_workflow`, and
  `execution_freshness` as internal modes rather than competing generic first
  entries

#### Scenario: Sibling evidence boundary preserved
- **WHEN** DevelopmentProcessFlow references evidence from ModelMesh, TestMesh,
  StructureMesh, Model-Test Alignment, LongCheck, or Conformance Adoption
- **THEN** the guidance continues to say it may use sibling evidence ids and
  freshness metadata but MUST NOT inspect, replace, or supervise sibling route
  internals

### Requirement: Evidence freshness and proof artifacts
FlowGuard SHALL let DevelopmentProcessFlow consume proof artifact metadata as
the concrete evidence boundary for validation freshness when a staged done,
release, archive, publish, or full-confidence claim depends on current proof.

#### Scenario: Evidence result path is missing
- **WHEN** strict process evidence is required and validation evidence declares
  a pass but has no result path or proof artifact reference
- **THEN** DevelopmentProcessFlow SHALL report incomplete validation evidence

#### Scenario: Artifact versions changed after proof
- **WHEN** a proof artifact covers older artifact versions than the current
  model, code, test, adapter, or requirement artifact
- **THEN** DevelopmentProcessFlow SHALL mark the proof stale and recommend
  revalidation

### Requirement: Development artifacts are versioned
FlowGuard SHALL allow projects to declare development process artifacts for
requirements, designs, models, source code, tests, validation adapters,
documentation, release assets, and sibling route reports with explicit current
versions and dependency metadata.

#### Scenario: Complete artifact registry
- **WHEN** every process action and evidence record references registered
  artifacts
- **THEN** DevelopmentProcessFlow reports no unknown-artifact finding

#### Scenario: Unknown artifact reference
- **WHEN** a process action or evidence record references an artifact that is
  not registered
- **THEN** DevelopmentProcessFlow reports an unknown-artifact finding

### Requirement: Process actions record lifecycle reads and writes
FlowGuard SHALL allow projects to declare ordered development process actions
with read artifacts, written artifacts, invalidated artifacts, produced
evidence, required evidence, actor metadata, and decision scope.

#### Scenario: Ordered lifecycle action
- **WHEN** an action writes a registered artifact
- **THEN** DevelopmentProcessFlow records that the artifact version changed for
  later evidence freshness checks

#### Scenario: Out-of-order lifecycle action
- **WHEN** an action declares an `order_after` dependency on an action that has
  not already occurred
- **THEN** DevelopmentProcessFlow reports an out-of-order process finding

### Requirement: Evidence freshness follows covered versions
FlowGuard SHALL mark validation evidence stale when a later process action
changes an artifact version that the evidence covers, directly invalidates that
evidence, or changes a verifier artifact used to produce that evidence.

#### Scenario: Code changes after unit pass
- **WHEN** unit-test evidence covers `code.module_a` at version 4 and a later
  action changes `code.module_a` to version 5
- **THEN** DevelopmentProcessFlow reports the unit-test evidence as stale

#### Scenario: Test changes after test pass
- **WHEN** test evidence covers `tests.module_a` as a verifier artifact and a
  later action changes `tests.module_a`
- **THEN** DevelopmentProcessFlow reports the earlier test evidence as stale

### Requirement: Freshness propagation is explicit
FlowGuard SHALL allow freshness rules that propagate upstream artifact changes
to downstream artifacts or evidence requirements, and SHALL report ambiguous or
unknown propagation policy before trusting a completion claim.

#### Scenario: Requirement change invalidates downstream evidence
- **WHEN** a freshness rule states that requirement changes invalidate design,
  model, code, and validation evidence, and a requirement changes after those
  records were produced
- **THEN** DevelopmentProcessFlow marks the affected downstream evidence stale

#### Scenario: Ambiguous freshness policy
- **WHEN** a completion claim depends on an artifact relationship with no
  explicit propagation rule
- **THEN** DevelopmentProcessFlow reports an ambiguous-freshness finding

### Requirement: Claims require current validation evidence
FlowGuard SHALL require done, release, archive, and publish-readiness claims to
be supported by current passing evidence that satisfies the relevant validation
requirements for the requested scope.

#### Scenario: Done claim with current evidence
- **WHEN** all required routine validation requirements have current passing
  evidence for current artifact versions
- **THEN** DevelopmentProcessFlow allows the done claim

#### Scenario: Release claim with stale evidence
- **WHEN** a release claim relies on evidence made stale by later artifact
  writes
- **THEN** DevelopmentProcessFlow reports a release-claim-with-stale-evidence
  finding and blocks release confidence

### Requirement: Background completion and skipped validation remain visible
FlowGuard SHALL distinguish current validation evidence from failed, skipped,
hidden-skip, not-run, timeout, running, and background progress-only evidence.

#### Scenario: Background progress-only evidence
- **WHEN** validation evidence is produced by a background run with progress
  output but no final exit or result artifact
- **THEN** DevelopmentProcessFlow reports progress-only evidence and does not
  count it as current validation coverage

#### Scenario: Hidden skipped validation
- **WHEN** validation evidence reports success while skipped validation is not
  visible
- **THEN** DevelopmentProcessFlow reports hidden-skipped validation and does not
  treat the evidence as sufficient

### Requirement: V-style validation pairs are supported
FlowGuard SHALL allow projects to declare validation requirements that pair
development artifacts with required validation evidence, including V-style
requirement/design/model/code-to-test relationships.

#### Scenario: Missing V-style validation pair
- **WHEN** a lifecycle plan declares a requirement-to-acceptance-test pair but
  no current evidence satisfies that pair
- **THEN** DevelopmentProcessFlow reports a missing V-model validation-pair
  finding

### Requirement: Minimum revalidation recommendations are derived
FlowGuard SHALL provide a deterministic revalidation recommendation for stale,
missing, failed, timeout, hidden-skip, progress-only, or not-run evidence that
prevents a claim from being supported.

#### Scenario: Revalidation after code and verifier changes
- **WHEN** a code artifact and its test artifact both change after prior test
  evidence
- **THEN** DevelopmentProcessFlow recommends rerunning the validation
  requirements that cover the current code and verifier artifact versions

### Requirement: Routine and release lifecycle scopes are distinct
FlowGuard SHALL distinguish routine lifecycle confidence from release
confidence so release-required evidence can be deferred visibly during routine
work but must be current for release claims, including local install and
shadow-workspace verification when the release process touches those artifacts.

#### Scenario: Routine scope defers release evidence
- **WHEN** a routine claim has all routine evidence current and release-required
  evidence pending
- **THEN** DevelopmentProcessFlow may allow routine confidence while reporting
  the release obligation as deferred

#### Scenario: Release scope requires release evidence
- **WHEN** a release claim lacks current release-required evidence
- **THEN** DevelopmentProcessFlow blocks release confidence

#### Scenario: Local release sync evidence is current
- **WHEN** a release claim includes a refreshed editable install and local
  shadow workspace sync
- **THEN** DevelopmentProcessFlow SHALL require final install and shadow import
  evidence for the released version before release confidence is claimed

### Requirement: DevelopmentProcessFlow consumes workflow step contracts
FlowGuard SHALL allow DevelopmentProcessFlow planning to consume workflow step contracts by projecting required receipts and claim gates into validation requirements that participate in missing, stale, skipped, failed, and progress-only evidence review.

#### Scenario: Step contract creates validation requirement
- **WHEN** a workflow step contract declares receipt `full_regression` as required for claim label `done_claimed`
- **THEN** the projection SHALL create a validation requirement that identifies the contract id, receipt id, and claim scope

#### Scenario: Projected requirement remains ordinary process evidence
- **WHEN** projected validation requirements are passed into `review_development_process_flow(...)`
- **THEN** DevelopmentProcessFlow SHALL review them with the same current, stale, skipped, failed, hidden-skip, not-run, running, and progress-only evidence rules used for manually declared validation requirements

### Requirement: Project adoption upgrade participates in process freshness
DevelopmentProcessFlow SHALL treat project FlowGuard adoption and upgrade
records as versioned process artifacts when a staged done, release, archive, or
publish claim depends on current FlowGuard guidance.

#### Scenario: FlowGuard guidance changes after validation
- **WHEN** a claim depends on FlowGuard Skill guidance or project adoption rules
- **AND** the FlowGuard package, managed AGENTS block, or project manifest has
  changed after the validation evidence was produced
- **THEN** DevelopmentProcessFlow reports that the prior evidence must be
  revalidated or the claim must be scoped

#### Scenario: Adoption log alone is insufficient
- **WHEN** an adoption or upgrade log entry exists but the required model/test
  validation evidence is missing or stale
- **THEN** DevelopmentProcessFlow does not treat the log entry as sufficient
  completion evidence

### Requirement: Development process planning accounts for reuse-ticket freshness
DevelopmentProcessFlow SHALL treat model and test reuse tickets as validation
evidence that can be invalidated by later writes.

#### Scenario: Later code write invalidates reused test result
- **WHEN** a development plan reuses a previous test result
- **AND** a later action changes a tested artifact, test source, dependency, or
  environment boundary named by the reuse ticket
- **THEN** the minimum revalidation plan SHALL require rerun or refreshed reuse
  proof before done confidence

#### Scenario: Unchanged evidence can remain scoped current
- **WHEN** the reuse ticket and proof artifact remain current after all later
  writes
- **THEN** DevelopmentProcessFlow MAY treat the reused result as current
  validation evidence within the ticket's declared scope

### Requirement: Revalidation recommendations expose AI rerun metadata
DevelopmentProcessFlow SHALL include route, proof-artifact, freshness-gap, and
claim-scope metadata in revalidation recommendations so AI agents can identify
the minimum rerun or evidence-refresh action.

#### Scenario: Stale evidence recommends concrete rerun
- **WHEN** evidence is stale because a covered artifact or verifier artifact
  changed
- **THEN** the recommendation SHALL include the requirement id, evidence id,
  command when known, artifact ids, freshness gap codes, and claim scopes that
  remain blocked until rerun

#### Scenario: Proof artifact is required
- **WHEN** the lifecycle plan requires proof artifacts and a recommendation
  concerns missing or stale evidence
- **THEN** the recommendation SHALL mark that proof artifact evidence is
  required before broad claim confidence can be promoted

### Requirement: Self-maintenance invalidation tracking
DevelopmentProcessFlow SHALL track edits to route graph, field lifecycle rows, structure facades, tests, installed skills, OpenSpec artifacts, adoption logs, install state, shadow workspace state, and local git state as evidence-invalidating actions.

#### Scenario: Later write changes route graph
- **WHEN** a route graph or public API grouping changes after validation
- **THEN** DevelopmentProcessFlow SHALL require API surface, skill guidance, and affected route checks to be rerun before done confidence

#### Scenario: Background validation is running
- **WHEN** a long validation is still running in the background
- **THEN** DevelopmentProcessFlow SHALL treat it as liveness only, not pass evidence

### Requirement: Field lifecycle evidence participates in freshness
DevelopmentProcessFlow SHALL treat field lifecycle meshes, field projections,
replacement decisions, old-field dispositions, model-code-test binding rows,
and bug repair closure rows as versioned artifacts that can stale validation
evidence.

#### Scenario: Field mesh changes after alignment
- **WHEN** a field lifecycle artifact changes after Model-Test Alignment
  evidence was produced
- **THEN** DevelopmentProcessFlow MUST mark the alignment evidence stale and
  recommend rerunning the owner route

#### Scenario: Bug repair field evidence changes
- **WHEN** a field root-cause record, same-class field case, owner code
  contract, old-field disposition, or old-path disposition changes after bug
  repair validation
- **THEN** DevelopmentProcessFlow MUST report bug repair closure stale before
  done or release confidence

### Requirement: DevelopmentProcessFlow tracks bug repair freshness
DevelopmentProcessFlow SHALL treat bug repair changes to model-miss
classification, model obligations, owner code contracts, observed-regression
tests, same-class tests, compatibility classifications, legacy path
dispositions, and risk-ledger rows as freshness-sensitive artifacts.

#### Scenario: Later repair edit stales earlier evidence
- **WHEN** a bug repair changes the model, code contract, test evidence,
  compatibility disposition, or legacy path disposition after validation
- **THEN** DevelopmentProcessFlow marks the affected alignment, closure, and
  risk evidence stale until the owning route reruns or refreshes evidence

#### Scenario: Final claim consumes current repair evidence
- **WHEN** a final done, release, archive, publish, or broad confidence claim
  closes a bug repair
- **THEN** DevelopmentProcessFlow requires current evidence ids from Model-Miss
  Review, Model-Test Alignment, TestMesh/ModelMesh when relevant, legacy-path
  disposition when relevant, and Risk Evidence Ledger / Closure Contract

### Requirement: Model-code-test changes stale linked evidence

DevelopmentProcessFlow SHALL treat model, code, and test edits as linked
invalidations for full confidence.

#### Scenario: One side of the binding changes
- **WHEN** a model obligation, code contract, code source, or test evidence row
  changes
- **THEN** previously claimed three-way binding evidence for the affected row
  becomes stale until the minimum revalidation plan refreshes it.

### Requirement: DevelopmentProcessFlow consumes plan-detail lifecycle rows
DevelopmentProcessFlow SHALL accept plan-detail projections as a lifecycle starting point for artifacts, actions, evidence, validation requirements, and freshness rules.

#### Scenario: Plan-detail projection supplies lifecycle registry
- **WHEN** plan-detail rows declare artifacts, ordered steps, produced evidence, required evidence, and validation requirements
- **THEN** the projected DevelopmentProcessPlan uses those rows for ordinary freshness and claim review

#### Scenario: Later action stale evidence remains blocked
- **WHEN** a projected plan changes an artifact after validation evidence was produced
- **THEN** DevelopmentProcessFlow reports the evidence as stale using the projected artifact and evidence ids

### Requirement: Human-operability artifacts stale UI completion evidence
DevelopmentProcessFlow SHALL treat changes to user task coverage, affordance,
action grammar, dialog/window, keyboard/focus, walkthrough, or related skill
guidance as stale for broad UI done/release claims until rerun.

#### Scenario: Action grammar changes after walkthrough
- **WHEN** a UI action grammar, task flow, or region map changes after
  walkthrough evidence was produced
- **THEN** development-process review requires revalidation before reusing the
  walkthrough for human-operable confidence

### Requirement: Source-baseline artifacts stale UI process evidence
DevelopmentProcessFlow SHALL treat UI work-mode, source-baseline, source-target mapping, approved difference dispositions, generic source interaction gates, and observed-source alignment artifacts as freshness-sensitive UI lifecycle artifacts.

#### Scenario: Source mapping changes after implementation evidence
- **WHEN** a source-based UI source-target mapping changes after UI implementation validation or walkthrough evidence was produced
- **THEN** DevelopmentProcessFlow marks the prior UI evidence stale and recommends rerunning the relevant UI Flow Structure gates

#### Scenario: Generic source interaction changes after evidence
- **WHEN** a source interaction branch, no-handler disposition, native/manual boundary, or approved difference changes after source-baseline evidence was produced
- **THEN** DevelopmentProcessFlow marks downstream source-based UI completion evidence stale

### Requirement: DevelopmentProcessFlow uses generic source-baseline names
DevelopmentProcessFlow SHALL name generic UI source-baseline artifacts and evidence in public guidance, templates, and constants rather than naming a specific source technology.

#### Scenario: Generic process surface uses source-specific name
- **WHEN** a current DevelopmentProcessFlow skill, template, API constant, or docs row names one source technology as a generic UI freshness gate
- **THEN** the process surface is incomplete until it is generalized

### Requirement: Writing-quality ledgers are freshness-sensitive artifacts
DevelopmentProcessFlow SHALL treat literature progression ledgers, method depth
ledgers, figure/table argument ledgers, AI-style density ledgers, citation or
footnote verification matrices, installed skill prompts, and final prose edits
as freshness-sensitive process artifacts when a workflow claims high-quality
writing completion.

#### Scenario: Final prose changes after citation audit
- **WHEN** final prose changes after a citation or footnote verification matrix
  is produced
- **THEN** DevelopmentProcessFlow MUST mark the citation evidence stale or
  require a scoped claim

#### Scenario: Citation audit is disposition-only
- **WHEN** source gaps were downgraded or dispositioned
- **AND** no citation or footnote verification matrix exists
- **THEN** DevelopmentProcessFlow MUST block strict source-verification claims
  while allowing a scoped no-invention/source-boundary claim

### Requirement: Owner-skill evidence remains explicit
DevelopmentProcessFlow SHALL preserve which owner skill is responsible for each
writing-quality gate and whether evidence is passed, scoped, stale, skipped, or
blocked.

#### Scenario: Literature progression gate is missing
- **WHEN** a thesis workflow claims deep literature review quality
- **AND** no LogicGuard or thesis-workflow progression evidence is current
- **THEN** DevelopmentProcessFlow MUST report the claim as unsupported

### Requirement: DevelopmentProcessFlow consumes plan-detail projections for rough plans
DevelopmentProcessFlow SHALL consume PlanDetail projections for non-trivial rough plans, AI-generated plans, or plan discussions before reviewing lifecycle order, evidence freshness, and completion claims.

#### Scenario: Rough plan projection supplies lifecycle rows
- **WHEN** a rough plan is converted to PlanDetail rows with artifacts, ordered steps, validation, evidence, and freshness rules
- **THEN** DevelopmentProcessFlow reviews the projected DevelopmentProcessPlan using the same ids and current freshness rules

#### Scenario: Prose-only lifecycle plan is not current evidence
- **WHEN** a non-trivial lifecycle claim relies only on a long Markdown or numbered prose plan
- **THEN** DevelopmentProcessFlow treats the claim as scoped or unsupported until structured lifecycle rows and evidence ids exist

### Requirement: Plan-detail gaps remain claim boundaries
DevelopmentProcessFlow SHALL preserve missing, skipped, stale, or scoped PlanDetail rows as lifecycle claim boundaries when deriving minimum revalidation.

#### Scenario: Missing subrequirement blocks done claim
- **WHEN** a projected plan has a subrequirement without current validation evidence or an accepted scoped omission
- **THEN** DevelopmentProcessFlow reports missing required revalidation or unsupported claim evidence before allowing full done confidence

#### Scenario: Later writes stale projected evidence
- **WHEN** implementation changes an artifact after projected validation evidence was produced
- **THEN** DevelopmentProcessFlow marks that evidence stale using the projected artifact and evidence ids

### Requirement: Capability coverage artifacts stale UI completion evidence
DevelopmentProcessFlow SHALL treat UI functional capability inventories, output contracts, capability-task mappings, implementation bindings, and capability coverage reports as freshness-sensitive UI lifecycle artifacts.

#### Scenario: Capability inventory changes after UI evidence
- **WHEN** a UI capability inventory, output contract, or implementation binding changes after human-operability or implementation validation evidence was produced
- **THEN** DevelopmentProcessFlow marks the affected UI evidence stale and requires rerunning the relevant UI Flow Structure gates

#### Scenario: UI task complete lacks capability evidence type
- **WHEN** a UI task is marked complete for functional implementation work
- **AND** no current capability coverage evidence kind or scoped-out boundary is recorded
- **THEN** DevelopmentProcessFlow blocks done or release confidence for that task

### Requirement: UI last-mile artifacts participate in process freshness
DevelopmentProcessFlow SHALL treat observed UI inventories, visible-surface
mappings, functional chains, source-baseline interaction gates,
implementation-validation runs, native/manual boundaries, installed-skill sync,
shadow-workspace sync, and local Git sync as freshness-sensitive artifacts.

#### Scenario: UI inventory changes after click evidence
- **WHEN** an observed UI inventory or visible control map changes after
  implementation validation evidence was produced
- **THEN** DevelopmentProcessFlow marks the affected UI evidence stale and
  recommends rerunning UI implementation validation

#### Scenario: Background regression is progress only
- **WHEN** a UI/model regression is started in the background but has no final
  exit status and result artifact
- **THEN** DevelopmentProcessFlow treats it as liveness only, not current
  validation evidence

#### Scenario: Skill guidance changes require sync evidence
- **WHEN** UI route skill guidance or public templates change
- **THEN** final confidence requires installed-skill sync, editable-install
  import evidence, shadow-workspace import evidence, and local Git sync status
  or an explicit scoped boundary

### Requirement: Payload and UI evidence freshness
DevelopmentProcessFlow SHALL treat UI action maps, payload schemas, import and
export behavior, AI work-package structure, validation prompts, installed
skills, and verifier artifacts as freshness-sensitive process artifacts.

#### Scenario: Payload schema changes after evidence
- **WHEN** payload schema, work-package structure, import/export code, or
  output formatting changes after payload validation evidence is produced
- **THEN** DevelopmentProcessFlow MUST mark that evidence stale and recommend
  rerunning the payload validation requirement

#### Scenario: UI action map changes after click-through evidence
- **WHEN** reachable UI controls, events, state transitions, or handlers change
  after browser, desktop, or manual click-through evidence is produced
- **THEN** DevelopmentProcessFlow MUST mark the click-through evidence stale

### Requirement: Installed prompt and package sync are process evidence
DevelopmentProcessFlow SHALL track repository skill guidance, installed Codex
skills, editable install state, source mirror sync, and package version as
process artifacts for done or release confidence.

#### Scenario: Repository prompt changed but installed prompt was not synced
- **WHEN** repository-managed FlowGuard skill guidance changes
- **AND** installed Codex skill content is not refreshed or verified
- **THEN** DevelopmentProcessFlow MUST report local installed behavior as
  unsynced or scoped

#### Scenario: Editable install points at current source
- **WHEN** local installed package behavior is claimed
- **THEN** evidence MUST show the imported package path, package version, and
  expected helper symbols from the current source

### Requirement: Contract-exhaustion evidence is freshness-sensitive
FlowGuard DevelopmentProcessFlow MUST treat ContractExhaustionMesh reports,
case ids, oracles, verifier artifacts, and downstream evidence as
freshness-sensitive lifecycle artifacts.

#### Scenario: Model change stales generated cases
- **WHEN** a model, field lifecycle row, payload contract, transition matrix,
  or parent-child closure model changes after contract-exhaustion evidence was
  produced
- **THEN** DevelopmentProcessFlow records the old report as stale until the
  owning evidence is regenerated or scoped

#### Scenario: Final claim consumes current report
- **WHEN** a done, release, archive, or publish claim depends on finite
  same-class or boundary exhaustion
- **THEN** DevelopmentProcessFlow requires current contract-exhaustion evidence
  and downstream route evidence before broad confidence

### Requirement: DevelopmentProcessFlow absorbs simulator and scan helpers
DevelopmentProcessFlow SHALL be the public owner for process simulation,
delegated process modes, typed post-change owner findings, evidence freshness,
install sync, shadow sync, release, archive, publish, and final process claims.

#### Scenario: Process simulator helper is consumed
- **WHEN** `review_development_process_simulator()` is used
- **THEN** its evidence MUST be reported under the `development_process_flow`
  route id
- **AND** callers MUST NOT publish `development_process_simulator` as a separate
  direct route starter

#### Scenario: Typed post-change findings are process inputs
- **WHEN** changed artifacts, peer writes, stale evidence, skipped routes, open
  obligations, or split/reduction signals are identified after work
- **THEN** each finding MUST preserve the affected artifact, status, current
  owner, and required next action
- **AND** DevelopmentProcessFlow MUST route the finding directly to that owner
  without creating an intermediate maintenance-scan plan or owner
- **AND** the finding MUST NOT become final confidence evidence by itself

#### Scenario: Maintenance scan is a process input
- **WHEN** a caller supplies a retired maintenance-scan plan or receipt as a
  process input
- **THEN** DevelopmentProcessFlow MUST reject the retired intermediary and
  consume the underlying typed findings through their exact current owners
- **AND** no maintenance-scan alias, adapter, or fallback route is created

### Requirement: Delegated process mode skills are owner-selected
DevelopmentProcessFlow SHALL select plan-detailing and agent-workflow mode
skills when those detailed reviews are required.

#### Scenario: Plan detailing is delegated
- **WHEN** DevelopmentProcessFlow selects `plan_detailing`
- **THEN** the owner-internal PlanDetailing implementation MAY produce detailed
  rows
- **AND** final process confidence remains owned by DevelopmentProcessFlow

#### Scenario: Agent workflow is delegated
- **WHEN** DevelopmentProcessFlow selects `agent_workflow`
- **THEN** the owner-internal AgentWorkflowRehearsal implementation MAY
  produce workflow evidence
- **AND** the internal helper MUST NOT be a competing public route or first
  stop

### Requirement: Development process consumes primary path authority evidence
DevelopmentProcessFlow SHALL include primary-path authority as a
freshness-sensitive validation gate for staged implementation, install sync,
and final done/release claims when path-sensitive behavior is in scope.

#### Scenario: Changed fallback surface stales evidence
- **WHEN** a changed artifact adds, removes, or modifies a path, alias,
  wrapper, helper route, compatibility facade, old field, fallback candidate,
  recovery path, or migration path
- **THEN** DevelopmentProcessFlow SHALL treat prior primary-path authority,
  runtime path, coverage, TestMesh, and RiskLedger evidence as stale

#### Scenario: Final claim lacks authority evidence
- **WHEN** a final claim depends on path-sensitive behavior and has no current
  primary-path authority evidence consumed by RiskEvidenceLedger
- **THEN** DevelopmentProcessFlow SHALL report the final claim as unsupported

### Requirement: Broad process claims require current ledger coverage
FlowGuard SHALL require DevelopmentProcessFlow to consume Behavior Commitment
Ledger coverage before done, release, publish, archive, production, or
full-confidence claims that cover non-trivial behavior.

#### Scenario: Ledger evidence is current
- **WHEN** a staged-work report has a current behavior ledger review with no blocking findings
- **THEN** DevelopmentProcessFlow MAY treat behavior commitment coverage as satisfied for that boundary

#### Scenario: Ledger evidence is missing
- **WHEN** a broad process claim has no current behavior ledger review
- **THEN** DevelopmentProcessFlow SHALL report a freshness-sensitive validation gap

### Requirement: Behavior process work selects a ledger change mode
FlowGuard SHALL require non-trivial behavior/API/CLI/skill/template/process
work to select a behavior-ledger change mode before implementation or broad
claims.

#### Scenario: Behavior change routes to ledger mode
- **WHEN** staged work affects external behavior or its source surfaces
- **THEN** DevelopmentProcessFlow SHALL preserve the selected mode among bootstrap, add, change, remove/replace, coverage-gap backfill, or model-miss check
- **AND** stale source surfaces SHALL invalidate broad behavior claims until ledger coverage is refreshed

### Requirement: Path-sensitive process claims consume PPA through the ledger
FlowGuard SHALL require path-sensitive behavior commitments to pass PPA before
DevelopmentProcessFlow claims broad completion.

#### Scenario: PPA blocks a ledger commitment
- **WHEN** a ledger report lists a PPA-blocked commitment
- **THEN** DevelopmentProcessFlow SHALL block done, release, publish, archive, production, and full-confidence claims for the affected boundary

### Requirement: DevelopmentProcessFlow consumes one current strategy decision
DevelopmentProcessFlow SHALL remain the single public process owner. It SHALL derive `process_optimization_status` as `not_needed`, `selected`, or `blocked`; SHALL require exactly one current optimization decision only when stable activation reasons are present; SHALL enforce hard outcome/evidence/safety/side-effect/dependency/authority equivalence; and SHALL preserve invalid candidates, hard blockers, not-run work, repair groups, affected revalidation, and stale-decision gaps in its claim boundary. It SHALL NOT create an alternate strategy report or route.

#### Scenario: Required optimization evidence is missing
- **WHEN** a process has an activation reason but no current decision evidence
- **THEN** DevelopmentProcessFlow reports `blocked` without creating an alternate process route

#### Scenario: Optimization is not needed
- **WHEN** a plan has no activation reason and no optimization decision
- **THEN** DevelopmentProcessFlow reports `not_needed` and omits optimizer details

#### Scenario: Decision exists without activation
- **WHEN** a caller supplies candidates or a decision for an ordinary inactive plan
- **THEN** DevelopmentProcessFlow rejects the unnecessary optimizer state

### Requirement: Minimum revalidation is coverage-aware
DevelopmentProcessFlow SHALL derive a deterministic revalidation set that covers every currently affected validation requirement and protected side-effect boundary before comparing equivalent covering sets. Estimated cost SHALL support only a preferred-set claim under current declared inputs; a bounded minimum claim requires a complete finite candidate set and current measured costs.

#### Scenario: One check covers two stale requirements
- **WHEN** one current check candidate covers two affected requirements and two other candidates cover one each at greater declared cost
- **THEN** the recommendation selects the covering check set and states whether its cost basis is estimated or measured

#### Scenario: Repair group omits one affected obligation
- **WHEN** a selected revalidation set leaves one repair-group obligation uncovered
- **THEN** DPF blocks the repair completion claim regardless of lower cost

### Requirement: Process closure requires post-snapshot evidence
DevelopmentProcessFlow SHALL reject done, archive, release, or publish
confidence based only on WorkContext status, provider checkboxes, planning
artifact presence, a pre-run snapshot, background liveness, or provider
metadata. Every FlowGuard-owned completion claim SHALL depend on current
terminal evidence from the exact native validation owner after all covered
artifacts and WorkContext fingerprints are final. Any provider-native
validation or archive action SHALL remain an external required action proved
only by that provider's own workflow.

#### Scenario: Session lacks terminal post evidence
- **WHEN** a FlowGuard-owned validation lacks a matching final input snapshot,
  terminal result, or current native evidence receipt
- **THEN** the process SHALL remain incomplete even if every WorkContext task
  or status artifact reports completion

#### Scenario: Provider status is the only proof
- **WHEN** a plan cites provider validation, task completion, or archive status
  without current evidence from the owner required by the FlowGuard claim
- **THEN** DevelopmentProcessFlow SHALL report the evidence gap and SHALL NOT
  convert the provider status into a FlowGuard receipt

#### Scenario: Provider-native lifecycle remains outstanding
- **WHEN** FlowGuard-owned implementation and validation evidence is current
  but a configured provider still requires native validation or archive
- **THEN** DevelopmentProcessFlow MAY report that external action as
  outstanding but SHALL NOT execute it or claim its completion

#### Scenario: Context changes after native validation
- **WHEN** a required WorkContext fingerprint changes after a dependent
  FlowGuard validation produced terminal evidence
- **THEN** DevelopmentProcessFlow SHALL stale the affected evidence and require
  the exact minimum owner-specific revalidation before closure

### Requirement: System-composition delivery follows a proof-first lifecycle
DevelopmentProcessFlow SHALL order system-composition work as benchmark/problem freeze, existing-owner and semantic freeze, candidate-architecture comparison, single checker-owner implementation, native evidence, prompt/skill activation, latest stable SkillGuard validation, clean consumer projection, local adoption/version sync, frozen-snapshot final verification, scoped Git commit, push/tag/source-only GitHub Release, and post-publish source/install/Git/remote parity verification.

#### Scenario: Prompt claims capability before native evidence
- **WHEN** agent guidance is updated before the executable API/CLI and benchmark acceptance exist
- **THEN** the process blocks activation because the AI would claim a capability the product cannot yet execute

#### Scenario: Large regressions run in the background
- **WHEN** model regressions are backgrounded under one declared owner
- **THEN** implementation may continue while progress is treated only as liveness and final confidence waits for complete terminal evidence

#### Scenario: Source changes after final validation starts
- **WHEN** a peer or owner changes a governed source, toolchain, or impact-plan input
- **THEN** the old final receipt becomes stale and no second unattended retry is started

#### Scenario: SkillGuard changes during implementation
- **WHEN** the maintained FlowGuard skill source is ready but SkillGuard has concurrent maintenance activity
- **THEN** the process freezes the latest stable released SkillGuard identity immediately before supervision, passes explicit run-state and evidence roots, and does not consume an older or moving maintainer checkout

#### Scenario: Post-publish correction is required
- **WHEN** source or release evidence changes after the release tag is published
- **THEN** the published tag remains immutable and the correction uses a new version rather than moving or overwriting the existing release

### Requirement: DevelopmentProcessFlow governs model-system revision order
DevelopmentProcessFlow SHALL order baseline freeze, isolated candidate
construction, affected-closure derivation, owner validation, activation
decision, compare-and-swap pointer update, installation synchronization, and
release closure. It SHALL defer model, commitment, field, test, and source
semantics to their existing owners.

#### Scenario: Candidate checks pass after the base advances
- **WHEN** the expected observed-head fingerprint no longer matches at activation time
- **THEN** DevelopmentProcessFlow blocks activation and requires a new baseline and affected validation

### Requirement: Promotion writes authority last
The process SHALL persist immutable candidate, decision, and activation
evidence before changing the sole observed-head pointer, and SHALL change that
pointer only once after all hard gates pass.

#### Scenario: Activation receipt cannot be persisted
- **WHEN** candidate validation passes but the activation receipt write fails
- **THEN** the observed-head pointer remains unchanged

### Requirement: Release closes distinct source and installation identities
Release closure SHALL separately verify source commit, package version, project
record, observed snapshot, author skill source, SkillGuard receipt, installed
consumer skills, installed Python distribution, Git tag, and published release.

#### Scenario: Source is current but installed skills are older
- **WHEN** source and model evidence pass but the installed skill projection differs
- **THEN** release readiness remains blocked until installation parity passes

### Requirement: DevelopmentProcessFlow consumes read-only WorkContexts
DevelopmentProcessFlow SHALL consume an explicit collection of zero, one, or
many reviewed WorkContexts as versioned development-process inputs. It SHALL
preserve context, adapter, native work, native owner, subject lane, artifact
role, behavior-source-surface, and fingerprint identities while ordering
FlowGuard-owned planning, implementation, validation, freshness, and release
actions. It SHALL NOT write provider artifacts, invoke provider execution or
validation, create provider sessions/caches/receipts, interpret provider status
as proof, or claim provider completion, synchronization, or archive authority.

#### Scenario: Work package enters the lifecycle
- **WHEN** one or more reviewed WorkContexts are selected as inputs to a
  DevelopmentProcessFlow plan
- **THEN** DPF SHALL order their read-only normalization, BCL/preflight target
  review, PlanDetail projection, FlowGuard-owned actions, and context
  freshness checks without creating or executing a provider work package

#### Scenario: Peer write occurs during the session
- **WHEN** a peer or unknown writer changes a covered WorkContext artifact
  after its fingerprint was consumed
- **THEN** DevelopmentProcessFlow SHALL preserve the peer write, stale every
  dependent row, and derive minimum owner-specific revalidation without
  rolling back the peer or opening a provider session

#### Scenario: Several contexts feed one lifecycle
- **WHEN** a process consumes contexts from several registered adapters or
  native work units
- **THEN** DevelopmentProcessFlow SHALL retain every context and artifact
  identity through actions, freshness rules, recommendations, and final claim
  boundaries without selecting one provider as the default

#### Scenario: A required artifact role is missing
- **WHEN** a selected WorkContext review reports a missing adapter-declared
  required role
- **THEN** DevelopmentProcessFlow SHALL block dependent actions and identify
  the native provider as the owner of any authoring or repair

#### Scenario: Provider execution metadata enters a context
- **WHEN** a WorkContext carries a command, check owner, session, cache,
  receipt, reuse decision, completion projection, or archive-readiness field
- **THEN** DevelopmentProcessFlow SHALL reject the context and SHALL NOT adopt
  or execute that authority

#### Scenario: A WorkContext targets product behavior
- **WHEN** a process step cites a WorkContext artifact mapped to a
  product-runtime commitment
- **THEN** DevelopmentProcessFlow SHALL preserve the product commitment as a
  typed target and SHALL NOT copy its behavior or primary-model ownership into
  the process action

### Requirement: Post-change scans gate lifecycle completion
DevelopmentProcessFlow SHALL consume a post-change owner scan after non-trivial
changes to stable business-intent inventories, behavior commitments, primary
paths, UI consistency models, materialized obligations, tests, public exports,
skills, templates, or synchronization artifacts. The scan SHALL preserve
changed artifacts, peer writes, skipped routes, stale evidence, open
obligations, and split or reduction signals, and SHALL route each unresolved
item to its existing owner before broad lifecycle confidence.

#### Scenario: Post-change scan finds stale owner evidence
- **WHEN** the post-change scan finds that a changed artifact invalidates
  Primary Path Authority, UI Flow Structure, Model-Test Alignment, TestMesh,
  install, shadow, formal-repository, or Git evidence
- **THEN** DevelopmentProcessFlow MUST derive the minimum owner-route
  revalidation and MUST NOT treat the prior evidence as current

#### Scenario: Required post-change scan is missing
- **WHEN** non-trivial work claims done, release, archive, publish, or full
  confidence without a current post-change scan for the changed artifacts
- **THEN** DevelopmentProcessFlow MUST report missing required revalidation and
  block the broad process claim

#### Scenario: Scan output is not pass evidence
- **WHEN** a post-change scan reports no new route recommendation but the
  required validation or synchronization receipts are absent
- **THEN** DevelopmentProcessFlow MUST treat the scan as routing input only and
  MUST NOT manufacture a passing validation result

#### Scenario: Background regression is visible but not terminal
- **WHEN** the post-change scan sees background regression progress without a
  current final TestMesh receipt
- **THEN** DevelopmentProcessFlow MUST preserve the run as liveness only and
  keep the associated completion gate unsatisfied

### Requirement: Synchronization domains have independent freshness gates
DevelopmentProcessFlow SHALL track repository source, editable or installed
package and skill state, shadow workspace, formal repository, and local Git
state as distinct freshness domains. Evidence from one domain MUST NOT stand in
for another domain, and a broad claim SHALL consume a current receipt for each
in-scope domain or preserve an explicit scoped boundary.

#### Scenario: Install evidence does not prove shadow or formal parity
- **WHEN** editable-install or installed-skill evidence is current but shadow
  workspace or formal-repository evidence is missing or stale
- **THEN** DevelopmentProcessFlow MUST report the missing synchronization gate
  instead of treating install success as cross-domain parity

#### Scenario: Shadow evidence does not prove local Git closure
- **WHEN** shadow-workspace validation passes but local Git evidence does not
  identify the current intended files and revision state
- **THEN** DevelopmentProcessFlow MUST keep local Git closure unsupported

#### Scenario: One synchronization domain changes after its receipt
- **WHEN** a package, installed skill, shadow copy, formal repository, or local
  Git artifact changes after that domain's receipt was produced
- **THEN** DevelopmentProcessFlow MUST stale that receipt and every dependent
  downstream claim while preserving unrelated current domain evidence

#### Scenario: All required synchronization receipts are current
- **WHEN** every in-scope install, shadow, formal-repository, and local Git gate
  has a current passing receipt for the same intended source revision
- **THEN** DevelopmentProcessFlow MAY treat synchronization freshness as
  satisfied without using one receipt as a proxy for another

### Requirement: Peer writes invalidate evidence without authorizing rollback
DevelopmentProcessFlow SHALL treat peer-agent or unknown-writer changes as
freshness events. It MUST preserve the current peer-written state, re-read and
merge against that state when work continues, and MUST NOT restore, overwrite,
or roll back peer work merely to recover an earlier green receipt.

#### Scenario: Peer writes after validation
- **WHEN** a peer or unknown writer changes an artifact after validation or
  synchronization evidence was produced
- **THEN** DevelopmentProcessFlow MUST mark the affected evidence stale and
  require validation against the current artifact state

#### Scenario: Earlier snapshot would restore green evidence
- **WHEN** restoring an earlier local snapshot would make an old receipt appear
  current but would discard peer-written content
- **THEN** DevelopmentProcessFlow MUST reject that rollback path and preserve
  the peer-written content

#### Scenario: Peer overlap cannot be merged safely
- **WHEN** current peer changes overlap the intended edit and the correct merge
  cannot be established from current evidence
- **THEN** DevelopmentProcessFlow MUST block the affected action or require
  human resolution rather than overwriting either side

### Requirement: Plane upgrade preserves route ownership
DevelopmentProcessFlow SHALL own lifecycle ordering and freshness for this change while leaving product-runtime behavior with its product owner, AI-operation behavior with AgentWorkflowRehearsal/owner models, and external behavior inventory with BCL.

#### Scenario: Development plan references product target
- **WHEN** a process step validates a product-runtime commitment
- **THEN** DevelopmentProcessFlow SHALL reference the commitment/evidence ids without becoming the product behavior owner

### Requirement: Plane upgrade lifecycle is explicitly ordered
The process plan SHALL order OpenSpec artifacts, model/field/structure decisions, schema, migration, lookup/preflight, miss/similarity integration, prompts/contracts, focused validation, installation parity, full validation, and final verification.

#### Scenario: Implementation begins before apply-ready artifacts
- **WHEN** required OpenSpec design/spec/verification/task artifacts are missing
- **THEN** the lifecycle review SHALL block implementation edits

#### Scenario: Prompt installation precedes focused checks
- **WHEN** installation is attempted before source prompt and contract checks pass
- **THEN** the lifecycle review SHALL report an out-of-order process step

### Requirement: Peer writes invalidate affected evidence without rollback
DevelopmentProcessFlow SHALL record peer/unknown writer changes as artifact-version changes, preserve those changes, and derive minimum revalidation rather than resetting or overwriting the workspace.

#### Scenario: Peer updates a shared module
- **WHEN** a peer changes a shared BCL/preflight/model file after local evidence was produced
- **THEN** affected evidence SHALL be stale
- **AND** the process SHALL reread, merge, and rerun the affected validations without reverting the peer change

### Requirement: Background validation remains visible
Long model regressions and full tests MAY run in the background while non-conflicting work continues, but DevelopmentProcessFlow SHALL distinguish liveness from final current evidence.

#### Scenario: Work continues during model regressions
- **WHEN** a registered regression child is running and the next edit does not depend on its final result
- **THEN** the process MAY continue that work
- **AND** SHALL keep completion blocked until final current receipts are consumed

### Requirement: Process Evidence Excludes AutoSplit Metrics
DevelopmentProcessFlow SHALL keep process evidence rows focused on evidence
freshness, artifacts, validation ownership, and proof references. Model/test
split measurements and split-gate status MUST remain in their current
ModelMesh or TestMesh owner evidence rather than returning as fields on
`ProcessEvidence`.

#### Scenario: Process evidence row is process-focused
- **WHEN** a process validation command is recorded
- **THEN** the `ProcessEvidence` row records its evidence identity, kind,
  status, artifacts, versions, verifier artifacts, validation requirements,
  owner, and proof reference without state-count or auto-split fields

#### Scenario: Split review is required
- **WHEN** model state count, test count, duration, or pending work suggests a
  split
- **THEN** the split review uses current ModelMesh or TestMesh evidence rather
  than fields on `ProcessEvidence`

### Requirement: DevelopmentProcessFlow owns implementation admission
DevelopmentProcessFlow SHALL provide an internal implementation-admission decision that separately reports model sufficiency, execution authorization, final admission, exact allowed scope, accepted open gaps, required validation, and invalidation conditions before production edits.

#### Scenario: Sufficient model and current request are admitted
- **WHEN** the current task has a task/candidate/coverage-matching closed-for-task maturation result and the user currently requests implementation within that scope
- **THEN** admission SHALL return ready for only that exact scope

#### Scenario: Open model without override is blocked
- **WHEN** required maturation gaps remain and the user has not explicitly accepted those gaps for an exact bounded scope
- **THEN** admission SHALL block production edits while preserving the maturation next actions

#### Scenario: Exact override allows only a scoped edit
- **WHEN** the user explicitly authorizes an exact reversible scope and accepts named current gap fingerprints
- **THEN** admission MAY return ready-scoped for only that scope and MUST preserve the non-full maturation status

### Requirement: Non-waivable boundaries remain authoritative
Implementation admission SHALL NOT waive a current read-only or no-code instruction, safety or approval boundary, unknown target, stale identity, scope mismatch, conflicting live ownership, or unavailable real toolchain.

#### Scenario: Current task is read-only
- **WHEN** the current request forbids code changes
- **THEN** implementation admission MUST return no-code-requested or blocked regardless of model sufficiency or an older authorization

### Requirement: Authorization becomes stale when its subject changes
An implementation authorization SHALL bind the current task, request evidence, allowed actions and artifacts, accepted gap fingerprints, required validations, source/model/coverage fingerprints, and invalidation rules.

#### Scenario: Authorized scope changes
- **WHEN** the task, allowed path, candidate model, coverage universe, accepted gaps, source identity, or required validation changes
- **THEN** the prior authorization MUST become stale and MUST NOT admit implementation

### Requirement: Implementation admission requires verified sufficiency and separate permission
DevelopmentProcessFlow SHALL issue `ready` or `ready_scoped` only when the exact task has a current eligible maturation receipt and independently evidenced implementation authorization. `no_code_requested` and `blocked` SHALL remain distinct terminal states.

#### Scenario: Model is sufficient but code was not authorized
- **WHEN** the maturation receipt verifies as closed but the task contains no current implementation authorization
- **THEN** admission returns `no_code_requested` and does not weaken the maturation result

#### Scenario: Code is authorized but model is insufficient
- **WHEN** authorization is current but the maturation receipt is blocked, stale, or incomplete
- **THEN** implementation admission returns `blocked`

### Requirement: Development process consumes distribution evidence without owning distribution inventory
DevelopmentProcessFlow SHALL consume typed, current installation or distribution evidence when the task requires it, but SHALL NOT own a fixed satellite count, installation algorithm, or SkillGuard validation procedure.

#### Scenario: Suite inventory changes
- **WHEN** the maintained FlowGuard suite adds or removes a member
- **THEN** DevelopmentProcessFlow relies on the current distribution evidence identity rather than requiring its own inventory update

### Requirement: Direct user choice does not become FlowGuard admission
Development process SHALL preserve direct-user-choice, model-first, and no-code as user execution choices separate from FlowGuard implementation admission. Only the maturation and authorization owners may produce implementation admission, and non-waivable blockers remain authoritative.

#### Scenario: User chooses direct execution
- **WHEN** the user explicitly permits direct execution without complete FlowGuard modeling
- **THEN** the process records direct-user-choice without reporting verified or scoped FlowGuard readiness

#### Scenario: No-code request is current
- **WHEN** the current authorization is discussion-only
- **THEN** implementation admission reports no-code-requested regardless of model sufficiency

### Requirement: Blueprint lifecycle uses the exact affected owner closure
DevelopmentProcessFlow SHALL track implementation inventory, binding, resource, intent, test, topology, projection, and static-closure freshness as distinct identities. Ordinary changes SHALL revalidate only their exact affected owner closure; an explicit whole-blueprint or release obligation SHALL assemble the complete canonical owner set.

#### Scenario: Ordinary implementation changes one blueprint shard
- **WHEN** a changed file invalidates one inventory or binding shard
- **THEN** the process revalidates the affected owner closure without materializing unrelated whole-project layers

#### Scenario: A whole-blueprint claim is explicit
- **WHEN** the task explicitly requires whole-target blueprint qualification
- **THEN** the process assembles the canonical complete owner plan and preserves every child status and gap

### Requirement: Final blueprint release freezes all consumed identities before the unique full gate
Before a release claims current software-blueprint closure, the process SHALL freeze source, observed model authority, implementation inventory, binding report, resource manifest, portable projection, skill projection, toolchain, and validation-plan identities. The unique final full gate SHALL run only after that freeze.

#### Scenario: Peer writes after the freeze
- **WHEN** a peer changes a consumed artifact after the final plan is frozen
- **THEN** affected evidence becomes stale and release publication remains blocked without rolling back the peer change

### Requirement: Blueprint-guided self-maintenance has an explicit ordered lifecycle
DevelopmentProcessFlow SHALL order blueprint-guided FlowGuard maintenance as: freeze current source and observed-authority identities; qualify the provider-neutral self blueprint; classify every architecture-reduction candidate by current software-DNA necessity; accept only equivalence/facade-ready ordinary contractions or complete evidence-authorized `retire_behavior` actions; execute the affected model/code/test/topology/consumer checks; synchronize package and consumer projections; freeze and execute one final full validation; then verify Git, tag, and release identities when publication is authorized.

#### Scenario: Self-blueprint qualification is incomplete
- **WHEN** the current self blueprint has an unresolved required inventory, semantic, code, test, resource, oracle, or lineage row
- **THEN** reduction and release remain blocked for the affected broad claim
- **AND** ordinary unrelated affected-only work is not automatically widened

#### Scenario: A reduction candidate lacks equivalence evidence
- **WHEN** self-audit finds a duplicate-looking path but ArchitectureReduction has not proven equivalence or facade-only delegation
- **THEN** the process records the ordinary contraction candidate as unresolved and does not schedule deletion
- **AND** other evidence-ready candidates MAY proceed through their own affected closures

#### Scenario: An intentional retirement lacks a complete responsibility proof
- **WHEN** self-audit finds a historical behavior that appears unnecessary but any commitment, consumer, negative case, interface, model, code, test, topology, prompt, skill, or release claim lacks a disposition
- **THEN** the process records the retirement candidate as unresolved and does not schedule deletion
- **AND** it does not silently downgrade the candidate into dead-code cleanup

#### Scenario: Final validation passes before peer source changes
- **WHEN** the frozen full gate passes and a peer subsequently changes a consumed source or owner artifact
- **THEN** the affected evidence becomes stale before release
- **AND** peer work is preserved rather than rolled back

### Requirement: Blueprint layers and distribution identities have independent freshness
DevelopmentProcessFlow SHALL track blueprint definition, implementation inventory, intent lineage, semantic evidence, model-code-test bindings, test inventory, resource/oracle closure, source tree, installed package, installed skill projection, repository commit, tag, and release as distinct versioned artifacts. A passing or current identity in one domain SHALL NOT fill another domain.

#### Scenario: Installed package is current but consumer skills are stale
- **WHEN** editable package parity passes and one affected installed skill differs from its frozen source projection
- **THEN** installation synchronization remains incomplete
- **AND** source, Git, tag, and release status are reported separately

#### Scenario: Static blueprint changes after qualification
- **WHEN** a consumed model, semantic source, implementation surface, test node, resource, oracle, intent contribution, or project definition changes
- **THEN** only the exact affected blueprint neighborhood and its consumers become stale
- **AND** unrelated current evidence MAY be reused when its identity remains exact

### Requirement: External interruption has an exact settlement lifecycle
After an externally interrupted validation process tree is confirmed absent, DevelopmentProcessFlow SHALL allow an authorized exact settlement that converts only the named residual leases into immutable interrupted evidence. Partial child results SHALL remain non-reusable unless independently current under their own unchanged producer identities.

#### Scenario: Ordinary residual leases remain after process termination
- **WHEN** exact leases name a dead process and lack an internal cleanup marker because the launcher did not execute its finalizer
- **THEN** settlement SHALL bind the exact plan, owners, process identity, zero-descendant observation, operator reason, and terminal interrupted status
- **AND** it SHALL NOT delete unrelated leases or create passing evidence

### Requirement: Parent and child current pointers have separate owners
Child validations SHALL update only child-scoped current pointers. A parent current pointer SHALL be published only with a terminal parent result that accounts for every planned child as executed, reused, blocked, or not run.

#### Scenario: One child passes before parent completion
- **WHEN** a child result is terminal pass and the parent has unfinished children
- **THEN** the child pointer MAY identify that child result
- **AND** the parent pointer SHALL remain absent or explicitly interrupted

### Requirement: Process freshness includes target-system provider identities
DevelopmentProcessFlow SHALL track the target-system descriptor, every consumed provider input and result, canonical intent inventory, portable behavior bindings, formal coverage edges, coverage execution evidence, compact understanding summary, and static blueprint result as distinct freshness-sensitive artifacts.

#### Scenario: Only one provider input changes
- **WHEN** a source, workflow, trace, resource, or authority provider input changes
- **THEN** the process SHALL stale the exact affected blueprint neighborhood and consumers
- **AND** unrelated provider evidence MAY remain reusable when its identities still match

### Requirement: Final release gate consumes static blueprint and provider freeze
Before the unique final full release validation, the process SHALL freeze the exact target-system descriptor, provider registry and results, observed model revision set, source tree, test and resource inventories, static blueprint result, reduction review, skill projections, toolchain, and owner plan.

#### Scenario: Provider registry changes after the final plan
- **WHEN** a provider identity or capability mapping changes after the final plan is frozen
- **THEN** the final plan and affected evidence SHALL become stale
- **AND** publication SHALL wait for one newly frozen full gate without rolling back peer work

### Requirement: Nested validation evidence paths are bounded without losing identity
DevelopmentProcessFlow SHALL keep deeply nested internal validation work directories within the supported platform path budget. Short internal names SHALL be deterministic projections of the exact owner identity, while the immutable receipt SHALL retain the complete owner, input, run, artifact, and result identities.

#### Scenario: A readable evidence root and long model id feed a shard-safety proof
- **WHEN** the complete nested path would exceed the supported Windows path budget
- **THEN** the proof uses a short deterministic owner hash for its internal directory
- **AND** the terminal receipt still records the full model id and exact evidence identities

### Requirement: Development validates affected owners before one frozen final gate
During implementation, DevelopmentProcessFlow SHALL execute or reuse only exact affected validation owners and SHALL keep unknown impact blocked. After all governed source, OpenSpec, model authority, SkillGuard projection, installation, version, and documentation inputs are frozen, exactly one owner SHALL run the final full gate.

#### Scenario: Focused diagnostics can run independently
- **WHEN** several focused diagnostics have isolated inputs, mutable state, side effects, and execution owners
- **THEN** they MAY run in safe parallel before source freeze
- **AND** later edits SHALL invalidate only evidence that consumes changed identities

#### Scenario: Final gate is interrupted
- **WHEN** the final owner times out, is cancelled, or is interrupted
- **THEN** its evidence SHALL be non-reusable until the entire descendant process tree is confirmed absent
- **AND** no unattended resume or second owner SHALL start from the mutable snapshot

### Requirement: Peer changes are preserved and selectively integrated
DevelopmentProcessFlow SHALL re-read concurrent or unknown-writer changes, preserve them, and stale only affected evidence. It SHALL NOT reset, overwrite, or discard peer work to restore an older green state.

#### Scenario: Peer edits an overlapping governed file
- **WHEN** another agent changes a file in the current integration boundary
- **THEN** the integration owner SHALL re-read and deliberately merge or block that file
- **AND** unrelated work SHALL continue without repository rollback

### Requirement: Release identities close in fixed order
OpenSpec verification, main-spec sync and archive, observed-model acceptance, SkillGuard source/consumer closure, local package and skill installation parity, version and changelog finalization, and cleanup review SHALL finish before the frozen final gate. Commit, immutable patch tag, push, and GitHub Release SHALL follow only a terminal passing gate.

#### Scenario: OpenSpec archive changes governed source
- **WHEN** an earlier full result predates the final archived OpenSpec tree
- **THEN** that result SHALL be stale for release
- **AND** the final gate SHALL consume the archived frozen tree

### Requirement: Continuing release and archive responsibilities have one current process owner
DevelopmentProcessFlow SHALL own the reusable FlowGuard lifecycle obligations for source and requirement freshness, affected validation, peer-write preservation, installation and shadow synchronization, Git/tag/GitHub Release identity, archive invalidation, and final process claims. Version-specific release or cleanup models SHALL NOT remain parallel current owners after their unique protections and implementation surfaces have been dispositioned.

#### Scenario: Historical release model duplicates the current process owner
- **WHEN** a self model describes one completed version's prompt, README, archive, install, tag, or release operation
- **AND** DevelopmentProcessFlow and its exact specialist owners already cover the reusable obligations
- **THEN** the dated model is retired from current authority rather than generalized into a second release path
- **AND** its release-verification or OpenSpec-check implementation surfaces attach to the exact continuing owner as supporting surfaces

#### Scenario: OpenSpec archive lifecycle is consumed
- **WHEN** FlowGuard plans or validates work around an OpenSpec archive
- **THEN** OpenSpec retains native artifact, validation, sync, and archive authority
- **AND** DevelopmentProcessFlow models only the surrounding order, freshness, evidence, install, peer-preservation, and release invalidation without creating a second OpenSpec execution owner

### Requirement: Development order makes path review conditional and current
DevelopmentProcessFlow SHALL run the affected model's lightweight path-quality review after requirement, intent, and owner closure are known and before behavior-sensitive implementation begins. Triggered deep review SHALL close before the corresponding broad implementation claim, while current `single_clear_path` results SHALL proceed without deep ceremony. Implementation or evidence changes SHALL stale and minimally refresh affected results before activation.

#### Scenario: Ordinary affected model has one clear path
- **WHEN** the lightweight result is current and no deep trigger applies
- **THEN** implementation proceeds with the compact result and no candidate expansion

#### Scenario: Implementation changes consumed identities
- **WHEN** code, helper, test, oracle, provider, dependency, or evidence changes after review
- **THEN** the affected result is refreshed before current activation
- **AND** unrelated models are not rerun unless topology requires them

### Requirement: Native validation ownership is bounded and non-duplicative
DevelopmentProcessFlow SHALL partition a broad native validation responsibility into named owners whose declared tests and source inputs correspond to distinct obligations. A native owner SHALL NOT retain tests already owned by another current member merely to make one route appear comprehensive.

#### Scenario: Broad owner overlaps sibling owners
- **WHEN** one native member selects tests that are already mapped to current sibling owners and the duplicate selection adds no independent obligation
- **THEN** the process SHALL contract the broad member to its distinct obligations and keep the sibling tests with their primary owners

#### Scenario: Split preserves all obligations
- **WHEN** a broad native owner is split into focused responsibilities
- **THEN** the compiled contract SHALL still map every required obligation to at least one exact native binding before validation can proceed

### Requirement: Full validation consumes resumable native members
The frozen full-validation owner SHALL invoke native-skill validation through the explicit exact-current resume execution path so successful unchanged member work is composed rather than repeated after a sibling or parent failure.

#### Scenario: Earlier parent failed after native member success
- **WHEN** a prior full-validation parent failed outside an exact-current native member and the member's complete receipt identities remain current
- **THEN** the next frozen parent SHALL reuse that member and execute only missing or stale native members

#### Scenario: Producer source changes before final gate
- **WHEN** the native receipt producer or a declared member input changes after a member receipt was published
- **THEN** the final gate SHALL execute the affected member once before accepting its evidence

### Requirement: Focused repair precedes one frozen full gate
DevelopmentProcessFlow SHALL use focused affected checks while the source is changing and SHALL reserve broad full validation for one stable frozen integration snapshot. A failed broad run SHALL be classified before repair; unchanged successful child evidence SHALL be reused only through exact-current verification.

#### Scenario: Validation-path defect is discovered
- **WHEN** a broad run exposes duplicate ownership, an avoidable timeout, or incomplete receipt binding
- **THEN** the process SHALL repair and focus-check that validation path before starting the next frozen full gate

### Requirement: Release work freezes identity once and validates once
The development process SHALL perform implementation and affected validation first, one consolidated cleanup pass second, version/model/install identity synchronization third, and one final full release gate only after the release tree is frozen.

#### Scenario: A feature is still changing
- **WHEN** source, model, prompt, or OpenSpec work remains in progress
- **THEN** the process SHALL use affected-only checks and SHALL not start the final full release parent

#### Scenario: Release identities are frozen
- **WHEN** source, model authority, OpenSpec, skills, installation, and release tree are current and frozen
- **THEN** plan-only SHALL classify each final owner as execute, reuse_current, or blocked before any producer starts
- **AND** one final parent SHALL execute each stale owner at most once

### Requirement: Current model closure is the release owner
The ordinary FlowGuard development and release process SHALL close the current
model, its code/test/resource/intent/interface bindings, affected impact, and
current executable evidence in the native project directory. A target-generation
step is not a lifecycle phase and SHALL not be used as a release or readiness
criterion.

#### Scenario: User requests ordinary modeling or maintenance
- **WHEN** a target is being modeled, changed, audited, or released
- **THEN** the process SHALL use the native blueprint, affected validation, and
  evidence-currentness routes
- **AND** it SHALL report the deepest proven layer and first remaining gap
- **AND** it SHALL not create a second target authority or generated target

### Requirement: Internal process modes have exact route edges
DevelopmentProcessFlow SHALL expose exact conditional reference edges for its
plan-detailing and agent-workflow internal modes.

#### Scenario: Rough plan needs detailing
- **WHEN** a rough or underspecified plan requires structured rows
- **THEN** the plan-detailing protocol SHALL be the named on-demand owner

#### Scenario: Multi-skill operation needs rehearsal
- **WHEN** a multi-skill, tool, plugin, or external-side-effect operation needs
  workflow rehearsal
- **THEN** the agent-workflow protocol SHALL be the named on-demand owner
