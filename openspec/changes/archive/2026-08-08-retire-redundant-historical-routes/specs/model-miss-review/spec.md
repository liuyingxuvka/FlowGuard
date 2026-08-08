## ADDED Requirements

### Requirement: Model misses use one bounded back-propagation path
Every real model miss SHALL resolve the exact affected behavior commitment and blueprint owner, classify the missing state, branch, boundary, child, finite same-class case, or evidence, add the observed and bounded same-class cases to ContractExhaustion, update model/code/test bindings, replay only the canonical affected topology, and emit one ModelMaturation result.

#### Scenario: Runtime bug escapes a green model
- **WHEN** runtime, replay, test, UI, log, or production evidence exposes a bug after the model was accepted
- **THEN** Model Miss Review binds the bug to the exact existing owner and completes the canonical ContractExhaustion and ModelMaturation handoff
- **AND** final confidence consumes that one current result

#### Scenario: Similar bugs are considered
- **WHEN** a real miss can affect an explicitly related sibling, same-intent commitment, shared owner, or shared mechanism
- **THEN** FlowGuard generates finite same-class cases only over those canonical relations
- **AND** it MUST NOT repeatedly scan the whole repository using free-form similarity or reflection loops

#### Scenario: Exact owner cannot be resolved
- **WHEN** the current DNA cannot identify the affected owner or relation boundary
- **THEN** the miss remains blocked and becomes a model-depth obligation rather than using a guessed owner or fallback search
