## MODIFIED Requirements

### Requirement: Latest-schema artifact upgrade
FlowGuard SHALL provide a deterministic upgrade review for older FlowGuard
artifacts, project records, reports, model evidence, docs, tests, and guidance
so recognized old shapes can be converted to the current schema without adding
long-lived runtime compatibility branches. A JSON artifact is owned only when
it is either an exact current registered `report`/`trace` envelope (unchanged,
no writer) or the exact complete historical bare behavior-ledger producer
shape from commit `56083c1e` (dedicated writer). Numeric version syntax, a name
prefix, a producer label, a scan path, a required-field subset, or a partial
ledger-like mapping MUST NOT independently grant FlowGuard write authority.

#### Scenario: Known old artifact upgrades to current shape
- **WHEN** an upgrade scan encounters a historical FlowGuard behavior ledger
  whose complete owned legacy shape matches its dedicated migration owner
- **AND** every row contains an explicit, valid upgrade-AI disposition for its
  current behavior plane and actor kind
- **THEN** the upgrade report records the original path, detected old shape,
  current replacement, and whether the item was changed
- **AND** the upgraded output equals the complete canonical mapping emitted by
  the current behavior-ledger serializer

#### Scenario: Missing semantic disposition blocks instead of guessing
- **WHEN** an exact historical behavior ledger lacks an explicit current
  behavior-plane or actor-kind disposition, or contains multiple historical
  primary path ids without one evidence-bound current choice
- **THEN** migration blocks without writing
- **AND** actor text, owner text, labels, commitment kinds, and runtime
  compatibility defaults are not used to guess the missing disposition

#### Scenario: Target-owned JSON shares generic markers
- **WHEN** an unregistered JSON mapping contains numeric `schema_version`,
  `created_by`, `payload`, a FlowGuard-looking type prefix, or a partial
  `ledger_id` and `commitments` shape
- **THEN** the mapping is outside FlowGuard's artifact migration authority
- **AND** apply mode does not serialize or modify it

#### Scenario: Unsupported registered envelope blocks instead of guessing
- **WHEN** an exact registered FlowGuard `report` or `trace` envelope has an
  old, future, namespaced, malformed, or otherwise unsupported shape without
  an evidence-bound migration rule
- **THEN** the upgrade report marks the item as blocked or manual-review
  required
- **AND** FlowGuard does not claim the artifact was upgraded

#### Scenario: Unsupported behavior-ledger envelope blocks instead of downgrading
- **WHEN** a declared behavior-ledger envelope has an old, future, malformed,
  extra-field, or otherwise non-canonical current shape
- **THEN** the upgrade report marks it blocked without writing
- **AND** the dedicated historical migrator is not applied to the envelope

#### Scenario: Full legacy field subset plus target fields is outside authority
- **WHEN** a JSON mapping contains every historical behavior-ledger field but
  adds a target-only top-level, row, or nested field
- **THEN** it does not match the exact `56083c1e` producer shape
- **AND** neither the scanner nor the public behavior-ledger migrator writes it

#### Scenario: Runtime path remains current-only
- **WHEN** current FlowGuard route review or report code executes after an
  upgrade scan
- **THEN** it consumes current-schema artifacts and current public API shapes
- **AND** it does not accept old fields solely for backward compatibility

#### Scenario: Bundled behavior-ledger template is an exact current producer
- **WHEN** FlowGuard materializes its public behavior-commitment-ledger template
- **THEN** the bundled JSON envelope equals the complete mapping emitted by the
  current behavior-ledger serializer
- **AND** the current runtime loader accepts it without filling omitted default
  fields or consulting a compatibility reader
