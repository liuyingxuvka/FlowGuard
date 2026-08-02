## ADDED Requirements

### Requirement: Development process consumes distribution evidence without owning distribution inventory
DevelopmentProcessFlow SHALL consume typed, current installation or distribution evidence when the task requires it, but SHALL NOT own a fixed satellite count, installation algorithm, or SkillGuard validation procedure.

#### Scenario: Suite inventory changes
- **WHEN** the maintained FlowGuard suite adds or removes a member
- **THEN** DevelopmentProcessFlow relies on the current distribution evidence identity rather than requiring its own inventory update
