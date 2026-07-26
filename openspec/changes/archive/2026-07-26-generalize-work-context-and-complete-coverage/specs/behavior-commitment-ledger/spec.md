## ADDED Requirements

### Requirement: Expected behavior-source inventory is derived independently
Before claiming broad behavior coverage, the system SHALL derive one immutable expected behavior-source inventory from the declared project boundary and the current native source inventories, independently of Behavior Commitment Ledger rows and caller-selected candidates. The expected inventory SHALL record its boundary, revision, fingerprint, exact item identities, source roles, source kinds, content references, and native owner references.

#### Scenario: A source is absent from an otherwise green ledger
- **WHEN** the independent expected inventory contains an in-scope item that is absent from the ledger reconciliation
- **THEN** broad behavior coverage SHALL remain blocked and SHALL identify the missing expected item

#### Scenario: An expected source changes after reconciliation
- **WHEN** the identity, content, role, or native owner of an expected source item changes
- **THEN** the previous reconciliation SHALL become stale and SHALL NOT support a current coverage claim

### Requirement: Every expected item has exactly one coverage disposition
The system SHALL reconcile every item in the expected behavior-source inventory with exactly one disposition: `modeled`, `delegated`, or `scoped`. A `modeled` item SHALL reference its Behavior Commitment, exactly one primary owner model, and current evidence. A `delegated` item SHALL reference exactly one native owner inventory, a typed delegation relation, and current native evidence. A `scoped` item SHALL record its scope owner, reason, and validation boundary. Missing, duplicate, or conflicting dispositions SHALL block broad coverage.

#### Scenario: One expected item has no disposition
- **WHEN** an expected item is present in the independent inventory but has no modeled, delegated, or scoped disposition
- **THEN** the reconciliation SHALL fail and SHALL report that exact item as uncovered

#### Scenario: One expected item is claimed twice
- **WHEN** two successful dispositions claim the same expected item
- **THEN** the reconciliation SHALL fail instead of accepting two independent success paths

#### Scenario: A specialist-owned item is delegated
- **WHEN** a UI, field, provider, or other specialist inventory remains the native semantic owner of an expected item
- **THEN** the ledger SHALL preserve that ownership through a typed delegated disposition and SHALL NOT recreate the specialist's classification

### Requirement: Source roles and normative conflicts remain explicit
The system SHALL preserve the role and authority lane of every expected source, including normative requirements, observed behavior, generated inventories, and contextual work artifacts. It SHALL detect and expose incompatible normative sources and normative-to-observed mismatches instead of silently choosing the last or most convenient source.

#### Scenario: Two normative sources disagree
- **WHEN** two current normative sources declare incompatible behavior for the same business intent
- **THEN** the ledger SHALL record a visible conflict and SHALL block a singular current commitment until the conflict has one owned disposition

#### Scenario: Observed behavior disagrees with the normative source
- **WHEN** current observed behavior differs from the selected normative commitment
- **THEN** the system SHALL preserve both roles, route the mismatch through the existing miss or repair owner, and SHALL NOT treat the observed behavior as an implicit normative replacement
