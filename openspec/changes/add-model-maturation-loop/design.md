## Context

FlowGuard already has specialized routes:

- Model-first creates the fit-for-risk executable model.
- Model-Miss Review handles real failures after a green result.
- Model-Test Alignment compares model obligations, code contracts, boundary
  observations, and tests.
- Scenario Sandbox reveals suspicious traces and expected-vs-observed gaps.
- ModelMesh, TestMesh, StructureMesh, and Layered Boundary Proof own hierarchy
  and evidence splits.
- Risk Evidence Ledger and the closure contract decide final confidence.

The missing product behavior is a unifying decision point that says what those
routes mean for the model itself. A ledger gap should not just say "missing";
it should tell the agent whether to add a state field, add a transition, add an
invariant, add a same-class scenario, split a child model, reattach a parent,
or downgrade the claim.

## Goals / Non-Goals

**Goals:**

- Keep the loop simple enough for agents and users to understand.
- Make post-code and post-bug feedback a first-class part of model evolution.
- Reuse existing FlowGuard sub-capabilities rather than duplicate them.
- Give reports a small set of concrete next actions.
- Block or downgrade full claims when in-scope maturation signals remain
  unresolved.

**Non-Goals:**

- Do not make first-pass models huge by default.
- Do not rerun every route automatically.
- Do not turn the helper into a new Codex satellite skill.
- Do not replace Model-Miss Review, Model-Test Alignment, ModelMesh, TestMesh,
  Risk Evidence Ledger, or Closure Contract.

## Decisions

### Maturation Is An Orchestration Helper

The package adds `ModelMaturationSignal`, `ModelMaturationPlan`,
`ModelMaturationReport`, and `review_model_maturation_loop()`. Inputs are
route-level signals. The helper does not inspect route internals; it reads the
same structured evidence that agents already prepare.

### Actions Are Concrete And Small

The report recommends only bounded actions:

- `no_model_change_needed`
- `add_state_field`
- `add_transition_case`
- `add_invariant`
- `add_same_class_scenario`
- `split_child_model`
- `reattach_parent_model`
- `refresh_evidence`
- `add_code_boundary_observation`
- `add_model_obligation`
- `downgrade_claim`

These are not implementation commands. They are model-lifecycle decisions that
route the next work to the existing owning capability.

### Signal Mapping Stays Conservative

Known signals map to default actions:

- `state_too_coarse` -> `add_state_field`
- `input_branch_missing` or `boundary_missing` -> `add_transition_case`
- `invariant_too_weak` -> `add_invariant`
- `same_class_missing` -> `add_same_class_scenario`
- `child_reattachment_missing` or child-boundary drift -> `reattach_parent_model`
- `duplicate_primary_edge_path` or `oversized_model` -> `split_child_model`
- `missing_model_obligation` -> `add_model_obligation`
- `stale_evidence` or `progress_only_evidence` -> `refresh_evidence`
- `code_boundary_mismatch` or `missing_code_boundary_observation` ->
  `add_code_boundary_observation`
- unresolved required signals also imply `downgrade_claim`

Callers may supply suggested actions to keep specialized route knowledge.

### Closure Consumes The Decision

The closure contract stays the final gate. The maturation helper supplies a
clear input to that gate: either the model is current for the claim, or the
claim is blocked/scoped because the model still needs maturation work.

## Risks / Trade-offs

- **Risk: helper looks like a replacement for route checks.** Mitigation:
  docs and API text say it consumes route signals and does not validate route
  internals.
- **Risk: agents over-upgrade models.** Mitigation: green/no-signal path
  returns `no_model_change_needed`.
- **Risk: agents hide unresolved signals behind scoped claims.** Mitigation:
  required unresolved signals downgrade the claim and remain visible in report
  findings.
- **Risk: peer-agent collisions.** Mitigation: add a small new helper module
  and targeted doc updates, without refactoring existing route internals.

## Validation

- Unit tests cover green maturation, state-too-coarse, same-class-missing,
  child reattachment, stale evidence, missing model obligation, caller-supplied
  suggested actions, and blocked full-claim decisions.
- API/docs/skill tests verify the helper is public and described as a loop over
  existing sub-capabilities.
- OpenSpec status is checked before implementation and final validation.
