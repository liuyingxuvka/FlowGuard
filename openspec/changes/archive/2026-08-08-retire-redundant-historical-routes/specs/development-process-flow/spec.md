## MODIFIED Requirements

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
