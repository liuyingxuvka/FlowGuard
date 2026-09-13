## MODIFIED Requirements

### Requirement: Garbage collection is plan-bound and recoverable before purge

Garbage collection SHALL first run a single lightweight storage audit that
counts paths and logical bytes without reading content or computing content
hashes. It SHALL then freeze an exact evidence plan from current audit
identity, SHALL quarantine only candidates that remain unreachable when the
plan is applied, and SHALL require a separate explicit purge of one exact
quarantine after current and pinned evidence still validate.

#### Scenario: Storage audit observes a large evidence tree

- **WHEN** the audit is invoked for routine budgeting
- **THEN** it reports role counts, byte totals, the largest bounded sample,
  and collectible/current/pinned/lease classes without reading payloads

#### Scenario: Current head changes after planning

- **WHEN** the evidence head, pins, or candidate fingerprint changes after a
  GC plan is created
- **THEN** apply rejects the stale plan and moves nothing

#### Scenario: Exact plan is applied

- **WHEN** every plan identity still matches and every candidate remains
  unreachable
- **THEN** apply moves only those candidates into the named quarantine and
  emits a receipt

#### Scenario: Purge target is not quarantined

- **WHEN** purge is asked to remove an active-store path or a path outside the
  exact quarantine
- **THEN** purge refuses and deletes nothing
