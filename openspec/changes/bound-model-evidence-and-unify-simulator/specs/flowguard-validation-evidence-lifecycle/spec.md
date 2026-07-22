## ADDED Requirements

### Requirement: Complete stream evidence has one logical owner
FlowGuard validation writers SHALL hash complete stdout/stderr bytes, store deterministic compressed objects by content identity, and expose separate logical and stored hashes, byte counts, media type, and relative object path. Parent and child summaries MUST NOT embed a second full copy of the stream or parsed payload.

#### Scenario: Two children have empty stderr
- **WHEN** two children in one run produce identical empty stderr streams
- **THEN** both descriptors reference the same content-addressed stored object

#### Scenario: Child payload is large
- **WHEN** a child stdout stream parses as a large JSON object
- **THEN** the child result records its fingerprint and bounded diagnostics while the complete object remains recoverable from the stream artifact

### Requirement: Terminal runs publish an explicit current head
A persistent evidence writer SHALL first durably write its terminal result and immutable run manifest, then atomically update one scope-local current-head record containing the run identity and terminal result fingerprint. Filesystem recency MUST NOT create current authority.

#### Scenario: New terminal failure replaces an older pass as latest observation
- **WHEN** a later terminal run completes with failure
- **THEN** the current head identifies that failed run while release pins may continue to preserve an earlier named pass

#### Scenario: Directory is newer but has no head binding
- **WHEN** an evidence directory has a newer modification time but no current-head or pin reference
- **THEN** audit does not infer that it is current

### Requirement: Evidence audit exposes lifecycle classes
Evidence audit SHALL be read-only and SHALL report current, release-pinned, collectible, legacy-unmanaged, quarantined, invalid, and incomplete runs with logical and stored byte totals.

#### Scenario: Historical result lacks a current run manifest
- **WHEN** audit finds an older FlowGuard result directory without the current lifecycle manifest
- **THEN** it reports the directory as legacy-unmanaged and does not silently rewrite or delete it

### Requirement: Garbage collection is plan-bound and recoverable before purge
Garbage collection SHALL freeze an exact plan from current audit identity, SHALL quarantine only candidates that remain unreachable when the plan is applied, and SHALL require a separate explicit purge of one exact quarantine after current and pinned evidence still validate.

#### Scenario: Current head changes after planning
- **WHEN** the evidence head, pins, or candidate fingerprint changes after a GC plan is created
- **THEN** apply rejects the stale plan and moves nothing

#### Scenario: Exact plan is applied
- **WHEN** every plan identity still matches and every candidate remains unreachable
- **THEN** apply moves only those candidates into the named quarantine and emits a receipt

#### Scenario: Purge target is not quarantined
- **WHEN** purge is asked to remove an active-store path or a path outside the exact quarantine
- **THEN** purge refuses and deletes nothing

### Requirement: Ordinary validation never performs persistent cleanup
Validation and simulator execution SHALL NOT automatically plan, quarantine, or purge prior persistent evidence. It MAY remove only its own unpublished temporary capture after a failed atomic write.

#### Scenario: Full validation succeeds repeatedly
- **WHEN** several persistent full validations complete
- **THEN** prior runs remain until an explicit lifecycle operation disposes them
