## ADDED Requirements

### Requirement: Model maturation emits open obligations for unresolved signals
Model maturation loop SHALL preserve unresolved required maturation signals as
open maintenance obligations until they are resolved or explicitly scoped.

#### Scenario: Required signal becomes open obligation
- **WHEN** an in-scope required maturation signal such as `state_too_coarse`,
  `input_branch_missing`, `missing_model_obligation`, stale evidence, or
  code-boundary mismatch remains unresolved
- **THEN** the maturation report MUST be able to expose an open obligation
- **AND** that obligation MUST name `model_maturation_loop` or the downstream
  owner route required to resolve it

#### Scenario: Scoped signal stays visible
- **WHEN** a required maturation signal is scoped out with a reason
- **THEN** the scoped disposition MUST remain visible
- **AND** broad confidence MUST be downgraded unless current evidence resolves
  the scoped obligation

