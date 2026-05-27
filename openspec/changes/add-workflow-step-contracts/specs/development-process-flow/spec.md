## ADDED Requirements

### Requirement: DevelopmentProcessFlow consumes workflow step contracts
FlowGuard SHALL allow DevelopmentProcessFlow planning to consume workflow step contracts by projecting required receipts and claim gates into validation requirements that participate in missing, stale, skipped, failed, and progress-only evidence review.

#### Scenario: Step contract creates validation requirement
- **WHEN** a workflow step contract declares receipt `full_regression` as required for claim label `done_claimed`
- **THEN** the projection SHALL create a validation requirement that identifies the contract id, receipt id, and claim scope

#### Scenario: Projected requirement remains ordinary process evidence
- **WHEN** projected validation requirements are passed into `review_development_process_flow(...)`
- **THEN** DevelopmentProcessFlow SHALL review them with the same current, stale, skipped, failed, hidden-skip, not-run, running, and progress-only evidence rules used for manually declared validation requirements
