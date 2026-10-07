## ADDED Requirements

### Requirement: Current maps preserve the complete declared structure
The observed authority SHALL bind a current complete declared graph, retained-element inventory, groundings, source references and complete effective intent for an explicit scope. Executed traces SHALL establish coverage or consistency only and SHALL NOT define the graph denominator. Unobserved declared branches SHALL remain present with `not_run` coverage. A `native_check_contract` graph SHALL NOT supply `model_behavior` or software-architecture completeness.

#### Scenario: Rare declared branch was not executed
- **WHEN** the declared graph contains a branch absent from the episode traces
- **THEN** the current map retains the branch and reports its coverage as `not_run`
- **AND** any required unexecuted hard obligation remains blocked

#### Scenario: Trace-only map claims complete structure
- **WHEN** a current-map candidate uses observed traces as its structural denominator
- **THEN** observation acceptance is blocked with the exact declaration or denominator gap

### Requirement: Faithful observation is separate from required improvement
A faithful current map SHALL retain actual inefficient or duplicated paths and unresolved architectural objectives. Observation acceptance SHALL require exact source, declaration, intent, native hard-invariant, oracle, terminal-owner and cleanup evidence. Verified unfinished improvement alone SHALL NOT erase current facts or block faithful observation; it SHALL still block required improvement completion or release. Unknown gaps SHALL remain observation blockers.

#### Scenario: Current architecture faithfully records an unmet target
- **WHEN** current facts and all required observation evidence are verified but a required architectural target is unmet
- **THEN** the observed map can be accepted with the improvement gap visible
- **AND** required improvement completion and release remain blocked

#### Scenario: Hard failure is mislabeled improvement
- **WHEN** an upstream owner failed, an oracle failed, a hard invariant failed, or cleanup is unconfirmed
- **THEN** observation acceptance remains blocked and the failure cannot be reclassified as unfinished improvement

### Requirement: Architectural confidence respects independent software scope
Software-architecture confidence SHALL additionally require the current independent implementation inventory and reverse implementation-binding coverage for the claimed source boundary. A self-consistent declaration without that coverage SHALL license only `declared_model` or `scoped` confidence. Missing writers, methods, branches or current independent coverage SHALL NOT be hidden by equality of self-declared ids.

#### Scenario: Scoped declaration omits an independently discovered writer
- **WHEN** a declared graph is internally exact but independent current source coverage finds an omitted writer
- **THEN** whole-software confidence remains blocked with that writer visible
- **AND** the map retains its honest scoped claim boundary

### Requirement: Architecture reads consume authenticated current detail
An architecture read SHALL bind the same accepted head, revision, snapshot and selected current index to verified declared sources, compact results and immutable details. Missing or stale detail SHALL be visible as an architecture-confidence gap. Read SHALL execute zero owners, perform zero refreshes and writes, avoid historical-generation traversal and load only exact selected objects, required objective scope and typed neighbors. Persistent accepted index and shard fields SHALL remain unchanged.

#### Scenario: Selected result has no architecture detail
- **WHEN** read resolves a current result whose authenticated detail is missing
- **THEN** it reports `architecture_detail_missing` within the selected architecture projection
- **AND** it does not synthesize a graph, refresh a producer or rewrite accepted data



### Requirement: Software coverage read is authenticated within its frozen boundary
An immutable architecture detail SHALL carry original independent boundary/inventory/resolved manifest rows/binding report/registered source identities and prior terminal proof. Read SHALL authenticate accepted result-detail-subject identities and exact claimed/covered surface denominator, with zero scanners/owners/refreshes/writes. Scope evidence SHALL not contain its enclosing result fingerprint. Completeness SHALL be limited to complete_within_authenticated_frozen_boundary and keep accepted subject revision visible.

#### Scenario: Real writer is consistently omitted from model and bindings
- **WHEN** independent original inventory contains W1 and W2 while declaration and reverse binding retain only W1
- **THEN** W2 remains an exact model/owner coverage gap and whole-scope proof is denied

#### Scenario: New unregistered file was not observed
- **WHEN** W3 is added without changing recorded inputs
- **THEN** zero-scanner read retains only frozen-boundary as-of proof and reports live-file detection as NOT_OBSERVED
- **AND** changed registered manifest or source invalidates that proof

### Requirement: Architecture findings provide exact actionable references
Strict improvement pointers SHALL retain observed subjects, exact elements/contexts, current objectives, hard obligations, actual native callable/result selector/oracle_member_ids, binding/result/receipt identity and missing input/next owner. Guessed joins and noncurrent proof SHALL not license equivalence or completion. Public request and index/shard wire remain unchanged.

#### Scenario: Required architecture arrays exceed one response page
- **WHEN** large Unicode pointers and scope evidence require paging
- **THEN** each JSON plus newline is at most 8192 UTF-8 bytes and complete concatenation preserves every required reference without duplication or omission
