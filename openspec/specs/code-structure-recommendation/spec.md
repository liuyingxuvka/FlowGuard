# code-structure-recommendation Specification

## Purpose
TBD - created by archiving change add-code-structure-recommendation. Update Purpose after archive.
## Requirements
### Requirement: Code structure recommendation is a parallel route
FlowGuard SHALL provide a code structure recommendation route that can be used
when a user or agent wants a recommended implementation structure before
writing production code.

#### Scenario: Direct architecture recommendation
- **WHEN** a user asks for a code structure recommendation for a planned feature
- **THEN** the route produces a recommended implementation structure without
  writing production code

#### Scenario: Optional use from ordinary modeling
- **WHEN** ordinary model-first work does not need implementation structure
  guidance
- **THEN** FlowGuard does not require the code structure recommendation route

### Requirement: Recommendations derive from functional models
Code structure recommendation SHALL use an existing FlowGuard functional model
or create a fit-for-risk functional or hierarchical functional model before
recommending implementation structure.

#### Scenario: Existing model is available
- **WHEN** a current FlowGuard functional model already describes the feature
- **THEN** the recommendation uses that model as its source evidence

#### Scenario: No model exists yet
- **WHEN** no functional model exists and structure recommendation is requested
- **THEN** the route creates or sketches a fit-for-risk functional model before
  recommending the structure

### Requirement: Recommendations include ownership boundaries
Code structure recommendation SHALL identify target modules, orchestration
responsibility, function-block ownership, state ownership, side-effect
ownership, facade or public entrypoint plans, validation boundaries, and
rationale.

#### Scenario: Complete recommendation
- **WHEN** a recommendation is produced
- **THEN** it includes module owners for function blocks, state fields, side
  effects, public entrypoints, and validation evidence

#### Scenario: Avoid mechanical over-splitting
- **WHEN** multiple related FunctionBlocks belong in one cohesive module
- **THEN** the recommendation may group them and records the grouping rationale
