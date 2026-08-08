## MODIFIED Requirements

### Requirement: Cross-route validation evidence gate
The retained `validation_evidence_gates` model SHALL represent the permanent evidence-kernel contract rather than an implementation rollout. It SHALL bind current evidence primitives, field structures, lifecycle, receipts, proof artifacts, validation ownership, and terminal results to their real code, tests, and normative specifications. It SHALL preserve stale, failed, skipped, not-run, progress-only, duplicate-owner, foreign-owner, and proof-fingerprint mismatch states as non-terminal evidence and SHALL require the current-head identity to match the terminal receipt before a broad claim. UI click-through, payload-domain semantics, manual operability, installed-skill synchronization, and release order SHALL remain delegated to their existing specialist owners.

#### Scenario: Rollout milestones are offered as current evidence behavior
- **WHEN** the retained model reaches success only because documentation, prompt, installation, or one-time rollout flags are set
- **THEN** current evidence-kernel purpose closure is blocked

#### Scenario: Real evidence implementation changes
- **WHEN** an owned evidence primitive, lifecycle, receipt, proof, ownership, result, test, or normative spec changes
- **THEN** the model-regression input identity becomes stale and the old evidence-kernel result cannot support current DNA

#### Scenario: Progress or skipped work is presented as terminal success
- **WHEN** a receipt is progress-only or hides failed, skipped, or not-run child work
- **THEN** the evidence model rejects terminal success and preserves the exact non-pass identities

#### Scenario: Ordinary validation would purge evidence automatically
- **WHEN** an ordinary run proposes automatic persistent evidence deletion without the recoverable lifecycle owner and explicit boundary
- **THEN** the model rejects the operation rather than treating cleanup as validation
