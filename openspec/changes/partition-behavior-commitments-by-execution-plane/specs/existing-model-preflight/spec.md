## ADDED Requirements

### Requirement: Project preflight queries commitments before path discovery
Full Existing Model Preflight SHALL query the canonical Behavior Commitment Ledger from the task summary, canonical terms, paths, tools, and error signatures before supplementing results with path-based model inventory.

#### Scenario: Registered AI operation is recalled
- **WHEN** a non-trivial task matches an `agent_operation` commitment lookup binding
- **THEN** preflight SHALL include that commitment and its primary owner model in the primary hit set before path-only model hits

#### Scenario: Path scan supplements commitment owner
- **WHEN** changed paths identify additional current models after a commitment owner is selected
- **THEN** preflight SHALL add those models as supplementary context without replacing the primary commitment owner

### Requirement: Preflight separates primary and related planes
Preflight output SHALL record lookup status, primary behavior plane, primary commitment hits, typed related commitment hits, plane ambiguity, and ledger fingerprint.

#### Scenario: Product target is related to agent operation
- **WHEN** an agent-operation commitment invokes a product-runtime commitment
- **THEN** preflight SHALL show the agent commitment as primary and the product commitment as an invoked target
- **AND** SHALL NOT present the product row as an AI instruction

#### Scenario: Development process governs operation
- **WHEN** a development-process commitment governs the selected agent operation
- **THEN** preflight SHALL show it as governing context rather than a second primary operation

### Requirement: Missing ledger fallback remains explicit
Existing Model Preflight MAY use its current project inventory scan when commitment lookup is missing, not applicable, or blocked, but SHALL preserve that status and confidence boundary.

#### Scenario: Ledger missing but models exist
- **WHEN** no canonical ledger can be loaded and path inventory finds relevant models
- **THEN** preflight SHALL return `fallback` lookup status with the model hits
- **AND** SHALL NOT claim that registered behavior commitments were searched successfully

### Requirement: Plane ambiguity blocks unsafe consolidation
Preflight SHALL NOT choose one cross-plane owner solely from shared words when the primary behavior plane remains ambiguous.

#### Scenario: Download appears in all planes
- **WHEN** task terms match product, agent, and development commitments with no selected plane or typed relation path
- **THEN** preflight SHALL report separated plane candidates and an ambiguity finding
- **AND** downstream full-confidence work SHALL require a selected plane
