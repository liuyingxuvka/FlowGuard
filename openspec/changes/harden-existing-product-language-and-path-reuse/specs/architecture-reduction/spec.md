## ADDED Requirements

### Requirement: Architecture Reduction accounts the complete same-intent candidate inventory
FlowGuard SHALL require an Architecture Reduction plan driven by existing-model or model-similarity evidence to declare the complete expected set of duplicate, same-workflow, adapter, alias, wrapper, helper, fallback, and facade candidates for each in-scope stable business intent.

#### Scenario: Expected reduction candidate is omitted
- **WHEN** Existing Model Preflight or Model Similarity identifies an in-scope same-intent surface but no reduction candidate or explicit keep/scoped disposition represents it
- **THEN** Architecture Reduction SHALL report the expected candidate as missing
- **AND** it SHALL NOT treat the caller-selected candidate subset as a complete contraction review

#### Scenario: Complete candidate inventory has dispositions
- **WHEN** every expected same-intent candidate is materialized and classified as merge, collapse, remove, delegate, keep-facade, manual-review, or scoped with reason
- **THEN** Architecture Reduction MAY report candidate-inventory completeness
- **AND** the report SHALL expose the expected, materialized, and scoped candidate ids

#### Scenario: Candidate inventory evidence is stale
- **WHEN** the source surface inventory, similarity relations, or affected business-intent boundary changes after candidate classification
- **THEN** Architecture Reduction SHALL mark the candidate inventory stale
- **AND** no broad contraction-readiness claim SHALL rely on that inventory

### Requirement: Similarity provenance materializes into concrete reduction candidates
FlowGuard SHALL require every in-scope similarity relation id and similarity code-obligation id used for Architecture Reduction to bind to one or more concrete reduction candidates, target code nodes, and target actions.

#### Scenario: Similarity relation produces concrete candidates
- **WHEN** a duplicate-boundary, same-workflow, adapter-only, or overlapping-ownership relation is handed to Architecture Reduction
- **THEN** the relation and any required similarity code-obligation ids SHALL be recorded on the concrete candidates derived from that relation
- **AND** each candidate SHALL identify its target node and intended reduction action

#### Scenario: Similarity ids remain plan-level metadata
- **WHEN** a reduction plan cites similarity relation or code-obligation ids only as plan metadata and no concrete candidate consumes them
- **THEN** Architecture Reduction SHALL report unmaterialized similarity provenance
- **AND** the ids alone SHALL NOT support contraction readiness

#### Scenario: Relation side has no candidate or rationale
- **WHEN** one in-scope side of a similarity relation has neither a materialized candidate nor an explicit keep/scoped rationale
- **THEN** Architecture Reduction SHALL report incomplete relation coverage
- **AND** the relation SHALL remain an open reduction obligation

### Requirement: Retained same-intent facades prove delegation to the selected primary path
FlowGuard SHALL allow a public facade, alias, adapter, or wrapper to remain after contraction only when it preserves the external entrypoint by delegating to the selected primary path and does not retain independent business authority.

#### Scenario: Facade is retained as a delegating boundary
- **WHEN** a same-intent public surface must remain for compatibility
- **AND** current evidence binds the surface to the stable business intent, active behavior commitment, selected primary path, and owner code contract
- **THEN** Architecture Reduction MAY classify the surface as keep-facade or delegate
- **AND** the target action SHALL preserve only the delegating boundary

#### Scenario: Facade can succeed independently
- **WHEN** a retained facade can return business success, perform the primary side effect, or mutate the business terminal without invoking the selected primary path
- **THEN** Architecture Reduction SHALL classify it as parallel business authority or silent fallback
- **AND** the candidate SHALL NOT be ready as a retained facade

#### Scenario: Facade delegates to a different path for the same intent
- **WHEN** facade evidence names the expected `business_intent_id` but delegates to a primary-path id different from the selected path
- **THEN** Architecture Reduction SHALL report same-intent path drift
- **AND** the facade SHALL require repair, removal, or a genuinely different typed business intent before readiness
