## ADDED Requirements

### Requirement: Preflight resolves authority before relevance
Existing Model Preflight SHALL validate the project observed-head snapshot
before selecting current model context. Lexical, path, class-name, ledger, or
filesystem discovery MAY identify candidates but MUST NOT make them current.

#### Scenario: Discovered file is not in the observed snapshot
- **WHEN** a model-like file matches the task text but is absent from the validated observed-head snapshot
- **THEN** preflight labels it non-authoritative discovery context and does not select it as the current primary model

#### Scenario: Observed head is missing or stale
- **WHEN** the project pointer is missing, its snapshot fingerprint differs, or its subject revision differs from the software revision
- **THEN** preflight blocks current-model confidence and reports the exact authority defect

### Requirement: Preflight reports the selected system context
Preflight SHALL report the observed source revision, observed snapshot
fingerprint, bounded coverage status, selected same-plane primary model ids,
candidate snapshot fingerprint when present, affected closure ids, unresolved
gap ids, and claim boundary.

#### Scenario: Target proposal is discussed
- **WHEN** a task has an observed base and a separate target snapshot
- **THEN** preflight reports both identities without presenting the target as the current software model
