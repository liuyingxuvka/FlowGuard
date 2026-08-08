## ADDED Requirements

### Requirement: The affected authority inventory has one existing model-system owner
An affected authority inventory that binds governed source, runtime, and test
endpoints into the model-system snapshot, together with the inventory root that
owns its identity, SHALL be owned by the existing authoritative model-system
model for revision-evidence purposes. Neither route SHALL create a second
authority model, inherit a generic owner, or pass solely because the complete
model-regression parent is green.

#### Scenario: Inventory endpoints enter an affected revision closure
- **WHEN** a governed source, runtime, or test endpoint owned by the affected authority inventory enters the exact revision closure
- **THEN** its native-owner evidence SHALL consume the exact-current authoritative model-system child evidence
- **AND** missing or ambiguous inventory ownership SHALL block model-authority activation

#### Scenario: Inventory root identity changes
- **WHEN** the affected authority inventory root itself enters the exact revision closure
- **THEN** the root's authoritative model-system route SHALL consume the same exact-current authoritative model-system child evidence
- **AND** it SHALL NOT inherit the default model-mesh owner
