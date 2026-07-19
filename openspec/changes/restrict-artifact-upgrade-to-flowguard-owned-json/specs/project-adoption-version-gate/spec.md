## MODIFIED Requirements

### Requirement: Project upgrade is explicit
FlowGuard SHALL provide a project upgrade helper that updates the managed
AGENTS block and project manifest to the currently installed FlowGuard version
only when the upgrade command is explicitly run. When the installed FlowGuard
version is newer than the project-recorded version, the upgrade helper SHALL
scan existing FlowGuard artifacts, model evidence, tests, docs, and guidance
for known old shapes. It SHALL modify JSON only when the complete bare
historical behavior-ledger producer shape from commit `56083c1e` matches the
dedicated migration owner. Exact current registered `report`/`trace` envelopes
are observed without serialization; unsupported declared envelopes block.
`project-upgrade` SHALL preserve every unknown or target-owned JSON file
byte-for-byte before broad confidence is claimed.

#### Scenario: Upgrade updates project record
- **WHEN** `project-upgrade` runs with an installed package version newer than
  the manifest
- **THEN** it updates the manifest package version and schema version
- **AND** it records that model/test evidence may need rerun before broad
  confidence

#### Scenario: Older adopted repository triggers upgrade scan
- **WHEN** `project-upgrade` runs in a repository whose manifest records an
  older FlowGuard package version than the installed package
- **THEN** it scans known FlowGuard records, artifacts, model evidence, tests,
  docs, and guidance for old schema or old API shapes
- **AND** it upgrades deterministic registered cases or reports
  blocked/manual-review registered cases without silently preserving old
  runtime compatibility

#### Scenario: Numeric schema field does not establish ownership
- **WHEN** a scanned target-owned JSON mapping contains an integer or numeric
  string `schema_version` but does not declare an exact registered FlowGuard
  artifact type
- **THEN** `project-upgrade` and `artifact-upgrade --apply` leave its bytes and
  content hash unchanged
- **AND** neither its path, a `flowguard`-looking prefix, `created_by`, nor an
  envelope-like `payload` grants migration authority

#### Scenario: Typed FlowGuard artifact migrates in the same project
- **WHEN** the same project contains a complete historical FlowGuard behavior
  ledger and an unknown target-owned JSON artifact
- **THEN** `project-upgrade` directly migrates the ledger through its dedicated
  typed migration owner to the current schema
- **AND** the upgrade-AI has supplied explicit current plane/actor dispositions
  for every historical row before the single write
- **AND** the target-owned artifact remains byte-identical
- **AND** no fallback, dual reader, compatibility parser, or target-specific
  path exclusion is used

#### Scenario: Legacy lookalike with target fields stays outside ownership
- **WHEN** a target-owned JSON mapping contains every historical
  behavior-ledger field plus a target-only top-level, row, or nested field
- **THEN** `project-upgrade` leaves its bytes and content hash unchanged
- **AND** the exact historical shape owner is not widened to accept it

#### Scenario: Records-only upgrade is explicit
- **WHEN** `project-upgrade` runs in records-only mode
- **THEN** it updates only the managed AGENTS block, manifest, and adoption
  records
- **AND** it reports that artifact/model/test upgrade scanning was scoped out

#### Scenario: Manifest update does not replace validation
- **WHEN** project adoption or upgrade writes AGENTS and manifest files
- **THEN** the report states that adoption records and artifact upgrades do not
  replace executable model checks, tests, replay, or closure evidence
