## ADDED Requirements

### Requirement: PlanIntake consumes plan-detail source and risk surfaces
PlanIntake SHALL be able to consume source evidence and risk surfaces projected from a PlanDetail.

#### Scenario: Complete projected surfaces pass intake
- **WHEN** a plan-detail projection includes current source evidence and every in-scope risk surface has source or evidence mapping
- **THEN** PlanIntake can review the projected intake plan with no missing-surface findings

#### Scenario: Plan-detail unknown remains visible
- **WHEN** a plan-detail risk surface is marked in scope but omitted, unreviewed, or unmapped
- **THEN** PlanIntake reports the corresponding incomplete surface finding
