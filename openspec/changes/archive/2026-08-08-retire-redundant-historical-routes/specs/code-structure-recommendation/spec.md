## ADDED Requirements

### Requirement: Canonical-relation-derived target structure
Code Structure Recommendation SHALL consume bounded canonical relation handoffs when current blueprint, behavior commitment, ownership, or topology evidence establishes shared-kernel, family-variant, symmetric-flow, adapter-only, same-intent, duplicate-boundary, or false-friend structure. The recommendation owner SHALL derive modules, facades, adapters, effect owners, and validation boundaries; the relation carrier SHALL NOT make that decision.

#### Scenario: Shared mechanism relation derives modules
- **WHEN** a current canonical relation establishes shared mechanism or same-intent behavior across exact endpoints
- **THEN** the recommendation identifies the shared owner, variant or directional adapter owners, public facade owner, and validation boundaries
- **AND** it preserves the relation id and source authority as provenance

#### Scenario: Adapter-only or duplicate-boundary relation is present
- **WHEN** a canonical relation identifies adapter-only variance or overlapping ownership
- **THEN** the recommendation binds each endpoint to a concrete target module, facade, adapter, or Architecture Reduction handoff

#### Scenario: False friend blocks a shared module
- **WHEN** a canonical relation records different intent, behavior plane, or false-friend evidence
- **THEN** Code Structure Recommendation MUST NOT derive a shared owner from wording or shape alone

## MODIFIED Requirements

### Requirement: Recommendations include ownership boundaries
Code structure recommendation SHALL identify target modules, orchestration responsibility, function-block ownership, state ownership, side-effect ownership, facade or public entrypoint plans, validation boundaries, rationale, and any canonical relation handoff that materially informs shared-kernel, adapter, duplicate-boundary, or separate-owner decisions.

#### Scenario: Complete recommendation
- **WHEN** a recommendation is produced
- **THEN** it includes module owners for function blocks, state fields, side effects, public entrypoints, and validation evidence

#### Scenario: Avoid mechanical over-splitting
- **WHEN** multiple related FunctionBlocks belong in one cohesive module
- **THEN** the recommendation may group them and records the grouping rationale

#### Scenario: Canonical relation informs shared modules
- **WHEN** a recommendation derives shared-kernel or adapter ownership from a current canonical relation
- **THEN** it MUST record the relation id, exact endpoints, source authority, and currentness
- **AND** it MUST materialize the relation into concrete code-owner and validation-boundary decisions rather than repeat scalar relation fields

#### Scenario: Similarity handoff drives shared modules
- **WHEN** a caller supplies a retired similarity handoff as authority for shared modules
- **THEN** Code Structure Recommendation MUST reject that retired authority
- **AND** it MAY derive shared modules only from exact current ownership and a bounded canonical relation handoff

## REMOVED Requirements

### Requirement: Similarity-derived target structure
**Reason**: The standalone Model Similarity review and maintenance groups are retired.
**Migration**: Derive target structure only from exact current owners plus bounded canonical relation handoffs, with Code Structure Recommendation retaining decision ownership.
