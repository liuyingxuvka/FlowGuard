## ADDED Requirements

### Requirement: DevelopmentProcessFlow consumes plan-detail projections for rough plans
DevelopmentProcessFlow SHALL consume PlanDetail projections for non-trivial rough plans, AI-generated plans, or plan discussions before reviewing lifecycle order, evidence freshness, and completion claims.

#### Scenario: Rough plan projection supplies lifecycle rows
- **WHEN** a rough plan is converted to PlanDetail rows with artifacts, ordered steps, validation, evidence, and freshness rules
- **THEN** DevelopmentProcessFlow reviews the projected DevelopmentProcessPlan using the same ids and current freshness rules

#### Scenario: Prose-only lifecycle plan is not current evidence
- **WHEN** a non-trivial lifecycle claim relies only on a long Markdown or numbered prose plan
- **THEN** DevelopmentProcessFlow treats the claim as scoped or unsupported until structured lifecycle rows and evidence ids exist

### Requirement: Plan-detail gaps remain claim boundaries
DevelopmentProcessFlow SHALL preserve missing, skipped, stale, or scoped PlanDetail rows as lifecycle claim boundaries when deriving minimum revalidation.

#### Scenario: Missing subrequirement blocks done claim
- **WHEN** a projected plan has a subrequirement without current validation evidence or an accepted scoped omission
- **THEN** DevelopmentProcessFlow reports missing required revalidation or unsupported claim evidence before allowing full done confidence

#### Scenario: Later writes stale projected evidence
- **WHEN** implementation changes an artifact after projected validation evidence was produced
- **THEN** DevelopmentProcessFlow marks that evidence stale using the projected artifact and evidence ids
