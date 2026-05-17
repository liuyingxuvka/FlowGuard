## MODIFIED Requirements

### Requirement: model-first-function-flow exposes code structure recommendation
The `model-first-function-flow` Skill SHALL expose `code_structure_recommendation`
as a parallel route for direct code architecture recommendations and
model-derived implementation structure planning.

#### Scenario: Route is available
- **WHEN** the Skill route map is read
- **THEN** `code_structure_recommendation` is listed as a route beside
  `core_modeling`, `model_mesh_maintenance`, `test_mesh_maintenance`, and
  `structure_mesh_maintenance`

#### Scenario: Core modeling remains lightweight
- **WHEN** ordinary core modeling does not need implementation structure
  planning
- **THEN** the Skill does not require the code structure recommendation route
