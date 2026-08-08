## ADDED Requirements

### Requirement: Maturation closes current model path quality
ModelMaturation SHALL require one current model-path-quality result for every new or materially changed model in its affected coverage universe. Missing, stale, or unresolved required rows SHALL remain explicit maturation gaps, while a current `single_clear_path` result SHALL satisfy ordinary path review without triggering deep work.

#### Scenario: Required model has current path quality
- **WHEN** every affected model has a current bounded conclusion and no unresolved row for the claimed boundary
- **THEN** maturation MAY consume those results with its other owner contributions

#### Scenario: Candidate omits a required model result
- **WHEN** the independent affected model denominator includes a model with no current path-quality result
- **THEN** maturation retains the missing row and SHALL NOT report full coverage
