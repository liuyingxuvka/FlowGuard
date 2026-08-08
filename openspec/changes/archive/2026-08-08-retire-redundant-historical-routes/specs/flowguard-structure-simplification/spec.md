## MODIFIED Requirements

### Requirement: Redundant compatibility fields may be removed
FlowGuard SHALL allow structure simplification to remove redundant legacy relation, maintenance-group, change-impact, test-obligation, and code-obligation fields when one canonical relation handoff plus consumer-native obligations preserve the required provenance, findings, blockers, and validation evidence. Retired fields SHALL be removed directly without aliases, dual emission, compatibility readers, or fallback parsing.

#### Scenario: Repeated ids are replaced by a typed handoff
- **WHEN** downstream route dataclasses repeat standalone similarity relation, maintenance-group, change-impact, test-obligation, or code-obligation id fields
- **THEN** FlowGuard MAY replace those fields with one canonical relation handoff and each route's native obligation rows
- **AND** focused tests MUST prove the same required route findings, warnings, blockers, and materialized owner obligations

#### Scenario: Retired fields are still supplied
- **WHEN** a caller supplies an intentionally retired compatibility field
- **THEN** the current interface fails visibly instead of translating or merging it into the canonical handoff

#### Scenario: Compatibility removal is released
- **WHEN** a redundant public field is removed during cleanup
- **THEN** changelog and version records MUST mark the cleanup as an intentional breaking surface change for the local 0.x version
- **AND** the retained protection semantics MUST remain covered by current owner tests

### Requirement: Handoff cleanup keeps route ownership explicit
FlowGuard SHALL keep route ownership visible after replacing repeated historical fields with a canonical relation handoff.

#### Scenario: Downstream route consumes canonical relation provenance
- **WHEN** Existing Model Preflight, Code Structure Recommendation, ContractExhaustionMesh, Model-Test Alignment, obligation-family parity, or Architecture Reduction consumes a canonical relation handoff
- **THEN** the route MUST materialize the handoff into its native cases, bindings, structure decisions, candidates, or scoped findings
- **AND** it MUST NOT treat relation provenance as proof by itself or recreate a standalone relation-review route

#### Scenario: Downstream route consumes similarity provenance
- **WHEN** a downstream route receives a retired similarity-provenance record
- **THEN** it MUST reject that retired authority and require one current canonical relation from the blueprint, commitment, or topology owner
- **AND** no compatibility reader or inferred translation is allowed
