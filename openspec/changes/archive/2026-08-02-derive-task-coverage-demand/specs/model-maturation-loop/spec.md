## ADDED Requirements

### Requirement: Maturation consumes an independent coverage demand
The model maturation loop SHALL evaluate candidate completeness against a current compiled TaskCoverageDemand and SHALL NOT treat a caller-authored list of contribution identifiers as the minimum denominator.

#### Scenario: Supplied contributions are internally green but demand is incomplete
- **WHEN** all supplied contribution evidence passes but at least one demanded row is unresolved or blocked
- **THEN** the maturation result is not closed for the task
