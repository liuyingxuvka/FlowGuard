## ADDED Requirements

### Requirement: Task prediction is frozen before official replay
FlowGuard SHALL provide an immutable task-local prediction snapshot that binds
one task, model version and fingerprint, scenario, expected trace, falsifier,
and observation boundary before the official replay observes production code.

#### Scenario: Prediction is replayed
- **WHEN** a caller passes a valid prediction snapshot to the official
  prediction replay helper
- **THEN** the resulting conformance report MUST bind the prediction id,
  prediction fingerprint, and model fingerprint
- **AND** the report MUST compare the snapshot's expected trace with the
  production adapter observations

#### Scenario: Prediction identity is changed
- **WHEN** prediction content changes
- **THEN** its deterministic fingerprint MUST change
- **AND** an earlier report MUST NOT represent the changed prediction

### Requirement: Task model revisions preserve base and candidate identities
FlowGuard SHALL provide a task-local model revision record that preserves one
base model version and one distinct candidate model version without rewriting
either artifact or modifying FlowGuard's own rules.

#### Scenario: Candidate is proposed
- **WHEN** a prediction mismatch motivates a model change
- **THEN** the revision MUST record the base identity, candidate identity,
  mismatch, changed model elements, and required replay ids
- **AND** the base MUST remain the active model while the revision is proposed

#### Scenario: Candidate passes all required replay
- **WHEN** every replay id required by the proposed revision is supplied as
  current passing `TaskReplayEvidence` from a real conformance report bound to
  the same task, model, and candidate-model fingerprint
- **THEN** the revision MAY transition to accepted
- **AND** the candidate model MUST become the active model identity

#### Scenario: Candidate lacks required replay
- **WHEN** one or more required replay ids are absent, status-only, failing, or
  bound to another task, model, or model fingerprint
- **THEN** FlowGuard MUST reject the acceptance transition
- **AND** the base model MUST remain active

#### Scenario: Candidate is rejected
- **WHEN** a proposed candidate is explicitly rejected with a reason
- **THEN** the revision MUST retain the base model as active
- **AND** the rejected candidate identity and reason MUST remain visible

#### Scenario: Accepted candidate is rolled back
- **WHEN** an accepted candidate is explicitly rolled back with a reason
- **THEN** the revision MUST restore the base model identity as active
- **AND** preserve the candidate identity and rollback reason

### Requirement: Task-local iteration does not self-modify the Guard
Prediction and revision helpers SHALL be pure task-artifact governance and
SHALL NOT write model files, modify FlowGuard rules, lower validation
thresholds, or promote task experience into a permanent default.

#### Scenario: Revision transition runs
- **WHEN** a caller accepts, rejects, or rolls back a task revision
- **THEN** the helper MUST return a new immutable record
- **AND** MUST NOT perform filesystem writes or mutate the base record
