# development-process-flow Specification

## Purpose
This capability defines how FlowGuard uses one development-process simulator
front door for plan discussion, multi-skill workflow setup, staged edits,
validation, install sync, shadow sync, release evidence, and done claims so
later work cannot reuse stale proof.
DevelopmentProcessFlow deltas can be archived into a main spec.
## Requirements
### Requirement: DevelopmentProcessFlow is the development-process simulator front door
The `model-first-function-flow` Skill SHALL include
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
- **AND** it records the `plan_detailing` simulator mode before delegating to
  `flowguard-plan-detailing-compiler`

#### Scenario: Multi-skill trigger enters simulator
- **WHEN** a task may require several Codex skills, tools, plugins, external
  actions, or skipped-skill consequences
- **THEN** the Codex-facing guidance enters `flowguard-development-process-flow`
  first
- **AND** it records the `agent_workflow` simulator mode before delegating to
  `flowguard-agent-workflow-rehearsal`

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
delegated process modes, post-change scan inputs, evidence freshness, install
sync, shadow sync, release, archive, publish, and final process claims.

#### Scenario: Process simulator helper is consumed
- **WHEN** `review_development_process_simulator()` is used
- **THEN** its evidence MUST be reported under the `development_process_flow`
  route id
- **AND** callers MUST NOT publish `development_process_simulator` as a separate
  direct route starter

#### Scenario: Maintenance scan is a process input
- **WHEN** changed artifacts, stale evidence, skipped routes, open obligations,
  or split/reduction signals are reviewed after work
- **THEN** DevelopmentProcessFlow MUST consume the scan as a post-change owner
  routing input
- **AND** the scan MUST NOT become the final confidence owner

### Requirement: Delegated process mode skills are owner-selected
DevelopmentProcessFlow SHALL select plan-detailing and agent-workflow mode
skills when those detailed reviews are required.

#### Scenario: Plan detailing is delegated
- **WHEN** DevelopmentProcessFlow selects `plan_detailing`
- **THEN** `flowguard-plan-detailing-compiler` MAY produce detailed rows
- **AND** final process confidence remains owned by DevelopmentProcessFlow

#### Scenario: Agent workflow is delegated
- **WHEN** DevelopmentProcessFlow selects `agent_workflow`
- **THEN** `flowguard-agent-workflow-rehearsal` MAY produce workflow evidence
- **AND** the delegated skill MUST NOT be a competing generic first stop

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

### Requirement: DevelopmentProcessFlow consumes spec work packages
DevelopmentProcessFlow SHALL treat provider work packages, reconciliation reports, session snapshots, and receipt fan-out as development-process artifacts without absorbing provider or product behavior authority.

#### Scenario: Work package enters the lifecycle
- **WHEN** a provider work package is selected for implementation or verification
- **THEN** DevelopmentProcessFlow SHALL order provider read, task/obligation reconciliation, begin snapshot, execute-or-reuse checks, post snapshot, native provider verification, synchronization, and archive readiness

#### Scenario: Peer write occurs during the session
- **WHEN** a peer or unknown writer changes a covered canonical input after begin
- **THEN** DevelopmentProcessFlow SHALL preserve the write, stale affected receipts, and derive minimum revalidation rather than roll back the peer

### Requirement: Process closure requires post-snapshot evidence
DevelopmentProcessFlow SHALL reject done, archive, release, or publish confidence based only on provider checkboxes, a pre-run snapshot, or background liveness.

#### Scenario: Session lacks terminal post evidence
- **WHEN** the process has no matching immutable post snapshot and terminal child receipts
- **THEN** the process SHALL remain incomplete even if every provider task is checked

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

