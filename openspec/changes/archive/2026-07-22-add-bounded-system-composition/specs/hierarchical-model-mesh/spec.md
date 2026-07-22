## ADDED Requirements

### Requirement: ModelMesh hands off bounded composite candidates without executing them
For parent/child, sibling reattachment, or hierarchical closure/freshness work, ModelMesh SHALL be able to emit a typed composite-candidate handoff containing exact child ids/fingerprints, proposed event/resource relations, affected siblings, a referenced current system-property owner or `owner_missing` gap, unresolved relations, proposed changed roots, and any current system-definition reference. It SHALL consume a composite receipt only when the referenced definition, exact slice, and component fingerprints match. Ordinary peer-model composition SHALL route directly to the portable-system owner without requiring ModelMesh.

#### Scenario: Candidate packet is complete
- **WHEN** a parent/child or sibling relationship creates an executable interaction risk
- **THEN** ModelMesh hands the packet to the canonical portable-composition owner without expanding or executing child graphs

#### Scenario: Composite receipt is stale
- **WHEN** any component, relation, property, or slice fingerprint differs from the receipt
- **THEN** ModelMesh reports stale composite evidence and cannot infer parent green from child-local passes
