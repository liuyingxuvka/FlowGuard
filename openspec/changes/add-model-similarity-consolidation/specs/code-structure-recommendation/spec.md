## ADDED Requirements

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
