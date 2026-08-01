## ADDED Requirements

### Requirement: Maturation compiles independent pre-code coverage intake
The maturation owner SHALL accept a current typed intake before or after production implementation and SHALL derive the coverage universe from independently identified task requirements, current-system ownership, unresolved model angles, and only the specialist routes triggered for the task.

#### Scenario: Candidate cannot shrink the denominator
- **WHEN** a candidate model omits a task, current-system, behavior, field, UI, mesh, test, or angle coverage item supplied by a current independent owner contribution
- **THEN** maturation MUST keep that item open and MUST NOT report task-local full confidence

#### Scenario: Low-risk task stays narrow
- **WHEN** a task does not trigger a specialist route
- **THEN** the intake compiler MUST NOT require that route's unrelated inventory merely for ceremony

### Requirement: Owner contributions preserve native semantics
Each maturation contribution SHALL identify its native owner, task, coverage items, current evidence identity, and open signals, while the maturation compiler SHALL merge and deduplicate those contributions without rejudging the specialist's domain semantics.

#### Scenario: Stale specialist report is not promoted
- **WHEN** a specialist contribution is stale, scoped, skipped, not-run, progress-only, blocked, or lacks its required current evidence identity
- **THEN** maturation MUST preserve that status as a gap and MUST NOT convert it into passing coverage

### Requirement: Maturation report exposes exact sufficiency identity
The task-local maturation report SHALL expose the task id, model id, candidate fingerprint, coverage-universe id and fingerprint, input fingerprint, decision, confidence, open gaps, and terminal reason needed by downstream admission, risk, and closure consumers.

#### Scenario: Downstream identity can be checked
- **WHEN** a maturation result is used by another FlowGuard owner
- **THEN** that owner MUST be able to verify the exact task, candidate, and coverage identity without relying on prose or self-reported understanding
