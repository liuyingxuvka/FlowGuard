## ADDED Requirements

### Requirement: Project mesh snapshot closes all reachable model relations
ModelMesh SHALL persist a content-addressed project snapshot whose model
members and typed relations are reachable from declared roots. It SHALL report
orphan, unknown, stale, historical-only, and unresolved members without
promoting them into current authority.

#### Scenario: Candidate replaces a child and changes a sibling dependency
- **WHEN** a revision replaces one child model and changes a relation consumed by a sibling
- **THEN** ModelMesh includes the parent, changed child, affected sibling, relation, and required reattachment evidence in one affected closure

#### Scenario: Historical model remains in storage
- **WHEN** a historical model is preserved but is not a member of the observed-head snapshot
- **THEN** ModelMesh keeps its historical disposition visible and excludes it from current-system coverage
