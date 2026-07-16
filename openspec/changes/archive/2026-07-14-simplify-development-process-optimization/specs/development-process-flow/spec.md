## MODIFIED Requirements

### Requirement: DevelopmentProcessFlow consumes one current strategy decision
DevelopmentProcessFlow SHALL remain the single public process owner. It SHALL derive `process_optimization_status` as `not_needed`, `selected`, or `blocked`; SHALL require exactly one current optimization decision only when stable activation reasons are present; SHALL enforce hard outcome/evidence/safety/side-effect/dependency/authority equivalence; and SHALL preserve invalid candidates, hard blockers, not-run work, repair groups, affected revalidation, and stale-decision gaps in its claim boundary. It SHALL NOT create an alternate strategy report or route.

#### Scenario: Required optimization evidence is missing
- **WHEN** a process has an activation reason but no current decision evidence
- **THEN** DevelopmentProcessFlow reports `blocked` without creating an alternate process route

#### Scenario: Optimization is not needed
- **WHEN** a plan has no activation reason and no optimization decision
- **THEN** DevelopmentProcessFlow reports `not_needed` and omits optimizer details

#### Scenario: Decision exists without activation
- **WHEN** a caller supplies candidates or a decision for an ordinary inactive plan
- **THEN** DevelopmentProcessFlow rejects the unnecessary optimizer state

### Requirement: Minimum revalidation is coverage-aware
DevelopmentProcessFlow SHALL derive a deterministic revalidation set that covers every currently affected validation requirement and protected side-effect boundary before comparing equivalent covering sets. Estimated cost SHALL support only a preferred-set claim under current declared inputs; a bounded minimum claim requires a complete finite candidate set and current measured costs.

#### Scenario: One check covers two stale requirements
- **WHEN** one current check candidate covers two affected requirements and two other candidates cover one each at greater declared cost
- **THEN** the recommendation selects the covering check set and states whether its cost basis is estimated or measured

#### Scenario: Repair group omits one affected obligation
- **WHEN** a selected revalidation set leaves one repair-group obligation uncovered
- **THEN** DPF blocks the repair completion claim regardless of lower cost
