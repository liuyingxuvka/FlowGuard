## ADDED Requirements

### Requirement: Self-owned model runners use the formal entry
FlowGuard's current repository-owned `.flowguard` model runner scripts SHALL
use a formal `FlowGuardCheckPlan`-based entry rather than calling
`Explorer(...)` as the script-level evidence path.

#### Scenario: Correct self-model consumes known-bad proof
- **WHEN** a `.flowguard` runner claims a correct self-model supports
  maintenance confidence
- **THEN** the runner MUST build a check plan with Risk Intent, minimum model
  contract, template reuse/no-match evidence, harvest closure, and current
  known-bad proof rows

#### Scenario: Bad self-model is actually caught
- **WHEN** a `.flowguard` runner declares an expected-bad workflow or explicit
  handled-bad label
- **THEN** the runner MUST prove that the bad case failed, was rejected, or was
  otherwise caught before the correct model consumes the proof

#### Scenario: Internal Explorer remains internal
- **WHEN** the formal runner explores finite states
- **THEN** `Explorer` MAY remain the internal engine behind
  `run_model_first_checks(...)`
- **AND** current `.flowguard` runner scripts MUST NOT call `Explorer(...)`
  directly as their public evidence entry
