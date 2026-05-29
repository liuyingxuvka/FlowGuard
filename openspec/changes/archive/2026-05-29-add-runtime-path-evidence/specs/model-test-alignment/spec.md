## ADDED Requirements

### Requirement: Model-Test Alignment consumes runtime path evidence
Model-Test Alignment SHALL be able to consume runtime node contracts,
observations, and path alignment evidence when a model obligation or code
contract requires proof that real code followed the modeled workflow node.

#### Scenario: Runtime path evidence covers obligation
- **WHEN** a required model obligation declares required runtime node ids
- **AND** current passing runtime observations cover those node ids at the
  external contract boundary
- **THEN** Model-Test Alignment SHALL treat the runtime path evidence as
  supporting the declared obligation

#### Scenario: Runtime path evidence is missing
- **WHEN** a required model obligation declares required runtime node ids
- **AND** no current passing runtime observation covers one of those ids
- **THEN** Model-Test Alignment SHALL report missing runtime path evidence and
  SHALL NOT return green alignment

#### Scenario: Runtime path binding mismatch blocks alignment
- **WHEN** a runtime observation names a code contract or model obligation that
  does not match the aligned obligation/code contract pair
- **THEN** Model-Test Alignment SHALL report a runtime path binding mismatch

#### Scenario: Runtime path evidence remains independent from mesh routes
- **WHEN** Model-Test Alignment consumes runtime path rows
- **THEN** it SHALL NOT invoke ModelMesh, TestMesh, or StructureMesh, and SHALL
  leave parent/child proof decisions to their owning routes
