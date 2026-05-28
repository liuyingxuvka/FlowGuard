# project-adoption-version-gate Specification

## Purpose
TBD - created by archiving change add-project-adoption-version-gate. Update Purpose after archive.
## Requirements
### Requirement: Project adoption writes durable local rules
FlowGuard SHALL provide a project adoption helper that writes or updates a
target repository's FlowGuard `AGENTS.md` managed block without deleting
existing project rules.

#### Scenario: Missing AGENTS file is created
- **WHEN** `project-adopt` runs in a target repository without `AGENTS.md`
- **THEN** it creates `AGENTS.md` with a managed FlowGuard project rules block
- **AND** the block includes the FlowGuard GitHub repository URL

#### Scenario: Existing AGENTS content is preserved
- **WHEN** `project-adopt` runs in a target repository with existing `AGENTS.md`
  content outside FlowGuard markers
- **THEN** it preserves that content
- **AND** it inserts or replaces only the FlowGuard managed block

### Requirement: Project adoption records FlowGuard versions
FlowGuard SHALL record the adopted package version, schema version, repository
URL, and verification metadata in `.flowguard/project.toml`.

#### Scenario: Manifest records current toolchain
- **WHEN** `project-adopt` runs with an importable FlowGuard package
- **THEN** `.flowguard/project.toml` records the package version, schema
  version, repository URL, last verification timestamp, and managed AGENTS path

#### Scenario: Package version and schema version remain separate
- **WHEN** a project manifest is written
- **THEN** the package release version and FlowGuard schema version are written
  as separate fields

### Requirement: Project audit detects version drift
FlowGuard SHALL provide a read-only project audit that compares the installed
FlowGuard package with the project manifest and reports missing, older, newer,
or unknown version states.

#### Scenario: Installed package is older than project record
- **WHEN** the installed FlowGuard package version is lower than the manifest's
  adopted package version
- **THEN** the audit reports a blocked finding and recommends upgrading the
  local toolchain before claiming FlowGuard confidence

#### Scenario: Installed package is newer than project record
- **WHEN** the installed FlowGuard package version is higher than the manifest's
  adopted package version
- **THEN** the audit reports a project upgrade finding
- **AND** it does not silently update the manifest during read-only audit

### Requirement: Project upgrade is explicit
FlowGuard SHALL provide a project upgrade helper that updates the managed
AGENTS block and project manifest to the currently installed FlowGuard version
only when the upgrade command is explicitly run.

#### Scenario: Upgrade updates project record
- **WHEN** `project-upgrade` runs with an installed package version newer than
  the manifest
- **THEN** it updates the manifest package version and schema version
- **AND** it records that model/test evidence may need rerun before broad
  confidence

#### Scenario: Manifest update does not replace validation
- **WHEN** project adoption or upgrade writes AGENTS and manifest files
- **THEN** the report states that adoption records do not replace executable
  model checks, tests, replay, or closure evidence

### Requirement: Adoption helper is standard-library-only
FlowGuard SHALL keep project adoption helpers dependency-free and safe for
ordinary repository use.

#### Scenario: Helper imports without optional packages
- **WHEN** the project adoption helper is imported
- **THEN** it uses only Python standard library modules and FlowGuard's own
  existing public constants/helpers

