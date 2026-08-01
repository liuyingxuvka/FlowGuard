## ADDED Requirements

### Requirement: Model Maturation is the sole task-local sufficiency owner
FlowGuard SHALL use Model Maturation, and no prompt, preflight, plan, authorization, risk row, or closure helper, as the sole owner of whether the current model is sufficiently deep for the exact task and claim boundary.

#### Scenario: Permission does not upgrade sufficiency
- **WHEN** a user explicitly authorizes implementation with listed open gaps
- **THEN** the maturation decision and confidence MUST remain unchanged and any non-full status MUST remain visible

### Requirement: Broad consumers use the same current maturation result
DevelopmentProcessFlow admission, broad Risk Evidence Ledger rows, and Closure Contract SHALL consume the same current task/candidate/coverage-bound maturation result when they participate in one broad claim.

#### Scenario: Consumers use different maturation identities
- **WHEN** downstream consumers reference different task, candidate, coverage, input, or maturation evidence identities
- **THEN** the broad claim MUST be blocked as an identity mismatch
