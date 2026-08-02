## ADDED Requirements

### Requirement: Direct user choice does not become FlowGuard admission
Development process SHALL preserve direct-user-choice, model-first, and no-code as user execution choices separate from FlowGuard implementation admission. Only the maturation and authorization owners may produce implementation admission, and non-waivable blockers remain authoritative.

#### Scenario: User chooses direct execution
- **WHEN** the user explicitly permits direct execution without complete FlowGuard modeling
- **THEN** the process records direct-user-choice without reporting verified or scoped FlowGuard readiness

#### Scenario: No-code request is current
- **WHEN** the current authorization is discussion-only
- **THEN** implementation admission reports no-code-requested regardless of model sufficiency
