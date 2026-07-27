## ADDED Requirements

### Requirement: Ledger mode controls discovery breadth
Behavior Commitment Ledger discovery SHALL derive broad historical source
inventory only for `bootstrap_ledger` and `coverage_gap_backfill`. Existing
project add, change, remove/replace, and model-miss modes SHALL default to the
affected commitments and explicitly admitted source mappings.

#### Scenario: Existing behavior changes
- **WHEN** mode is `change_behavior` and the affected commitment and source
  identities are known
- **THEN** inventory SHALL remain bounded to the affected closure and SHALL NOT
  scan every historical source merely because broad-confidence fields exist

#### Scenario: Coverage gap is being backfilled
- **WHEN** mode is `coverage_gap_backfill`
- **THEN** the ledger SHALL require broad independent discovery and preserve
  every expected item disposition

#### Scenario: Mode is omitted for an existing ledger
- **WHEN** a current non-empty ledger is reviewed without an explicit mode
- **THEN** FlowGuard SHALL infer an affected existing-project review or block
  ambiguity and SHALL NOT silently select bootstrap-wide discovery
