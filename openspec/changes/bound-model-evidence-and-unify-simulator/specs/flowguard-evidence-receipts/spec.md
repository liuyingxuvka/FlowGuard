## ADDED Requirements

### Requirement: Evidence reachability is explicit
Repository evidence SHALL distinguish immutable run identity from mutable scope-local current heads and named release pins. A run is current or retained only through exact validated bindings; directory names and modification times MUST NOT provide authority.

#### Scenario: Current head references a changed result
- **WHEN** the result fingerprint no longer matches the current-head binding
- **THEN** the head is invalid and the run cannot support a current claim

### Requirement: Evidence disposal preserves receipt authority
Evidence lifecycle operations SHALL never mutate a retained receipt in place. Quarantine and purge receipts SHALL identify the exact audit, plan, candidate fingerprints, head/pin replay, moved or deleted paths, and claim boundary.

#### Scenario: Collectible run is quarantined
- **WHEN** an exact current GC plan is applied
- **THEN** the original run bytes move together without receipt rewriting and the quarantine receipt records their prior identities
