## ADDED Requirements

### Requirement: DevelopmentProcessFlow consumes one current strategy decision
DevelopmentProcessFlow SHALL remain the single public process owner, SHALL consume a current strategy-selection report when policy requires optimization, and SHALL preserve invalid, excluded, not-run, and re-evaluation gaps in its claim boundary.

#### Scenario: Required strategy evidence is missing
- **WHEN** a process scope requires strategy selection and no current report is bound to the plan
- **THEN** DevelopmentProcessFlow blocks the claim without creating an alternate process route

### Requirement: Minimum revalidation is coverage-aware
DevelopmentProcessFlow SHALL derive a deterministic non-dominated revalidation set that covers all currently affected validation requirements before using cost to break equivalent choices.

#### Scenario: One check covers two stale requirements
- **WHEN** one current check candidate covers two affected requirements and two other candidates cover one each at greater total cost
- **THEN** the recommendation selects the covering check set and preserves the declared cost boundary
