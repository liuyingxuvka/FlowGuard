## ADDED Requirements

### Requirement: Whole-system authority is semantic rather than inventory-only
A whole-system understanding claim SHALL be licensed only when every member of the finite current model universe has a semantic disposition and all required inter-model and consumer relations are current. Presence in the inventory alone SHALL NOT license the claim.

#### Scenario: All model files exist without consumer relations
- **WHEN** the finite universe contains every current model file but required consumer relations are absent
- **THEN** whole-system understanding remains unresolved

#### Scenario: Semantic relation changes after verification
- **WHEN** a model disposition or required relation changes after the whole-system receipt
- **THEN** every consuming whole-system claim becomes stale
