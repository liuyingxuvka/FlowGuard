## ADDED Requirements

### Requirement: Parent mesh consumes child runtime path evidence
Hierarchical ModelMesh SHALL allow parent models to consume current child
runtime path evidence ids as part of child reattachment and whole-flow
confidence without inlining every child node.

#### Scenario: Parent consumes current child path evidence
- **WHEN** a child model provides current runtime path evidence for the child
  handoff consumed by a parent
- **AND** the child evidence id matches the parent reattachment contract
- **THEN** the parent mesh SHALL accept that child path evidence for the
  reattachment decision

#### Scenario: Parent consumes stale child path evidence
- **WHEN** a parent consumes a child runtime path evidence id that is stale or
  no longer matches the child boundary
- **THEN** the parent mesh SHALL block parent confidence with a stale child
  runtime path finding

#### Scenario: Child path output has no consumer
- **WHEN** a child runtime path emits an output required by the parent workflow
- **AND** no parent, sibling, terminal, or out-of-scope disposition consumes it
- **THEN** the mesh closure review SHALL block whole-flow confidence
