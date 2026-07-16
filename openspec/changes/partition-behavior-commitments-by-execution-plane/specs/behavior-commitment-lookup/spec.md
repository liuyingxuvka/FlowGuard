## ADDED Requirements

### Requirement: Lookup filters by behavior plane before similarity
FlowGuard SHALL provide a deterministic commitment lookup that selects or reports one primary behavior plane before text similarity can produce primary hits.

#### Scenario: Agent operation query excludes product instructions
- **WHEN** an `agent_operation` query contains a word also used by a `product_runtime` commitment
- **THEN** only same-plane commitments MAY appear as primary hits
- **AND** the product commitment MAY appear only through a typed relation as related context

#### Scenario: Ambiguous plane remains separated
- **WHEN** a query cannot select one primary plane with sufficient caller context
- **THEN** lookup SHALL report plane ambiguity and separate plane candidates
- **AND** SHALL NOT merge those candidates into one primary instruction list

### Requirement: Lookup results are explainable and freshness-bound
Each lookup report SHALL expose its status, selected or ambiguous plane, primary hits, typed related hits, match reasons, owner model ids, and canonical ledger fingerprint.

#### Scenario: Exact operational error signature matches
- **WHEN** a query error signature exactly matches a commitment lookup binding
- **THEN** the hit SHALL identify the matching field and reason
- **AND** SHALL expose the commitment's primary owner model

#### Scenario: Ledger is missing or stale
- **WHEN** the canonical ledger cannot be loaded or its evidence is stale for the requested claim
- **THEN** lookup SHALL return an explicit fallback or blocked status and reason
- **AND** SHALL NOT claim a complete behavior lookup

### Requirement: Lookup uses one canonical ledger authority
The lookup library SHALL build an in-memory index from the canonical Behavior Commitment Ledger and SHALL NOT require a second persisted lookup database.

#### Scenario: Ledger edit changes lookup identity
- **WHEN** canonical ledger content changes
- **THEN** the next report SHALL carry a different ledger fingerprint
- **AND** evidence bound to the previous fingerprint SHALL be stale

### Requirement: CLI and Python API share lookup semantics
FlowGuard SHALL expose a read-only `behavior-commitment-query` command that calls the same lookup implementation as Existing Model Preflight.

#### Scenario: CLI JSON query succeeds
- **WHEN** a caller supplies a project root, task text, optional plane, and canonical terms with `--json`
- **THEN** the command SHALL return the same primary/related grouping and match reasons as the Python API

#### Scenario: Query command is not a route
- **WHEN** the CLI command is registered
- **THEN** FlowGuard SHALL keep it inside the existing BCL/preflight API ownership
- **AND** SHALL NOT add a new FlowGuard route id

### Requirement: Lookup does not force universal execution
Commitment lookup SHALL provide model discovery and typed context without becoming a universal runtime executor or mandatory gate for trivial operations.

#### Scenario: Trivial preflight is skipped
- **WHEN** Existing Model Preflight records its existing trivial-task skip decision
- **THEN** commitment lookup MAY remain `not_applicable`
- **AND** no synthetic failure SHALL be created solely because lookup did not run
