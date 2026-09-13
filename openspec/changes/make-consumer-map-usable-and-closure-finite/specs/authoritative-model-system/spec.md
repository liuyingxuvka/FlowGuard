## MODIFIED Requirements

### Requirement: A project has one observed model-system head

The project SHALL expose exactly one model-authority pointer for the current
`observed_implementation` snapshot. The pointer SHALL identify the snapshot by
content fingerprint and subject revision, and no registry label, file
discovery result, model-id suffix, target snapshot, experiment snapshot, or
alternate pointer SHALL act as a fallback current authority. The pointer's
generation, activation receipt, and reverse-binding metadata SHALL be treated
as authority-transaction binding context, distinct from the selected model
content and its functional input identity.

#### Scenario: Current-model lookup resolves the sole observed head
- **WHEN** a consumer asks which model system describes the software now
- **THEN** the system resolves and validates the project model-authority
  pointer before performing relevance lookup
- **AND** only active members of that observed snapshot are eligible as current
  model owners

#### Scenario: Missing or invalid head fails visibly
- **WHEN** the project model-authority pointer is missing, ambiguous, refers to
  a non-observed lane, or does not match the referenced snapshot fingerprint
- **THEN** current-model lookup reports observed authority as unavailable
- **AND** it does not infer a replacement from discovered files, registry
  entries, lexical matches, or historical evidence

#### Scenario: Pointer binding changes after functional validation
- **WHEN** generation, activation receipt, or reverse binding changes while the
  selected snapshot, model payloads, contracts, and resolved functional inputs
  remain identical
- **THEN** the system performs one finite binding/CAS integrity check
- **AND** it does not invalidate or rerun the selected model's functional
  producer solely because the binding metadata changed

#### Scenario: Selected model content changes
- **WHEN** a model payload, owner input, contract, oracle, or required relation
  selected by the new pointer differs from the accepted snapshot
- **THEN** the affected model closure becomes stale until revalidated
- **AND** the content change is not classified as pointer-only metadata

### Requirement: Finite recursive model composition is depth-independent

The observed model system SHALL compose any finite hierarchy through one
bottom-up traversal. A parent SHALL consume the exact direct-child receipts
and its own typed connection obligations; adding a level SHALL not launch a
new whole-system validation cycle. The model pointer/head remains provenance
and integrity context, while node functional freshness is decided from the
resolved node closure.

#### Scenario: Deep finite hierarchy
- **WHEN** a valid model has more than five nested levels
- **THEN** the hierarchy reviewer processes each node exactly once in a deterministic post-order
- **AND** it does not impose a fixed depth limit or rerun all descendants for each parent

#### Scenario: Pointer changes without node content changes
- **WHEN** a new current pointer resolves the same node model, partition, obligations, and connections
- **THEN** those nodes remain eligible for exact reuse
- **AND** a changed pointer alone does not make every descendant stale
