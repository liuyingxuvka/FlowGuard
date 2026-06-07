## ADDED Requirements

### Requirement: Existing model preflight consumes model angle deliberation
Existing Model Preflight SHALL consume model-angle deliberation rows when a
task requires open-ended review of whether one model is enough.

#### Scenario: Required deliberation is missing
- **WHEN** a full preflight marks model-angle review as required
- **AND** no deliberation rows are supplied
- **THEN** preflight MUST report a blocking model-angle gap before broad confidence

#### Scenario: Deliberation row has unresolved gap
- **WHEN** a deliberation row reports an unresolved required angle, missing disposition rationale, or human-review question
- **THEN** preflight MUST keep that gap visible and route downstream work without claiming the current model is sufficient

#### Scenario: Deliberation supports continuation
- **WHEN** each required model angle is reused, extended, created, scoped, deferred, or sent to human review with sufficient rationale
- **THEN** preflight MAY continue with scoped or full confidence according to the row decisions and evidence
