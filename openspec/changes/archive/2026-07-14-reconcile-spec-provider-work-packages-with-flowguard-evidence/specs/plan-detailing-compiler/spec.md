## ADDED Requirements

### Requirement: PlanDetail preserves provider task identity and mappings
PlanDetail SHALL preserve provider, work-package, change, and task identities plus mapped obligations/checks or typed scoped-out reasons when specification work is projected into plan steps.

#### Scenario: Specification tasks become plan steps
- **WHEN** a provider task list is compiled into PlanDetail rows
- **THEN** every in-scope task SHALL retain its source identity and bidirectional obligation/check mapping through DevelopmentProcessFlow and TestMesh projections

#### Scenario: Task text alone is used as identity
- **WHEN** similar task wording from parallel changes would collapse two tasks
- **THEN** PlanDetail SHALL reject the ambiguous projection
