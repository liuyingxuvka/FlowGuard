## MODIFIED Requirements

### Requirement: Recommendations include ownership boundaries
Code structure recommendation SHALL identify target modules, orchestration
responsibility, function-block ownership, state ownership, side-effect
ownership, facade or public entrypoint plans, validation boundaries, rationale,
and any model-similarity maintenance handoff that drives shared-kernel or
adapter ownership.

#### Scenario: Complete recommendation
- **WHEN** a recommendation is produced
- **THEN** it includes module owners for function blocks, state fields, side
  effects, public entrypoints, and validation evidence

#### Scenario: Avoid mechanical over-splitting
- **WHEN** multiple related FunctionBlocks belong in one cohesive module
- **THEN** the recommendation may group them and records the grouping rationale

#### Scenario: Similarity handoff drives shared modules
- **WHEN** a recommendation derives shared-kernel or adapter ownership from
  model-similarity review
- **THEN** it MUST consume a `SimilarityHandoff` that names the relevant code
  obligations instead of repeated scalar similarity id fields
