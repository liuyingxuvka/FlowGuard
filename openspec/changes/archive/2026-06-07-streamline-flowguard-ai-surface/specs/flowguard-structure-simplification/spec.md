## ADDED Requirements

### Requirement: Redundant compatibility fields may be removed
FlowGuard SHALL allow structure simplification to remove redundant compatibility
fields when a clearer replacement preserves the represented behavior and
validation evidence.

#### Scenario: Repeated ids are replaced by a typed handoff
- **WHEN** multiple downstream route dataclasses repeat model-similarity
  relation, maintenance-group, change-impact, test-obligation, or
  code-obligation id fields
- **THEN** FlowGuard MAY replace those fields with a single typed handoff
- **AND** tests MUST prove the same route findings, warnings, and blockers are
  still produced through the new structure

#### Scenario: Compatibility removal is released
- **WHEN** a redundant public field is removed during a cleanup
- **THEN** changelog and version records MUST mark the cleanup as an
  intentional breaking surface change for the local 0.x version
- **AND** the full capability behavior MUST remain covered by current tests

### Requirement: Handoff cleanup keeps route ownership explicit
FlowGuard SHALL keep route ownership visible after replacing repeated fields
with a handoff object.

#### Scenario: Downstream route consumes similarity provenance
- **WHEN** Existing Model Preflight, Code Structure Recommendation,
  Model-Test Alignment, or Architecture Reduction consumes model-similarity
  evidence
- **THEN** the route MUST read the typed handoff and emit route-specific
  findings rather than treating similarity as proof by itself
