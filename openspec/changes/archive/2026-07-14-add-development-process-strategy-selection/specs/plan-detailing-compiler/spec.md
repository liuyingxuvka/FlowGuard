## ADDED Requirements

### Requirement: Plan detail projects strategy execution gates
PlanDetailing SHALL preserve selected candidate ids, diagnostic campaign ids, repair batch ids, and strategy re-evaluation gate ids in the detailed steps and DPF projection.

#### Scenario: Repair batch changes governed artifacts
- **WHEN** a plan step applies a repair batch
- **THEN** the projected process includes its mandatory re-evaluation and revalidation gates before completion
