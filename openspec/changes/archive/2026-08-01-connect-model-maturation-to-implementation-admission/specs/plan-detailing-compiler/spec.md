## ADDED Requirements

### Requirement: Plan detail pass is not implementation admission
A passing PlanDetail review SHALL prove only that the plan is detailed enough to inspect and project; production edit steps SHALL depend on a separate current DevelopmentProcessFlow implementation-admission result.

#### Scenario: Detailed plan lacks implementation authorization
- **WHEN** all plan rows are complete but no current implementation admission permits the code step
- **THEN** the plan MAY continue through modeling and recommendation steps but MUST NOT authorize the production edit

### Requirement: Plan detail projects task coverage to maturation
PlanDetail SHALL project in-scope requirements, risks, states, side effects, failure branches, validation obligations, and scoped-out boundaries into the independent Model Maturation intake.

#### Scenario: Plan risk is missing from candidate model
- **WHEN** an in-scope required plan risk has no matching candidate coverage or explicit current disposition
- **THEN** maturation MUST keep the risk open instead of allowing the candidate to shrink the plan-derived coverage
