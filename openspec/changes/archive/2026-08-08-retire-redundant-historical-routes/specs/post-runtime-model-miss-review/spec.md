## ADDED Requirements

### Requirement: Model Miss Review emits an exact blueprint gap and bounded case seed
Post-runtime Model Miss Review SHALL classify why the accepted current model missed the observed behavior, bind the miss to one exact current blueprint owner and behavior commitment, and emit only a typed model-depth gap plus observed-problem and bounded canonical-relation seeds. ContractExhaustionMesh, not Model Miss Review, SHALL generate or own the finite same-class, sibling, combination, boundary, and holdout case identities.

#### Scenario: Observed miss resolves to a current owner
- **WHEN** runtime, replay, test, UI, log, manual, or production evidence exposes a miss and current authority resolves its blueprint owner
- **THEN** Model Miss Review records the observed failure, previous green reason, root-cause gap type, exact owner and commitment identities, and canonical relation ids
- **AND** it hands those seeds to ContractExhaustionMesh and the gap to ModelMaturation

#### Scenario: Related risk has no canonical relation
- **WHEN** a suspected sibling or similar surface is not connected by a current same-intent, shared-owner, affected-sibling, shared-mechanism, or other canonical relation
- **THEN** Model Miss Review records an unresolved relation or model-depth gap
- **AND** it MUST NOT widen the review through a caller-supplied or free-form analogous repository scan

#### Scenario: Canonical cases return to the miss chain
- **WHEN** ContractExhaustionMesh materializes the finite required cases and oracles
- **THEN** Model Miss Review references those case ids for the model update, model-code-test binding, and affected-topology replay
- **AND** it MUST NOT create a parallel case list or completion receipt

### Requirement: Recurring misses reopen the same canonical owner
When a miss recurs, FlowGuard SHALL reopen the same exact blueprint owner, canonical case universe, model-code-test bindings, and affected replay scope. Recurrence MAY increase required finite coverage or maturation depth, but MUST NOT create a new DefectFamily owner or merge failures from different behavior planes by shared wording alone.

#### Scenario: Same owner and mechanism recur
- **WHEN** current evidence shows another miss against the same commitment, owner, and mechanism
- **THEN** ModelMaturation and ContractExhaustionMesh deepen that same owner and case universe
- **AND** the new evidence retains its own observed case id and source identity

#### Scenario: Similar symptom belongs to another plane
- **WHEN** two misses share a visible symptom but affect different product, agent-operation, or development-process commitments
- **THEN** they remain separate owner-local misses unless a current typed relation explicitly connects them

## MODIFIED Requirements

### Requirement: In-scope misses add one generalized bad case
The model-first Skill SHALL require an in-scope model miss to contribute the observed failure and, when the canonical affected relation set contains a practical same-class dimension, at least one bounded seed to ContractExhaustionMesh before the repaired model is trusted.

#### Scenario: Same-class bad case is practical
- **WHEN** the missed issue belongs inside the modeled boundary and a finite same-class variant can be expressed over canonical relation endpoints
- **THEN** ContractExhaustionMesh creates or reuses a stable canonical case with an executable oracle
- **AND** the accepted model and current evidence reference that case id

#### Scenario: Same-class bad case is not practical
- **WHEN** the miss is outside the modeled boundary, no canonical related member exists, or the additional case is not practical for the current scoped claim
- **THEN** the review records the exact boundary or scoped reason
- **AND** it does not manufacture an open-ended search obligation

### Requirement: Model misses upgrade the model before same-class exhaustion
FlowGuard MUST require non-trivial in-scope model misses to become an exact model rule, state or branch refinement, child-model obligation, declared boundary, or evidence-depth gap on the current blueprint owner before ContractExhaustionMesh case evidence can support broad closure.

#### Scenario: Observed bug becomes model rule
- **WHEN** a runtime, test, replay, UI, log, manual, or production bug appears after a FlowGuard pass
- **THEN** the review records the exact root-cause blueprint gap and the accepted model rule or declared boundary that now represents the failure

#### Scenario: Same-class closure uses contract exhaustion
- **WHEN** the repaired failure requires finite same-class, sibling, interaction, boundary, or holdout evidence
- **THEN** Model Miss Review consumes stable ContractExhaustionMesh case ids and oracles
- **AND** a hand-written family list or analogous-scan result MUST NOT become canonical coverage

### Requirement: Concrete miss records preserve behavior identity
Runtime, UI, and recurring-miss records SHALL preserve the affected behavior plane, commitment id, blueprint block id, primary owner model id, owner code-contract id when known, evidence source, previous green identity, and bounded canonical relation ids.

#### Scenario: UI test operation miss is recorded
- **WHEN** an AI-operated UI integration run fails because the agent did not connect required services
- **THEN** the concrete miss record SHALL identify the agent-operation commitment and owner model
- **AND** the visible product capability MAY be recorded only as typed related context

#### Scenario: Identity is unknown
- **WHEN** concrete evidence proves a failure but no current commitment or blueprint owner can be resolved
- **THEN** the record SHALL preserve the selected plane and an ownership or coverage-gap status
- **AND** it SHALL route to Behavior Commitment Ledger or blueprint ownership repair without guessing a family or owner

### Requirement: User-observed UI mismatch after green evidence is a model miss
Post-runtime Model Miss Review SHALL treat user-visible UI mismatch after a green FlowGuard claim as a model miss. The review MUST record the previous green claim, observed UI failure, miss classification, why the previous model passed, exact affected UI behavior owner, bounded canonical relations, and the tests or implementation evidence needed to prevent recurrence.

#### Scenario: User opens UI and a wired button fails
- **WHEN** a user observes that an enabled UI button does not perform the claimed function after a prior green model or implementation claim
- **THEN** Model Miss Review classifies the issue as evidence_overclaimed, boundary_missing, state_too_coarse, input_branch_missing, or another supported miss type
- **AND** ContractExhaustionMesh materializes the required finite related UI cases before broad closure

#### Scenario: Local patch cannot close UI miss
- **WHEN** canonical relations show that a UI miss affects a finite class of buttons, fields, file pickers, table loaders, or visible state updates
- **THEN** repairing only the observed instance is insufficient for broad confidence unless the remaining canonical cases are explicitly scoped with rationale

#### Scenario: Previous green reason is preserved
- **WHEN** a prior FlowGuard model or task was marked green before the UI miss
- **THEN** the miss review records which evidence passed, why it was too narrow, and which new model, case, test, or validation row would have failed earlier

## REMOVED Requirements

### Requirement: Model-miss review can derive family sibling bad cases
**Reason**: Model Miss Review should identify the exact miss and bounded relations, while ContractExhaustionMesh remains the sole canonical finite-case generator.
**Migration**: Emit observed-problem and canonical-relation seeds to ContractExhaustionMesh and consume its stable case ids.

### Requirement: Model-miss review scans analogous defect radius
**Reason**: A free-form analogous scan can expand without a canonical denominator and duplicates affected-topology and finite-case ownership.
**Migration**: Limit related coverage to explicit canonical relations and preserve an unresolved model-depth gap when that relation set is insufficient.

### Requirement: Recurring defect gates remain plane-local
**Reason**: Plane-local identity remains necessary, but a separate DefectFamily gate is redundant.
**Migration**: Reopen the same plane-local blueprint owner, ContractExhaustionMesh case universe, ModelMaturation result, and model-code-test evidence.
