## MODIFIED Requirements

### Requirement: Complete stream evidence has one logical owner

FlowGuard validation writers SHALL store complete stdout/stderr as one deterministic content-addressed object only when the native owner explicitly requires complete streams or the current failure policy retains a debug bundle. Successful runs without that requirement SHALL publish a bounded tail and structured diagnostics. Parent and child summaries MUST NOT embed a second full copy of any stream or parsed payload.

#### Scenario: Two children have empty stderr

- **WHEN** two children in one run produce identical empty stderr streams and complete streams are required
- **THEN** both descriptors SHALL reference the same content-addressed stored object

#### Scenario: Successful child has no full-stream requirement

- **WHEN** a child succeeds and its native contract does not require complete stdout/stderr
- **THEN** the result SHALL retain only bounded diagnostics and a terminal identity
- **AND** it SHALL not persist an unbounded full stream by default

#### Scenario: Child payload is large

- **WHEN** a child stdout stream parses as a large JSON object
- **THEN** the child result SHALL record its fingerprint and bounded diagnostics while any required complete object remains recoverable from one stream artifact

## ADDED Requirements

### Requirement: Ordinary validation disposes unreachable evidence after publication

Validation and simulator execution SHALL publish the terminal result and current head before classifying prior runs. After the head and pins are replayed, unreachable unpublished work and unpinned collectible runs SHALL be quarantined and purged within the same lifecycle operation. Current, explicitly pinned, and actively leased evidence SHALL never be deleted. Ordinary validation SHALL not perform an unbounded forensic byte scrub.

#### Scenario: Full validation succeeds repeatedly

- **WHEN** several persistent full validations complete and older runs are not current, pinned, or actively leased
- **THEN** the lifecycle operation SHALL dispose those unreachable runs and report released bytes

#### Scenario: Current head changes after disposal planning

- **WHEN** the evidence head, pins, leases, or candidate reference identity changes after disposal planning
- **THEN** disposal SHALL stop, move nothing further, and report a stale lifecycle plan

#### Scenario: Current or pinned evidence is targeted

- **WHEN** a disposal candidate is current, pinned, actively leased, outside the exact evidence root, or a reparse point
- **THEN** disposal SHALL refuse that candidate and delete nothing
