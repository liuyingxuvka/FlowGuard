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

### Requirement: Code structure consumes field owners
Code Structure Recommendation SHALL consume field lifecycle reader, writer,
owner, public-entrypoint, and validation-boundary rows when deriving target
modules or facades.

#### Scenario: Field writer owner is missing
- **WHEN** a behavior-bearing field has writes in scope
- **AND** no target code owner or validation boundary owns those writes
- **THEN** Code Structure Recommendation MUST report an owner gap instead of
  recommending implementation structure as complete

#### Scenario: Field facade is required
- **WHEN** old field access must be delegated to a new field or new path for
  public compatibility
- **THEN** the target structure recommendation MUST expose the facade or
  adapter boundary and route public-entrypoint parity to StructureMesh when
  required

### Requirement: Similarity-derived target structure
Code Structure Recommendation SHALL be able to consume shared-kernel,
family-variant, symmetric-flow, and adapter-only model-similarity relations
when deriving target modules, facades, variant adapters, effect owners, and
validation boundaries.

#### Scenario: Shared kernel relation derives modules
- **WHEN** a code-structure recommendation cites a shared-kernel
  model-similarity relation
- **THEN** the recommendation identifies the shared kernel owner, variant or
  directional adapter owners, public facade owner, and validation boundaries

#### Scenario: Similarity maintenance group cites code obligation
- **WHEN** a code-structure recommendation uses a similarity maintenance group
  to derive shared-kernel or adapter ownership
- **THEN** the recommendation records the maintenance group ids and code
  obligation ids that named the shared kernel, adapter owners, and code paths

#### Scenario: False friend blocks shared module recommendation
- **WHEN** a model-similarity relation is classified as false friend
- **THEN** Code Structure Recommendation does not use that relation to derive a
  shared module without a separate manual-review route

