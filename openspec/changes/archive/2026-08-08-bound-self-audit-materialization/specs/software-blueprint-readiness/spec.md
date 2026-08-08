## ADDED Requirements

### Requirement: One governed observation can feed independent decisions
Within one blueprint build, source discovery SHALL produce one immutable observation bundle per provider input. Independent surface classification, implementation-denominator review, behavior compilation, and reduction analysis MAY consume that same observation, but each SHALL retain its own rules, findings, and result identity. Reusing the observation SHALL NOT reuse an old result or bypass a denominator check.

#### Scenario: Declaration and inventory inspect the same current file
- **WHEN** both declaration classification and implementation inventory require the same provider observation in one build
- **THEN** the provider SHALL observe and parse that file once for that build
- **AND** both consumers SHALL independently validate their complete obligations from the same immutable facts

#### Scenario: A later invocation sees changed content
- **WHEN** the file content or provider contract changes before a later build
- **THEN** the later build SHALL create a new observation and identity
- **AND** no invocation-local observation SHALL become a persistent cache authority

### Requirement: Large normalized reference views have one in-memory owner
One normalization invocation SHALL construct each complete logical reference view once and reuse that exact immutable value for its fingerprint, byte count, integrity checks, and physical projection. It SHALL NOT hold two independently reconstructed complete reference dictionaries for the same logical report.

#### Scenario: A behavior report contains many coverage edges
- **WHEN** the report is normalized into reference shards and shared objects
- **THEN** its complete normalized reference dictionary SHALL be produced once
- **AND** all downstream identity calculations SHALL consume that same value without changing canonical output

### Requirement: Affected shared objects are independently validated once
Affected-blueprint materialization SHALL compute the current fingerprint of every supplied shared object before accepting it. For a projection-declared base object, it SHALL compare that actual fingerprint with the declared fingerprint and fail on any difference. After successful validation, the exact computed fingerprint SHALL be reused in the final affected index; content-addressed objects created during the same invocation SHALL likewise be fingerprinted once and reused.

#### Scenario: A normalized object is current
- **WHEN** an affected-blueprint index materializes from a supplied object whose actual fingerprint matches the normalized projection
- **THEN** the materializer SHALL record that independently computed fingerprint in the final index
- **AND** it SHALL NOT hash the same immutable payload again during that invocation

#### Scenario: A supplied object drifts
- **WHEN** the supplied payload no longer matches its normalized projection fingerprint
- **THEN** materialization SHALL fail visibly after computing the actual payload fingerprint
- **AND** no declared fingerprint, cache, or fallback SHALL be accepted as a substitute for that check

### Requirement: Resource observation starts from one initialized current snapshot
Before any resource provider is observed, a blueprint builder SHALL obtain and validate the exact non-empty current observed-snapshot fingerprint. Every current resource observation created by that build SHALL bind its `subject_revision` to that same fingerprint. A missing snapshot identity SHALL block before observation; the builder SHALL NOT substitute an empty value, a later assignment, a source-file revision, or another authority lane.

#### Scenario: Current resources are observed for one blueprint build
- **WHEN** the builder has validated the current observed-snapshot fingerprint and begins resource observation
- **THEN** every current resource row SHALL carry that exact fingerprint as its subject revision
- **AND** resource observation SHALL NOT begin before the snapshot input exists

#### Scenario: Snapshot identity is missing
- **WHEN** the current model authority does not provide a non-empty observed-snapshot fingerprint
- **THEN** blueprint construction SHALL fail visibly before invoking the resource observer
- **AND** no empty, inferred, stale, or later-populated fingerprint SHALL enter the resource inventory

### Requirement: Statically finite dynamic selectors have one observed current contract
When a provider can derive a non-empty finite selector domain directly from current source structure, the self-blueprint SHALL materialize one exact dynamic-selector contract from that observation. The contract SHALL bind the exact operation, surface, effective owner, structure fingerprint, selector-source fingerprint, and sorted selector values. The authored blueprint definition SHALL NOT require or retain a second manual copy of the same mechanically derivable contract.

#### Scenario: A loop drives an attribute lookup from a finite literal domain
- **WHEN** current source proves every possible selector value for a dynamic operation
- **THEN** the provider SHALL emit one exact-current dynamic-selector contract for that operation
- **AND** the contract SHALL become stale automatically when the structure, selector source, owner, operation, or value set changes

#### Scenario: A selector domain is genuinely open
- **WHEN** the provider cannot derive a complete non-empty selector domain
- **THEN** the operation SHALL remain a visible implementation-inventory blocker unless source is made finite or one explicit exact allowance owns the bounded exceptional behavior
- **AND** no stale generated contract, empty value set, broad allowance, or authored fallback SHALL be accepted
## ADDED Requirements

### Requirement: Compact self-qualification exposes bounded actionable blocker classes
The compact self-qualification projection SHALL count actionable child findings by exact child report, finding code, and severity and SHALL include one bounded example for each emitted blocker class. It SHALL derive those summaries from already-materialized child findings without serializing a complete child report or rebuilding the blueprint.

#### Scenario: One upstream defect blocks several blueprint layers
- **WHEN** many child findings share one code and later readiness layers are blocked only by dependency order
- **THEN** compact output SHALL expose the shared child finding count and one bounded example
- **AND** an AI consumer SHALL NOT need a second full blueprint build merely to identify the upstream blocker class
