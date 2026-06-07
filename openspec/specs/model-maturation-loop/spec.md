# model-maturation-loop Specification

## Purpose
This capability defines FlowGuard's Model Maturation Loop behavior and the evidence required to use it safely in AI-agent maintenance workflows.
maturation deltas can be archived into a main spec.
## Requirements
### Requirement: Complete FlowGuard Use Requires Current Maturation Decision

FlowGuard closure claims SHALL consume the current model maturation decision
before reporting complete FlowGuard use.

#### Scenario: Closure claim consumes maturation

- **GIVEN** a task claims complete FlowGuard use
- **AND** route evidence includes code, test, model-miss, mesh, or risk-ledger
  signals
- **WHEN** the closure contract is reviewed
- **THEN** the claim requires a current maturation decision showing the model
  is current or the claim is explicitly partial/scoped

### Requirement: Model Maturation Loop Produces Explicit Upgrade Decisions

FlowGuard SHALL provide a model maturation loop that consumes route-level
signals from post-code evidence, model misses, alignment, scenario review,
mesh review, evidence freshness, and risk ledgers, then returns explicit model
upgrade actions.

#### Scenario: No maturation signal keeps the model current

- **GIVEN** a model has current route evidence
- **AND** there are no unresolved in-scope maturation signals
- **WHEN** the maturation loop is reviewed
- **THEN** it reports `no_model_change_needed` and allows the current claim to
  continue within its declared boundary

#### Scenario: In-scope signal recommends a model upgrade

- **GIVEN** an in-scope unresolved signal such as `state_too_coarse`,
  `input_branch_missing`, `same_class_missing`, `child_reattachment_missing`,
  `duplicate_primary_edge_path`, or `missing_model_obligation`
- **WHEN** the maturation loop is reviewed
- **THEN** it reports a concrete action such as `add_state_field`,
  `add_transition_case`, `add_same_class_scenario`, `reattach_parent_model`,
  `split_child_model`, or `add_model_obligation`

### Requirement: Unresolved Maturation Blocks Or Downgrades Full Claims

FlowGuard SHALL prevent unresolved required maturation signals from supporting
full done, release, publish, or production-confidence claims.

#### Scenario: Full claim has unresolved maturation

- **GIVEN** a task makes a full confidence claim
- **AND** an in-scope required maturation signal remains unresolved
- **WHEN** the maturation loop is reviewed
- **THEN** the report includes `downgrade_claim` and returns a blocked or
  scoped decision instead of full confidence

#### Scenario: Scoped signal remains visible

- **GIVEN** a signal is explicitly out of scope or non-required
- **WHEN** the maturation loop is reviewed
- **THEN** the signal remains visible as scoped evidence and does not silently
  become a pass

### Requirement: Model Maturation Reuses Existing Sub-Capabilities

FlowGuard SHALL describe the maturation loop as an orchestration helper over
existing sub-capabilities rather than as a replacement route.

#### Scenario: Model miss feeds maturation

- **GIVEN** Model-Miss Review classifies a real failure after a green result
- **WHEN** the maturation loop consumes that signal
- **THEN** it recommends the model update action while Model-Miss Review still
  owns the observed failure and same-class bad-case responsibility

#### Scenario: Parent child evidence feeds maturation

- **GIVEN** a child model changed under a parent model
- **WHEN** ModelMesh or layered proof reports stale or missing reattachment
- **THEN** the maturation loop recommends `reattach_parent_model` or
  `split_child_model` while ModelMesh still owns the actual reattachment proof

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

