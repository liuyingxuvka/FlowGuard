## ADDED Requirements

### Requirement: Process Evidence Excludes AutoSplit Metrics
DevelopmentProcessFlow SHALL keep process evidence rows focused on evidence
freshness, artifacts, and proof references. Auto-split metrics and split gate
status MUST be represented by AutoSplit/TestMesh route evidence instead.

#### Scenario: Process evidence row is process-focused
- **WHEN** a process validation command is recorded
- **THEN** the `ProcessEvidence` row records the evidence id, kind, status,
  artifacts, versions, verifier artifacts, validation requirements, and proof
  artifact without state-count or auto-split fields

#### Scenario: Split review is required
- **WHEN** state count, test count, duration, or pending work suggests a split
- **THEN** the split review uses AutoSplit route data rather than fields on
  `ProcessEvidence`

## REMOVED Requirements

### Requirement: ProcessEvidence AutoSplit Fields
**Reason**: AutoSplit fields duplicate another route and make every process
evidence row look like a large-model split review.

**Migration**: Create AutoSplit evidence for split review and link its proof
artifact or route report from the process evidence where needed.
