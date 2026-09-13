## ADDED Requirements

### Requirement: Self-maintenance has a finite persistent completion cycle
Self-maintenance SHALL bind a completion cycle to the repository, objective, and required obligations; it SHALL allow at most one initial producer and one typed repair and SHALL retain terminal results without reopening them for output-path changes.

#### Scenario: Same objective is invoked twice
- **WHEN** a terminal parent result is current and a second invocation uses the same frozen inputs
- **THEN** the second invocation returns the same parent receipt with producer count zero and creates no new run directory

#### Scenario: Third attempt is requested
- **WHEN** an objective has already consumed its initial and one repair attempt
- **THEN** the cycle is blocked and cannot regain budget by changing output, store, or disposition identifiers

### Requirement: Canonical readiness is a complete envelope
The public readiness route SHALL produce and verify one canonical owner plan, native gate results, input identities, and any typed repair link without relying on caller-supplied hashes or a duplicate helper.

#### Scenario: Readiness is planned before execution
- **WHEN** a caller requests readiness with current source and required gates
- **THEN** the route returns a complete deterministic plan without reserving an attempt, launching a heavy producer, or writing a fake receipt

### Requirement: One immutable completion-run manifest binds readiness to full validation
The readiness route SHALL persist one content-addressed completion-run manifest containing the normalized invocation and frozen child semantic plan. The full route SHALL consume that manifest, ignore output-only locations, and block on field-level drift before acquiring a lease, creating a run directory, or starting a producer.

#### Scenario: Only the output directory changes
- **WHEN** the same readiness manifest is supplied to full validation with a different result output directory
- **THEN** the invocation remains compatible and no new completion epoch is created for that output-path change

#### Scenario: A semantic invocation changes
- **WHEN** model jobs, timeout, receipt root, objective, consumer roots, or a child semantic command differs from the manifest
- **THEN** full validation returns a typed field-level manifest mismatch before any lease, run directory, receipt, or producer is created

### Requirement: Self-blueprint validation scripts have exact owners
The self-maintenance mesh SHALL require every checked-in validation script that it executes or audits to resolve to one exact owner in the authoritative software blueprint before formal qualification. A route name, filename convention, aggregate result, or caller-provided owner list SHALL NOT substitute for the explicit mapping.

#### Scenario: A validation script is not mapped
- **WHEN** the self-blueprint inventory contains a checked-in validation script with no exact owner override or model binding
- **THEN** self-maintenance review returns a typed blueprint-owner failure before qualification and the parent cannot claim closure

#### Scenario: The exact owner mapping is present
- **WHEN** every checked-in validation script has one current owner and the owner is included in the model authority and evidence plan
- **THEN** self-maintenance review may proceed to the remaining native, test, and completion gates without producing a duplicate owner

### Requirement: Agent workflow rehearsal is risk-admitted
The DevelopmentProcessFlow simulator SHALL select its internal `agent_workflow`
mode only for an explicit rehearsal request, a cross-owner handoff or shared
write, a post-validation-invalidating write, an agent/route workflow change, or
multiple independent owners with irreversible side effects. The mode SHALL
remain `not_triggered` for ordinary small, read-only, single-owner,
single-tool, targeted-test, or multi-tool work without one of those facts, and
the rehearsal protocol SHALL not be loaded for that work.

#### Scenario: Ordinary multi-tool work has one reversible owner
- **WHEN** a non-trivial task mentions multiple skills/tools or an external-effect label but has one owner and no admitted workflow-risk fact
- **THEN** the simulator selects the owning route or execution-freshness mode, records `agent_workflow` as `not_triggered`, and starts no rehearsal review

#### Scenario: A workflow-risk fact is present
- **WHEN** the task explicitly requests rehearsal or carries a cross-owner/shared-write, post-validation-invalidating, route-change, or multiple-owner irreversible-side-effect fact
- **THEN** the simulator selects the internal `agent_workflow` mode behind DevelopmentProcessFlow and records the exact admission reason

### Requirement: A changed governed source opens a new reviewed completion scope
The self-maintenance mesh SHALL bind a completion cycle to one frozen source
observation as well as the reviewed objective.  If a real merged source or route
contract changes after the objective's finite attempt budget is exhausted, the
owner SHALL record that revision in the reviewed objective and open a new cycle.
Historical aborted ledgers SHALL remain immutable evidence, and output paths,
caches, disposition labels, or retry wording SHALL NOT reset the old cycle.

#### Scenario: Source revision follows an exhausted cycle
- **WHEN** a governed source revision changes after the initial and typed-repair attempts are consumed
- **THEN** the owner records the new revision in the reviewed objective scope
- **AND** readiness derives a new completion-cycle identity
- **AND** the predecessor ledgers remain historical and are not rewritten

#### Scenario: Only execution metadata changes
- **WHEN** only an output directory, cache location, receipt disposition label, or retry wording changes
- **THEN** the existing completion-cycle identity and attempt budget remain unchanged
- **AND** no producer attempt is admitted
