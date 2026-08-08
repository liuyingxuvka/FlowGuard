# code-structure-recommendation Specification

## Purpose
This capability defines FlowGuard's Code Structure Recommendation behavior and the evidence required to use it safely in AI-agent maintenance workflows.
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

### Requirement: Implementation-ready structure is bound to admitted scope
Code Structure Recommendation MAY produce an early model-derived architecture recommendation before implementation admission, but it SHALL call a recommendation implementation-ready only when its task, source model, candidate, coverage universe, and allowed artifact scope match a current DevelopmentProcessFlow admission.

#### Scenario: Early recommendation has no admission
- **WHEN** a structurally valid recommendation has no current matching implementation admission
- **THEN** the report MUST describe it as recommendation-only and MUST NOT present it as permission to edit production code

#### Scenario: Scoped admission cannot expand
- **WHEN** admission permits only a bounded subset with open gaps
- **THEN** the implementation-ready structure MUST stay inside that subset and preserve the unadmitted modules and open gaps

### Requirement: Blueprint structure recommendations cover the exact model-element universe
When a code-structure recommendation supports a software-blueprint claim, it SHALL bind the exact current set and fingerprint of required FunctionBlocks, state, fields, effects, and public entrypoints. Every required element SHALL map to one target owner or a typed unresolved disposition, and the recommendation SHALL emit reverse implementation-coverage obligations for later source audit.

#### Scenario: Nonempty mapping omits one current effect
- **WHEN** a recommendation maps several model elements but omits one effect from the bound current model universe
- **THEN** the recommendation is incomplete for blueprint use

#### Scenario: Model revision changes
- **WHEN** the model-element universe changes after recommendation
- **THEN** the recommendation and its reverse coverage obligations become stale

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

