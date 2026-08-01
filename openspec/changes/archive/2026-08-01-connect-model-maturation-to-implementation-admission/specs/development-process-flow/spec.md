## ADDED Requirements

### Requirement: DevelopmentProcessFlow owns implementation admission
DevelopmentProcessFlow SHALL provide an internal implementation-admission decision that separately reports model sufficiency, execution authorization, final admission, exact allowed scope, accepted open gaps, required validation, and invalidation conditions before production edits.

#### Scenario: Sufficient model and current request are admitted
- **WHEN** the current task has a task/candidate/coverage-matching closed-for-task maturation result and the user currently requests implementation within that scope
- **THEN** admission SHALL return ready for only that exact scope

#### Scenario: Open model without override is blocked
- **WHEN** required maturation gaps remain and the user has not explicitly accepted those gaps for an exact bounded scope
- **THEN** admission SHALL block production edits while preserving the maturation next actions

#### Scenario: Exact override allows only a scoped edit
- **WHEN** the user explicitly authorizes an exact reversible scope and accepts named current gap fingerprints
- **THEN** admission MAY return ready-scoped for only that scope and MUST preserve the non-full maturation status

### Requirement: Non-waivable boundaries remain authoritative
Implementation admission SHALL NOT waive a current read-only or no-code instruction, safety or approval boundary, unknown target, stale identity, scope mismatch, conflicting live ownership, or unavailable real toolchain.

#### Scenario: Current task is read-only
- **WHEN** the current request forbids code changes
- **THEN** implementation admission MUST return no-code-requested or blocked regardless of model sufficiency or an older authorization

### Requirement: Authorization becomes stale when its subject changes
An implementation authorization SHALL bind the current task, request evidence, allowed actions and artifacts, accepted gap fingerprints, required validations, source/model/coverage fingerprints, and invalidation rules.

#### Scenario: Authorized scope changes
- **WHEN** the task, allowed path, candidate model, coverage universe, accepted gaps, source identity, or required validation changes
- **THEN** the prior authorization MUST become stale and MUST NOT admit implementation
