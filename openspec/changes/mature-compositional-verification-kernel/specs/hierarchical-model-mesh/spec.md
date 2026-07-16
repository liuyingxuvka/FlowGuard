## ADDED Requirements

### Requirement: Portable Mesh Semantic Binding
When a hierarchical mesh makes a portable interchange or cross-process verification claim, the system SHALL bind each active child model and parent refinement edge to current portable model identities and explicit refinement bindings.

#### Scenario: Portable mesh evidence is complete
- **WHEN** every active parent and child node has a current portable identity and every refinement edge has a passing binding receipt
- **THEN** the mesh may support the portable semantic closure claim

#### Scenario: Descriptive edge is insufficient
- **WHEN** a mesh edge has ownership metadata but no executable refinement binding
- **THEN** portable semantic closure remains blocked

