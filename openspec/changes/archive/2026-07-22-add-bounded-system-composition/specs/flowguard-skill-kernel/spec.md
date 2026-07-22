## ADDED Requirements

### Requirement: The default kernel recognizes bounded system-composition triggers
The default FlowGuard skill SHALL select bounded system composition when a non-trivial change affects multiple current models and involves event delivery, business identity, retry, ordering, shared resources, cache authority, external confirmation, atomicity, compensation, or an owner-bound system property. It SHALL route discovery, case generation, evidence, and process work to their existing satellite owners while retaining one canonical execution owner.

#### Scenario: Multiple models are merely colocated
- **WHEN** models have no declared interaction or shared property within the task boundary
- **THEN** the kernel does not create a composite slice solely because the model count is greater than one

#### Scenario: Local green could hide an interaction
- **WHEN** current local evidence cannot decide a cross-model event/resource/retry property
- **THEN** the kernel requests exact composite context and executable evidence rather than treating token closure as system proof

### Requirement: Kernel outputs preserve candidate model-delta status
Kernel guidance SHALL expose affected model/component ids, fingerprints, slice/binding status, shared identities/resources, system-property owner, finite bounds, composite evidence status, minimal trace target, and model-delta disposition. Proposed deltas MUST NOT be labeled current until accepted by the owner.

#### Scenario: Candidate relation is inferred
- **WHEN** code or topology suggests a relation that is not current authority
- **THEN** the output records `model_delta_status=proposed` and blocks broad use of that relation

