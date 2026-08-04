## ADDED Requirements

### Requirement: Blueprint-guided self-maintenance has an explicit ordered lifecycle
DevelopmentProcessFlow SHALL order blueprint-guided FlowGuard maintenance as: freeze current source and observed authority identities; qualify the project-neutral self-blueprint; audit current architecture-reduction candidates; accept only evidence-ready contractions; execute the affected model/code/test checks; synchronize package and consumer projections; freeze and execute one final full validation; then verify Git, tag, and release identities when publication is authorized.

#### Scenario: Self-blueprint qualification is incomplete
- **WHEN** the current self-blueprint has an unresolved required inventory, semantic, code, test, resource, oracle, or lineage row
- **THEN** reduction and release remain blocked for the affected broad claim
- **AND** ordinary unrelated affected-only work is not automatically widened

#### Scenario: A reduction candidate lacks equivalence evidence
- **WHEN** self-audit finds a duplicate-looking path but ArchitectureReduction has not proven equivalence or facade-only delegation
- **THEN** the process records the candidate as unresolved and does not schedule deletion
- **AND** other evidence-ready candidates MAY proceed through their own affected closures

#### Scenario: Final validation passes before peer source changes
- **WHEN** the frozen full gate passes and a peer subsequently changes a consumed source or owner artifact
- **THEN** the affected evidence becomes stale before release
- **AND** peer work is preserved rather than rolled back

### Requirement: Blueprint layers and distribution identities have independent freshness
DevelopmentProcessFlow SHALL track blueprint definition, implementation inventory, intent lineage, semantic evidence, model-code-test bindings, test inventory, resource/oracle closure, optional reconstruction receipt, source tree, installed package, installed skill projection, repository commit, tag, and release as distinct versioned artifacts. A passing or current identity in one domain SHALL NOT fill another domain.

#### Scenario: Installed package is current but consumer skills are stale
- **WHEN** editable package parity passes and one affected installed skill differs from its frozen source projection
- **THEN** installation synchronization remains incomplete
- **AND** source, Git, tag, and release status are reported separately

#### Scenario: Static blueprint changes after qualification
- **WHEN** a consumed model, semantic source, implementation surface, test node, resource, oracle, intent contribution, or project definition changes
- **THEN** only the exact affected blueprint neighborhood and its consumers become stale
- **AND** unrelated current evidence MAY be reused when its identity remains exact

### Requirement: Reconstruction remains optional and never starts from lifecycle continuation
Inventory, audit, qualification, ordinary regression, architecture reduction, installation, final validation, archive, and release steps SHALL leave empirical reconstruction `not_run` unless the user explicitly requests reconstruction as a separate action.

#### Scenario: Release requires static blueprint evidence only
- **WHEN** the declared release gate requires a complete static blueprint but no empirical reconstruction claim
- **THEN** a current static qualification with reconstruction `not_run` MAY satisfy that blueprint child
- **AND** the process does not add a reconstruction producer

#### Scenario: User explicitly requests reconstruction
- **WHEN** the user separately authorizes an empirical reconstruction exercise with an exact blueprint fingerprint and boundary
- **THEN** DevelopmentProcessFlow records a separate owner, environment, evidence, and result lifecycle
- **AND** the reconstruction result cannot replace static closure or ordinary validation evidence
