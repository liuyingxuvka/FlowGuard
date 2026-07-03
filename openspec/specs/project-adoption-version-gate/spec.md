# project-adoption-version-gate Specification

## Purpose
This capability defines how FlowGuard projects verify installed package version, schema version, managed project records, and upgrade readiness before claiming FlowGuard confidence.
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

### Requirement: Adoption helper is standard-library-only
FlowGuard SHALL keep project adoption helpers dependency-free and safe for
ordinary repository use.

#### Scenario: Helper imports without optional packages
- **WHEN** the project adoption helper is imported
- **THEN** it uses only Python standard library modules and FlowGuard's own
  existing public constants/helpers

### Requirement: Minimal CI protects release-critical gates
FlowGuard SHALL keep a minimal GitHub Actions workflow for push and pull
request checks that covers install, project adoption, OpenSpec strict
validation, self-maintenance model checks, and focused unit tests.

#### Scenario: CI covers release-critical checks
- **WHEN** code is pushed or proposed through a pull request
- **THEN** CI runs editable install, project audit, OpenSpec strict validation,
  self-maintenance model checks, and focused unit tests before a release claim
  relies on the branch

### Requirement: Shadow workspace sync helper
FlowGuard SHALL provide a tracked shadow sync helper that can copy complete source sets into a shadow workspace, optionally refresh editable install metadata, and verify import path, package version, schema version, and a named helper in the target workspace.

#### Scenario: Shadow verification succeeds
- **WHEN** the shadow sync helper runs with verification enabled after copying source sets
- **THEN** it reports the target import path, metadata version, schema version, and helper availability

#### Scenario: Shadow verification fails
- **WHEN** the target workspace import path, package version, schema version, or helper availability does not match expectations
- **THEN** the helper exits non-zero and reports the mismatched field

### Requirement: Project integration separates skill setup from check commands
Project integration guidance SHALL separate AI skill-suite setup from executable
check command setup.

#### Scenario: Target project integration is read
- **WHEN** a user or agent reads `docs/project_integration.md`
- **THEN** it MUST first explain how the target agent can access the FlowGuard
  skill suite
- **AND** project adoption, audit, upgrade, import, and CLI commands MUST be
  described as project-record or check-execution commands, not as the skill
  install surface

### Requirement: Package metadata does not prove skill setup
FlowGuard project adoption/version guidance SHALL not treat package metadata as
proof that AI-agent skills are available.

#### Scenario: Package metadata is current but skills are missing
- **WHEN** package version, schema version, or project audit passes
- **AND** `.agents/skills/` is not available to the AI agent
- **THEN** FlowGuard skill setup MUST be reported as incomplete or scoped

