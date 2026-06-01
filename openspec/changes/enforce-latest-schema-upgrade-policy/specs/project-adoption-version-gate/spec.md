## MODIFIED Requirements

### Requirement: Project upgrade is explicit
FlowGuard SHALL provide a project upgrade helper that updates the managed
AGENTS block and project manifest to the currently installed FlowGuard version
only when the upgrade command is explicitly run. When the installed FlowGuard
version is newer than the project-recorded version, the upgrade helper SHALL
also scan existing FlowGuard artifacts, model evidence, tests, docs, and
guidance for known old shapes, deterministically upgrade safe cases, and report
blocked cases before broad confidence is claimed.

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
- **AND** it upgrades deterministic cases or reports blocked/manual-review
  cases without silently preserving old runtime compatibility

#### Scenario: Records-only upgrade is explicit
- **WHEN** `project-upgrade` runs in records-only mode
- **THEN** it updates only the managed AGENTS block, manifest, and adoption
  records
- **AND** it reports that artifact/model/test upgrade scanning was scoped out

#### Scenario: Manifest update does not replace validation
- **WHEN** project adoption or upgrade writes AGENTS and manifest files
- **THEN** the report states that adoption records and artifact upgrades do not
  replace executable model checks, tests, replay, or closure evidence
