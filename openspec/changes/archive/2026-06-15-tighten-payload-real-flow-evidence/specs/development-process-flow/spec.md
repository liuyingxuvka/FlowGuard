## ADDED Requirements

### Requirement: Payload evidence freshness follows real surfaces
DevelopmentProcessFlow SHALL treat real payload surfaces, payload schemas,
fixtures, import/export/save/load/generate behavior, AI work-package structure,
validation prompts, and proof artifacts as freshness-sensitive process
artifacts.

#### Scenario: Real payload surface changes after evidence
- **WHEN** the real payload surface, payload schema, fixture, generated output,
  work-package structure, or validation prompt changes after payload evidence
  is produced
- **THEN** DevelopmentProcessFlow MUST mark the old payload evidence stale and
  recommend rerunning Model-Test Alignment or TestMesh payload validation
