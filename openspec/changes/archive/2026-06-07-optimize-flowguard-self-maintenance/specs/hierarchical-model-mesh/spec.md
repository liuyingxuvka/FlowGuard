## ADDED Requirements

### Requirement: Self-maintenance child model freshness
Hierarchical Model Mesh SHALL include self-maintenance child model freshness when a parent FlowGuard confidence claim depends on route graph, field, structure, validation, or closure child models.

#### Scenario: Child model is stale
- **WHEN** a child self-maintenance model has stale, skipped, partial, or blocked evidence
- **THEN** the parent mesh SHALL downgrade broad confidence and name the child route that must be refreshed
