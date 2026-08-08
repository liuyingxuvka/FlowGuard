## ADDED Requirements

### Requirement: Binding blocker lookup is indexed once
Model-test alignment SHALL read the complete blocker finding sequence once to build exact lookup indexes by model obligation, code contract, and test evidence. Each binding row SHALL derive its blocker codes from those indexes. The indexed result SHALL preserve the same unique sorted blocker codes that a complete finding scan would produce.

#### Scenario: Many binding rows share one finding inventory
- **WHEN** one alignment review contains many model/code/test binding rows and blocker findings
- **THEN** every blocker finding SHALL be admitted to the exact lookup indexes once
- **AND** producing additional binding rows SHALL NOT rescan the complete finding sequence

#### Scenario: One finding identifies several binding dimensions
- **WHEN** a blocker finding identifies an obligation, code contract, or evidence item used by a binding row
- **THEN** that row SHALL contain the finding code exactly once in sorted order
- **AND** indexing SHALL NOT downgrade, discard, or duplicate the blocker

### Requirement: Supporting test provenance does not imply exact behavior coverage
A test node that is current and required but lacks one exact behavior/case/oracle/dimension edge SHALL remain `supporting`. Model-level test-file patterns MAY establish regression provenance, but SHALL NOT assign behavior owners to every test node in the file. Exact behavior coverage and native execution ownership SHALL continue through their dedicated typed edges.

#### Scenario: One test file appears in several model regression inputs
- **WHEN** a required test node belongs to a file referenced by multiple model owners but has no exact behavior coverage edge
- **THEN** the node SHALL remain supporting with no invented behavior owner
- **AND** the independent test inventory SHALL still preserve its exact source identity and required disposition
## ADDED Requirements

### Requirement: Supporting oracle implementation does not self-certify behavior
A supporting implementation binding MAY reference an oracle whose physical source is that same supporting surface only when the binding relation is explicitly `supports`, delegates to one exact current behavior owner, and creates no independent behavior contract. The inherited oracle reference SHALL provide owner traceability only. Every direct `implements` binding SHALL continue to require semantic and oracle sources independent from its implementation source.

#### Scenario: A native runner implements the oracle it delegates
- **WHEN** a current native runner is retained in the implementation denominator as a supporting surface and is also the physical source of the exact oracle used by its owner behavior
- **THEN** its typed supporting binding SHALL remain traceable without reporting oracle self-certification
- **AND** the runner SHALL NOT become an independent behavior block or relax source independence for the owner's direct implementation binding
