# project-adoption-version-gate Specification

## Purpose
This capability defines how FlowGuard projects verify installed package version, schema version, managed project records, and direct current-replacement readiness before claiming FlowGuard confidence.
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
- **THEN** the audit reports that the project record is non-current and recommends explicit `project-adopt`
- **AND** it does not silently update the manifest during read-only audit

### Requirement: Project adoption directly writes the current record
FlowGuard SHALL use `project-adopt` as the only writing project-record command. It SHALL accept the current project inputs, replace the managed AGENTS block and project manifest with the one current shape, and reject former project/runtime shapes rather than reading, converting, migrating, aliasing, or preserving them as a success path.

#### Scenario: Adoption replaces a non-current project record
- **WHEN** `project-adopt` runs with a current installed package and a non-current managed record
- **THEN** it writes the current manifest package version and schema version directly
- **AND** it records the exact minimum affected model/test revalidation without scanning or converting former runtime shapes

#### Scenario: Former project shape cannot be a write input
- **WHEN** only a former project/runtime shape is available
- **THEN** adoption remains blocked until the caller supplies complete current inputs
- **AND** no migration, upgrade, converter, records-only, or compatibility route is offered

#### Scenario: Manifest update does not replace validation
- **WHEN** project adoption writes AGENTS and manifest files
- **THEN** the report states that adoption records do not
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
- **AND** project adoption, audit, import, and CLI commands MUST be
  described as project-record or check-execution commands, not as the skill
  install surface

### Requirement: Package metadata does not prove skill setup
FlowGuard project adoption/version guidance SHALL not treat package metadata as
proof that AI-agent skills are available.

#### Scenario: Package metadata is current but skills are missing
- **WHEN** package version, schema version, or project audit passes
- **AND** `.agents/skills/` is not available to the AI agent
- **THEN** FlowGuard skill setup MUST be reported as incomplete or scoped

### Requirement: Managed Adoption Semantic Parity
Project audit SHALL compare the current managed `AGENTS.md` block with the block produced by the installed generator using stable rule identifiers and normalized content. It SHALL also compare package version, project-manifest version, and rendered adoption version. Markers alone MUST NOT satisfy adoption health.

#### Scenario: Managed block has stale version
- **WHEN** package and manifest report 0.53.1 but the managed block records 0.53.0
- **THEN** project audit fails with a rendered-version-mismatch finding

#### Scenario: Current governance rule is missing
- **WHEN** the rendered block omits a required BCL, PPA, path-sensitive, current-authority-only, or default-replacement rule
- **THEN** project audit fails with the missing stable rule identifiers

### Requirement: Project audit is the non-mutating currentness preview
Project audit SHALL compute manifest differences, managed-block semantic differences, suite findings, affected current components, and minimum revalidation without modifying any repository file or adoption log.

#### Scenario: Audit previews stale adoption repair
- **WHEN** project audit runs with `--json` against a stale managed block
- **THEN** it reports the required direct current replacement and the repository tree remains byte-identical

### Requirement: Adoption Must Not Weaken Governance
A writing project adoption MUST refuse to proceed when the proposed generated block loses a rule present in the current required rule set, when the installed engine is older than the project record, or when suite inventory validation is unresolved.

#### Scenario: Generator would delete PPA rules
- **WHEN** the proposed generated block lacks the current Primary Path Authority rule
- **THEN** adoption exits nonzero before writing and reports a governance-regression blocker

#### Scenario: Installed engine is older
- **WHEN** the installed engine version is lower than the project manifest version
- **THEN** adoption exits nonzero without changing the project

### Requirement: Adoption Decision Evidence
Project audit and adoption results SHALL include canonical status, versions, inventory hash, managed-block semantic hash, findings, skipped steps, required revalidation, and claim boundary. A log entry MAY be written only for a real audit or writing adoption, and logging MUST NOT convert a failed check into pass.

#### Scenario: Successful writing adoption completes
- **WHEN** an approved writing adoption finishes and post-write audit passes
- **THEN** adoption logs record the before/after hashes, versions, checks, and remaining claim boundary

### Requirement: Generated revalidation commands are project-relative
FlowGuard SHALL generate project-adoption minimum and required executable revalidation commands that are owned by the installed FlowGuard package, run from the target project root, and do not require FlowGuard source-repository files. Generated commands persisted in human adoption logs MUST NOT embed the resolved absolute target path. A human-only revalidation instruction MAY remain as prose but MUST NOT be represented as a successfully validated executable command.

#### Scenario: Report recommends an executable portable command
- **WHEN** project adoption or audit builds a report for a valid target repository that does not contain the FlowGuard source `scripts/` directory
- **THEN** its generated executable revalidation command uses `python -m flowguard project-audit --root . --json`
- **AND** the command succeeds when executed from that target project
- **AND** the returned report contains passing current project-adoption and skill-suite status

#### Scenario: Report excludes source-layout-only commands
- **WHEN** project adoption or audit builds required revalidation guidance for an ordinary adopted target
- **THEN** no generated executable command requires `python scripts/` or another FlowGuard source-repository-relative path
- **AND** the existing package-owned project audit remains the single target-project audit authority

#### Scenario: Human adoption log preserves privacy
- **WHEN** a writing project-adoption action records its next actions in `docs/flowguard_adoption_log.md`
- **THEN** the Markdown log contains the package-owned project-relative revalidation command
- **AND** it does not contain the target repository's resolved absolute path through those next actions

### Requirement: Project adoption consumes strict mixed-root suite evidence
Project audit and project adoption SHALL accept an ownership-backed mixed skill
root when the canonical FlowGuard suite is complete, and SHALL continue to
block when canonical membership or ownership evidence is unresolved.

#### Scenario: Project audit sees a valid mixed root
- **WHEN** a target project contains a passing canonical seventeen-member
  FlowGuard suite with valid distribution ownership evidence
- **AND** unrelated non-FlowGuard skills are co-located in the skill root
- **THEN** project audit does not report
  `suite_inventory_unresolved` for those unrelated skills

#### Scenario: Project adoption sees a valid mixed root
- **WHEN** explicit project adoption runs against a valid ownership-backed mixed
  root
- **AND** all other current adoption gates pass
- **THEN** adoption may write the current project records
- **AND** it preserves the unrelated skill directories

#### Scenario: Mixed root contains a missing or fake FlowGuard member
- **WHEN** a declared FlowGuard member is missing or an undeclared
  FlowGuard-reserved member is present
- **THEN** project adoption remains blocked by
  `suite_inventory_unresolved`
- **AND** no project record is written merely because unrelated skills were
  classified separately
