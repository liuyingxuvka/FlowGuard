## ADDED Requirements

### Requirement: Installed route groups
FlowGuard global routing SHALL expose installed satellite routes as route groups with stable ids, trigger summaries, minimal inputs, primary outputs, evidence boundaries, and downstream handoffs.

#### Scenario: Specialist route has public helpers
- **WHEN** a specialist route exports public helpers, templates, docs, or installed skill guidance
- **THEN** the route SHALL have a corresponding route discovery group unless it is explicitly scoped out with a reason

### Requirement: Handoff continuity
Route groups SHALL express how SummaryReport, MaintenanceScan, ExistingModelPreflight, FieldLifecycleMesh, Model-Test Alignment, StructureMesh, TestMesh, ModelMesh, DevelopmentProcessFlow, Risk Evidence Ledger, and Closure Contract hand off to one another.

#### Scenario: Maintenance finding identifies a route owner
- **WHEN** a finding or maintenance obligation names a route owner
- **THEN** route discovery SHALL provide the minimal inputs and next-action path for that owner
