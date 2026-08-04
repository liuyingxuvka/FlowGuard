# flowguard-self-maintenance-mesh Specification

## Purpose
This capability defines how FlowGuard uses its own route, API, field, test, install, shadow, and git evidence to maintain FlowGuard itself without overclaiming completion.
## Requirements
### Requirement: Self-maintenance parent mesh
FlowGuard SHALL provide a parent self-maintenance model that coordinates route graph completeness, field layering, structure governance, validation evidence, install/shadow sync, and final closure evidence without replacing the specialist route checks.

#### Scenario: Child route evidence is current
- **WHEN** the self-maintenance mesh receives current child closure reports for route graph, fields, structure, validation, and closure
- **THEN** it SHALL allow a scoped self-maintenance confidence claim that names the covered routes and evidence artifacts

#### Scenario: Child route evidence is stale
- **WHEN** any child route report is stale, skipped, blocked, partial, or missing
- **THEN** the self-maintenance mesh SHALL downgrade the broad claim and emit the owning next action

### Requirement: Route graph completeness child
The self-maintenance mesh SHALL include a child check that compares installed route capabilities with AI-facing route discovery groups.

#### Scenario: Installed route is not discoverable
- **WHEN** an installed FlowGuard route has templates, helpers, skills, or docs but no compact route discovery group
- **THEN** the child check SHALL report a route graph gap with the expected group id and route owner

### Requirement: Field layering child
The self-maintenance mesh SHALL include a child check that classifies fields as core, route-owned, shared evidence, metadata/display, compatibility, removed, blocked, delegated, preserved, or out-of-scope.

#### Scenario: Compatibility field lacks disposition
- **WHEN** a field is old, replaced, aliased, fallback-like, or compatibility-like
- **THEN** the field layering child SHALL require an explicit disposition before broad confidence

### Requirement: AI journey simulation
The self-maintenance mesh SHALL simulate at least one AI maintenance journey from user intent to route selection, route-owned evidence, validation, and closure boundary.

#### Scenario: AI entry sees route-first path
- **WHEN** an AI needs to maintain fields, structure, tests, or route handoffs
- **THEN** the simulated journey SHALL reach a compact route profile before exposing the flat public helper surface

### Requirement: Self-maintenance default plan folds common fields
FlowGuard SHALL provide a public helper that builds the common
`SelfMaintenancePlan` from route profiles, public route API groups, AI entry
profiles, and field layer defaults while preserving explicit advanced plan
construction.

#### Scenario: Default plan is reviewable
- **WHEN** a caller provides only a plan id and current child closure reports
- **THEN** the helper returns a `SelfMaintenancePlan` that
  `review_flowguard_self_maintenance(...)` can validate without requiring the
  caller to manually fill the route graph fields

#### Scenario: Full fields remain available
- **WHEN** a specialist route needs to override route profiles, AI profiles,
  field layers, or API group ids
- **THEN** direct `SelfMaintenancePlan` construction remains supported

### Requirement: Self-maintenance scans runner entry evidence
The self-maintenance mesh SHALL include current self-model runner entry evidence
when it reviews fallback, direct-entry, compatibility, and prompt cleanup risk.

#### Scenario: Runner still uses direct Explorer
- **WHEN** a current `.flowguard` runner script calls `Explorer(...)` directly
- **THEN** self-maintenance evidence MUST classify the runner as a cleanup gap
  instead of treating the model as fully current

#### Scenario: Runner uses formal helper
- **WHEN** a current `.flowguard` runner script delegates through the formal
  workflow-suite helper and adoption audit reports no current direct Explorer
  runner warnings
- **THEN** self-maintenance evidence MAY treat the runner entry path as current
  for this maintenance claim

### Requirement: Parent Closure Consumes Real Child Receipts
Full self-maintenance closure SHALL require current receipts for suite inventory, SkillGuard deep contracts, behavior commitments, route topology, model-test alignment, TestMesh, model regression, installation/version state, and documentation/distribution gates. The parent model and runner MUST load and verify those receipts and MUST NOT manufacture passing child reports.

#### Scenario: SkillGuard child receipt is missing
- **WHEN** every child except SkillGuard deep certification has a current passing receipt
- **THEN** full self-maintenance remains blocked and identifies the missing child

#### Scenario: Runner constructs pass in memory
- **WHEN** a runner attempts to provide a child status without a verifiable receipt id and fingerprint
- **THEN** the parent rejects the child report as unbound evidence

### Requirement: Synthetic Evidence Transitions Are Forbidden
Self-maintenance state transitions MUST NOT set multiple evidence domains to current/pass without independently consumed receipts for each domain. Evidence booleans, if retained as view fields, SHALL be derived from verified receipt state.

#### Scenario: One action sets all evidence flags
- **WHEN** a transition attempts to set suite, ledger, DCAR, TestMesh, model-miss, and route evidence to true together without child receipts
- **THEN** model conformance or contract validation fails the transition

### Requirement: Full Governance Uses Exact Status Semantics
For full self-governance, every required child MUST be current and exact `pass`. `pass_with_gaps`, `scoped`, `stale`, `skipped`, `not_run`, `progress_only`, and `blocked` MUST remain visible and MUST NOT satisfy the parent full claim.

#### Scenario: Child passes with gaps
- **WHEN** the topology child reports `pass_with_gaps`
- **THEN** the parent reports an open topology gap and cannot emit full pass

#### Scenario: Scoped formal case meets expected boolean
- **WHEN** a scoped model case reports non-failing status but the parent claim is full
- **THEN** the formal summary does not promote it to full observed success

### Requirement: Three Layer Governance Status
Self-governance output SHALL separately report `engine_and_core_tests`, `skill_contract_governance`, and `full_self_governance`, with evidence, blockers, skipped checks, residual risk, and claim boundary for each layer.

#### Scenario: Engine passes and contracts fail
- **WHEN** core tests pass but any required skill deep contract fails
- **THEN** engine status is pass, skill contract governance is fail, and full self-governance is blocked

### Requirement: FlowGuard self maintenance exercises the full understanding path
The self-maintenance mesh SHALL include executable child gates for task-demand derivation, model maturation, receipt verification, implementation admission, risk confidence, and final integrity closure using the same public state names and identities as runtime.

#### Scenario: Self model uses a drifted terminal state name
- **WHEN** a self-model state or transition does not match the current public runtime contract
- **THEN** self-maintenance validation fails before release confidence is granted

### Requirement: A FlowGuard release proves the exact whole-system understanding path
Before a FlowGuard release claims current self-understanding, self-maintenance SHALL execute the exact current task through task-fact demand, one resolution per demanded owner, maturation, canonical receipt publication, independent receipt verification, implementation admission, risk review, and closure. Every stage SHALL consume the same current task and model-system identity.

#### Scenario: One stage uses a previous model-system identity
- **WHEN** any self-maintenance stage consumes an identity from an earlier revision
- **THEN** the whole-system self-understanding claim is stale and release closure is blocked

#### Scenario: User authorization is present but maturation was not run
- **WHEN** release work is authorized but the exact current self-understanding task lacks verified maturation
- **THEN** self-maintenance reports understanding not-run and does not claim ready

### Requirement: Parent evidence remains publishable from deep Windows worktrees
The evidence lifecycle SHALL read and atomically publish content-addressed evidence objects when the resolved Windows path exceeds the legacy path limit. A passing child set without a publishable parent result SHALL NOT support a completion claim.

#### Scenario: Model children pass under a deep worktree
- **WHEN** selected model runners pass but the parent evidence object resolves beyond the legacy Windows path limit
- **THEN** the parent result and its object are stored and independently readable without shortening or changing the governed worktree identity

### Requirement: FlowGuard self-qualification uses the public project-neutral path
FlowGuard self-maintenance SHALL build and qualify its self-blueprint through the same target-system compiler, provider registry and snapshot, project-neutral builder, Python observation providers, test inventory, alignment, and qualification contracts available to other targets. The FlowGuard self definition SHALL be a thin bounded software preset and SHALL NOT duplicate generic assembly, semantic, provider, or evidence authority.

#### Scenario: Generic compiler behavior changes
- **WHEN** the target-system compiler, project-neutral builder, or a consumed schema changes
- **THEN** FlowGuard self-qualification exercises that exact current implementation and schema
- **AND** a FlowGuard-only alternate builder cannot keep the self check green

#### Scenario: FlowGuard-specific preset supplies repository boundaries
- **WHEN** self-maintenance loads FlowGuard's checked-in blueprint definition
- **THEN** the preset supplies only target-specific boundaries, provider selections, owner mappings, and declared resources
- **AND** generic qualification remains owned by the public provider-neutral path

#### Scenario: A non-code fixture follows the same core path
- **WHEN** regression supplies a bounded workflow or mixed target with equivalent current provider capabilities
- **THEN** both targets are compiled through the same target-system API and checker contracts
- **AND** target identity and provider kinds change only the declared target data
### Requirement: Self-maintenance exposes honest depth and safe contraction inputs
The self-maintenance parent SHALL consume current child evidence for independent inventory, intent lineage, semantics, model-code-test bindings, resources and oracles, static qualification, affected-only behavior, and optional empirical reconstruction status. It SHALL publish exact gaps and provide ArchitectureReduction only current evidence-bound candidates.

#### Scenario: One FlowGuard test row is orphaned
- **WHEN** the self test inventory contains a required executable node or obligation without a complete current binding
- **THEN** the parent reports the exact orphan and its owner
- **AND** broad self regression success does not close static blueprint qualification

#### Scenario: Static self-blueprint passes without reconstruction
- **WHEN** every required static child passes and no reconstruction was requested
- **THEN** self-maintenance reports static self-blueprint complete and reconstruction `not_run`
- **AND** it does not claim empirical rebuilding

#### Scenario: Self-audit finds an uncertain duplicate path
- **WHEN** the blueprint exposes a possible duplicate helper, adapter, branch, validation route, or facade without current equivalence evidence
- **THEN** the parent emits a typed ArchitectureReduction candidate with unresolved proof status
- **AND** it does not edit or remove the path automatically

### Requirement: Self-maintenance release consumes behavior and reduction children
FlowGuard self-maintenance release closure SHALL consume independent terminal children for behavior-block blueprint qualification and fingerprinted ArchitectureReduction self-review. Neither child SHALL be inferred from generic model regression or narrative OpenSpec completion.

#### Scenario: Static owner map passes without behavior closure
- **WHEN** FlowGuard's owner-level blueprint passes but behavior-block qualification is incomplete
- **THEN** full self-understanding and release closure SHALL remain blocked

#### Scenario: Reduction review is missing
- **WHEN** all other self-maintenance children pass but the current self-reduction report is absent or stale
- **THEN** release closure SHALL identify the missing reduction child
