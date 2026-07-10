## ADDED Requirements

### Requirement: Satellite Activation And Non-Use Boundaries
Every satellite skill SHALL define specific `Use When` and `Do Not Use When` conditions that distinguish it from the kernel and peer satellites. Delegated-only routes MUST state the permitted delegator and SHALL NOT activate as generic public fallbacks.

#### Scenario: Plan detailing is invoked generically
- **WHEN** PlanDetailing is selected without explicit user request or DevelopmentProcessFlow delegation
- **THEN** activation validation rejects the route and returns the correct owner handoff

### Requirement: Satellite Workflow And Evidence Output
Every satellite SHALL declare its required workflow, native checks, evidence fields, blockers, skipped-check handling, residual risk, claim boundary, and typed next actions. Its output MUST distinguish checked, unchecked, blocked, and uncertain obligations.

#### Scenario: Satellite omits residual risk
- **WHEN** a satellite reports completion without its required residual-risk and claim-boundary fields
- **THEN** its contract check fails and the result cannot satisfy parent closure

### Requirement: Prompt Size And Routed References
Satellite prompts SHOULD remain at or below 60 lines and 3000 characters. Required detail beyond the prompt budget SHALL move to directly linked, layout-resolvable references with explicit local-material routing.

#### Scenario: Installed reference is repository-only
- **WHEN** a satellite direct reference resolves in the source tree but not in a temporary installed layout
- **THEN** layout validation fails for the installed profile

### Requirement: Satellite Specific Contract Checks
Each satellite's check manifest SHALL include at least one check specific to its owned behavior or evidence gate in addition to shared schema/layout checks. A suite of only shared field-presence checks MUST NOT qualify as deep certification.

#### Scenario: Manifest contains only shared checks
- **WHEN** a satellite manifest lists no owner-specific check or test-gap disposition
- **THEN** depth validation fails with an insufficient-native-depth finding
