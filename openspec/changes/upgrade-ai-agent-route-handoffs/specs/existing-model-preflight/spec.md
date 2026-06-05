## ADDED Requirements

### Requirement: Project inventory can build existing-model preflight input
FlowGuard SHALL provide a project inventory helper that creates an
`ExistingModelPreflight` object from a project root, task summary, optional
changed paths, and optional downstream routes.

#### Scenario: Existing model files are found
- **WHEN** the project root contains FlowGuard model files or adoption records
  that mention model ownership
- **THEN** the helper SHALL return relevant `ModelContextHit` rows and record
  the searched paths

#### Scenario: No model is found
- **WHEN** the project root has no relevant FlowGuard model inventory
- **THEN** the helper SHALL return the existing `no_model_found` reuse decision
  with a visible no-model-found reason rather than claiming model ownership

#### Scenario: Helper output remains reviewable
- **WHEN** the helper returns an `ExistingModelPreflight`
- **THEN** callers SHALL be able to pass it to
  `review_existing_model_preflight(...)` without converting to a separate
  schema
