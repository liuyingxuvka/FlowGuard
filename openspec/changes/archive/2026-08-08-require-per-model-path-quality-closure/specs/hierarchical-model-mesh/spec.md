## ADDED Requirements

### Requirement: ModelMesh propagates compact path-quality freshness
ModelMesh SHALL propagate the current path-quality subject, conclusion, unresolved state, and detailed-evidence fingerprint across affected parent/child and sibling relations. It SHALL reopen only topology-required neighbors and SHALL NOT copy deep candidate bodies into every mesh node or independently rejudge single-model path quality.

#### Scenario: Child model path changes
- **WHEN** a child's path-quality subject or consumed interface identity changes
- **THEN** every parent or sibling whose contract consumes that identity becomes stale until its affected handoff is reviewed

#### Scenario: Child deep details are not required
- **WHEN** a parent claim needs only the child's current compact result
- **THEN** the mesh carries the summary and fingerprint without loading or duplicating deep details
