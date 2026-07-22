## ADDED Requirements

### Requirement: TestMesh preserves composite execution identity and completeness
TestMesh SHALL preserve system-definition, request, slice, component, compiled-model, scheduler/bound, truncation, and trace identities through the existing `ProofArtifactRef.artifact_fingerprints` map plus stable case/shard ids, explored-state count, terminal artifacts, and exactly one execution owner for long or background executable-composition checks. New system-specific generic receipt fields SHALL be added only if focused evidence proves the existing fingerprint map cannot represent the identity.

#### Scenario: Background composite run completes
- **WHEN** a background run has a terminal result, exit status, complete stdout/stderr evidence, covered ids, and matching inventory/source identities
- **THEN** TestMesh may expose that current receipt to its parent gate

#### Scenario: Composite run only reports progress
- **WHEN** a PID, log, heartbeat, or explored-state count exists without terminal artifacts
- **THEN** TestMesh reports liveness only and cannot project executable-composition pass

#### Scenario: Exploration is truncated
- **WHEN** the final receipt records an unexplored frontier
- **THEN** TestMesh preserves blocked status and cannot count the selected cases as complete passing evidence
