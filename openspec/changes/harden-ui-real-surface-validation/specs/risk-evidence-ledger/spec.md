## ADDED Requirements

### Requirement: Final UI confidence consumes real-surface and implementation evidence
Risk Evidence Ledger SHALL require broad UI done, release, or full-confidence
claims to consume current observed-surface inventory, UI implementation
validation, functional-chain, MATLAB baseline semantics when relevant, and
final done-claim review evidence.

#### Scenario: Ledger has current UI evidence
- **WHEN** a broad UI claim has current passing real-surface inventory,
  implementation validation, functional-chain, and done-claim evidence
- **THEN** the risk ledger may support full UI confidence if no other in-scope
  risk gate blocks

#### Scenario: Ledger lacks UI implementation validation
- **WHEN** a broad UI claim lacks current `UIImplementationValidation`
- **THEN** the risk ledger blocks or scopes the claim even if labels, APIs, or
  static tests exist

#### Scenario: Planned evidence cannot support ledger confidence
- **WHEN** UI evidence is marked planned, not-run, running, stale, skipped, or
  progress-only
- **THEN** the risk ledger cannot count it as passing evidence
