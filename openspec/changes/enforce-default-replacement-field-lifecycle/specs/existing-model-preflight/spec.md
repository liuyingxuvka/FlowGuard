## ADDED Requirements

### Requirement: Existing model preflight includes field ownership
Existing model preflight SHALL include field lifecycle model ownership and
field projection status when a task changes fields, schemas, flags, modes,
payloads, persisted data, prompts, or configuration surfaces.

#### Scenario: Existing field model is reused
- **WHEN** a task touches fields already covered by a field lifecycle mesh
- **THEN** preflight MUST report the existing field group owner and reuse or
  extend decision before adding a parallel field model

#### Scenario: No field model exists
- **WHEN** a task changes behavior-bearing fields and no field lifecycle mesh
  covers them
- **THEN** preflight MUST report a field model gap and route the work to create
  or extend field lifecycle coverage
