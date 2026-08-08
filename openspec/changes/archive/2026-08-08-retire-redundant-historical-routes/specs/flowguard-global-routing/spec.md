## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Handoff continuity
Route groups SHALL express how SummaryReport findings, typed maintenance obligations, ExistingModelPreflight, FieldLifecycleMesh, Model-Test Alignment, StructureMesh, TestMesh, ModelMesh, DevelopmentProcessFlow, ModelMaturation, Risk Evidence Ledger, and Closure Contract hand off directly to one another.

#### Scenario: Maintenance finding identifies a route owner
- **WHEN** a finding or maintenance obligation names a current route owner
- **THEN** route discovery SHALL provide the minimal typed inputs and next-action path for that owner
- **AND** no retired routing intermediary is inserted

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

## REMOVED Requirements

### Requirement: Global routing preserves existing routes while adding handoff continuation
**Reason**: The SummaryReport-to-MaintenanceScan sequence preserves a redundant intermediary after typed findings already name their current owners.
**Migration**: Send SummaryReport findings and maintenance obligations directly to the named owner route.

### Requirement: Global routing includes model-angle deliberation
**Reason**: Open-ended angle deliberation duplicates concrete TaskCoverageDemand and ModelMaturation gaps.
**Migration**: Record exact missing state, branch, child, boundary, finite-case, binding, or evidence dimensions on the affected owner and send them directly to ModelMaturation.

### Requirement: FlowGuard-managed projects use maintenance scan before broad claims
**Reason**: A mandatory scan intermediary repeats affected-owner propagation already owned by DevelopmentProcessFlow and canonical topology.
**Migration**: Derive the affected current owner set and require each owner's current evidence before broad claims.

### Requirement: ExistingModelPreflight owns angle and similarity consumption
**Reason**: ExistingModelPreflight still owns exact current-owner lookup, but the independent angle and standalone similarity routes are retired.
**Migration**: Consume bounded canonical relation handoffs inside the exact affected owner closure and route concrete depth gaps directly to ModelMaturation.
