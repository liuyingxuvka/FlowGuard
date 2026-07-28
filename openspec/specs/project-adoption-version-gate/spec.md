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
FlowGuard project adoption and version guidance SHALL NOT treat package
metadata, an author checkout, or a directory name as proof that AI-agent skills
are available. Ordinary project audit and upgrade SHALL load the single
package-owned consumer authority and independently compare its exact member and
file identities with the installed global consumer projection and distribution
ownership manifest. The author source tree and its maintenance state SHALL NOT
be required for that currentness decision.

#### Scenario: Package metadata is current but skills are missing
- **WHEN** package version, schema version, or project audit records are current
- **AND** one or more authority-declared consumer skills or files are absent
  from the installed global projection
- **THEN** FlowGuard skill setup MUST be reported as incomplete or scoped
- **AND** package metadata, a project-local directory, or an author checkout
  cannot substitute for the missing consumer projection

#### Scenario: Author workspace is unavailable
- **WHEN** the installed package authority and installed global consumer
  projection are exact and current
- **AND** no author checkout, project-local `.agents/skills/` tree, SkillGuard
  registry, or author receipt store is available
- **THEN** ordinary project audit and upgrade may validate consumer currentness
  without reporting an author-dependency defect

### Requirement: Managed Adoption Semantic Parity
Project audit SHALL compare the current managed `AGENTS.md` block with the block produced by the installed generator using stable rule identifiers and normalized content. It SHALL also compare package version, project-manifest version, and rendered adoption version. Markers alone MUST NOT satisfy adoption health.

#### Scenario: Managed block has stale version
- **WHEN** package and manifest report 0.53.1 but the managed block records 0.53.0
- **THEN** project audit fails with a rendered-version-mismatch finding

#### Scenario: Current governance rule is missing
- **WHEN** the rendered block omits a required BCL, PPA, path-sensitive, latest-schema-first, or default-replacement rule
- **THEN** project audit fails with the missing stable rule identifiers

### Requirement: Non-Mutating Upgrade Preview
Project upgrade SHALL provide a dry-run mode that computes proposed manifest changes, managed-block semantic differences, suite findings, affected artifacts, and minimum revalidation without modifying any repository file or adoption log.

#### Scenario: Dry-run previews stale adoption repair
- **WHEN** project upgrade runs with `--dry-run --json` against a stale managed block
- **THEN** it reports the proposed semantic changes and the repository tree remains byte-identical

### Requirement: Upgrade Must Not Weaken Governance
A writing project upgrade MUST refuse to proceed when the proposed generated block loses a rule present in the current required rule set, when the installed engine is older than the project record, or when suite inventory validation is unresolved.

#### Scenario: Generator would delete PPA rules
- **WHEN** the proposed generated block lacks the current Primary Path Authority rule
- **THEN** the upgrade exits nonzero before writing and reports a governance-regression blocker

#### Scenario: Installed engine is older
- **WHEN** the installed engine version is lower than the project manifest version
- **THEN** the upgrade exits nonzero without changing the project

### Requirement: Adoption Decision Evidence
Project audit and upgrade results SHALL include canonical status, versions, inventory hash, managed-block semantic hash, findings, skipped steps, required revalidation, and claim boundary. A log entry MAY be written only for a real audit or writing upgrade, and logging MUST NOT convert a failed check into pass.

#### Scenario: Successful writing upgrade completes
- **WHEN** an approved writing upgrade finishes and post-write audit passes
- **THEN** adoption logs record the before/after hashes, versions, checks, and remaining claim boundary

### Requirement: Generated revalidation commands are project-relative
FlowGuard SHALL generate project-adoption minimum and required revalidation commands relative to the target project root. Generated commands persisted in human adoption logs MUST NOT embed the resolved absolute target path.

#### Scenario: Report recommends portable commands
- **WHEN** project adoption, audit, or upgrade builds a report for any target repository
- **THEN** its generated audit and suite-verification commands use `--root .`
- **AND** those generated commands do not contain the resolved absolute target root

#### Scenario: Human adoption log preserves privacy
- **WHEN** a writing project-adoption action records its next actions in `docs/flowguard_adoption_log.md`
- **THEN** the Markdown log contains the project-relative revalidation commands
- **AND** it does not contain the target repository's resolved absolute path through those next actions

### Requirement: Project adoption consumes strict mixed-root suite evidence
Project audit and project upgrade SHALL derive the canonical FlowGuard
consumer member and file inventory only from the package-owned
`flowguard/consumer-suite-authority.json`. They SHALL compare that exact
authority with the installed global skills root and distribution ownership
manifest, accept unrelated non-FlowGuard skills as outside the claim boundary,
and block when canonical membership, file identity, or ownership evidence is
unresolved. They SHALL NOT repeat a fixed member list or consume an author-side
suite map as runtime authority.

#### Scenario: Project audit sees a valid mixed root
- **WHEN** package authority and the installed global FlowGuard projection
  have exact member, file, and ownership parity
- **AND** unrelated non-FlowGuard skills are co-located in the skill root
- **THEN** project audit does not report
  `suite_inventory_unresolved` for those unrelated skills
- **AND** its passing claim is bounded to the authority-declared FlowGuard
  projection

#### Scenario: Project upgrade sees a valid mixed root
- **WHEN** explicit project upgrade runs against the exact package-authority,
  installed-projection, and ownership-manifest identity set
- **AND** all other upgrade gates pass
- **THEN** the upgrade may write only the target project's current managed
  records
- **AND** it preserves unrelated skill directories and writes no author state

#### Scenario: Mixed root contains a missing or fake FlowGuard member
- **WHEN** an authority-declared FlowGuard member or required file is missing
  or an undeclared FlowGuard-reserved member is present
- **THEN** project upgrade remains blocked by
  `suite_inventory_unresolved`
- **AND** no project record is written merely because unrelated skills were
  classified separately

### Requirement: Project adoption audits model authority
Project adoption SHALL validate the sole observed-head pointer, immutable
snapshot fingerprint, snapshot subject revision, and declared coverage status
in addition to package, schema, skill-suite, and rendered project records.

#### Scenario: Package versions match but snapshot is stale
- **WHEN** source, installed package, and project record versions match but the observed snapshot names another software revision
- **THEN** project audit fails model-authority parity and does not claim current FlowGuard confidence

### Requirement: Version identities are never conflated
Project adoption SHALL report source, project record, installed package,
installed skills, snapshot, Git commit, tag, and release identities separately.

#### Scenario: A historical folder has an older project record
- **WHEN** an inactive historical checkout retains an older record
- **THEN** audit reports that checkout as historical or stale without treating it as the active installed authority

### Requirement: Managed adoption guidance uses the provider-neutral work-context rule
Generated and upgraded project guidance SHALL describe external requirements, plans, designs, tasks, and status through provider-neutral WorkContext and generic artifact roles. It SHALL NOT identify OpenSpec or any other provider as the sole or default provider, and it SHALL preserve standalone FlowGuard operation when no provider is selected. The retired provider-specific SpecContext rule SHALL be replaced directly without a compatibility alias, dual managed rule, or fallback execution path.

#### Scenario: A project uses a non-OpenSpec provider
- **WHEN** a project declares Spec Kit, Superpowers, a declared-file profile, or another registered provider
- **THEN** project audit SHALL accept the same current WorkContext contract without requiring OpenSpec artifacts or commands

#### Scenario: A project uses no external provider
- **WHEN** no WorkContext provider is configured for a project
- **THEN** the version gate SHALL keep normal FlowGuard adoption valid and SHALL NOT synthesize an implicit provider

#### Scenario: Retired provider-specific guidance remains
- **WHEN** managed project guidance still contains the retired SpecContext execution, receipt, or OpenSpec-default rule after upgrade
- **THEN** project audit SHALL report semantic drift and SHALL NOT treat the adoption projection as current

### Requirement: Managed adoption guidance exposes complete coverage gates
Current managed guidance SHALL state that broad behavior coverage depends on an independently derived expected inventory, exact `modeled`, `delegated`, or `scoped` disposition for every expected item, and current native UI and field inventory projections where those surfaces are in scope. The project audit SHALL compare the managed semantic rule and declared record identity but SHALL NOT execute a WorkContext provider or convert provider status into validation evidence.

#### Scenario: Adoption guidance omits the independent inventory gate
- **WHEN** a project's managed guidance permits broad coverage from caller-selected ledger rows alone
- **THEN** project audit SHALL report the coverage rule as stale or incomplete

#### Scenario: Provider status is present during project audit
- **WHEN** a provider reports a completed proposal, plan, design, or task list
- **THEN** project audit SHALL treat the status as contextual metadata only and SHALL NOT mark FlowGuard checks, models, tests, or evidence as passed

### Requirement: Coverage inventory identities participate in project freshness
When a project declares behavior, UI, field, or external work-context inventories, its adoption record SHALL preserve their current authority identities or declared discovery locations. A changed or missing required inventory identity SHALL be reported as a visible freshness or completeness issue rather than being ignored or repaired through a provider fallback.

#### Scenario: A declared UI inventory revision changes
- **WHEN** the current UI inventory fingerprint differs from the identity bound by the last broad coverage result
- **THEN** the project audit SHALL report the affected coverage evidence as stale without executing UI validation on behalf of its native owner

### Requirement: Project adoption is FlowGuard-only
FlowGuard project adoption, audit, installed-currentness checking, and upgrade
SHALL operate without discovering, installing, validating, executing, or
modifying SkillGuard, SkillGuard Global Router, `.skillguard`, private
maintenance contracts, receipts, router state, run stores, or author prompts.

#### Scenario: Ordinary project is adopted
- **WHEN** `project-adopt` runs in a repository with no SkillGuard
- **THEN** it creates only FlowGuard-owned target-project records

#### Scenario: SkillGuard is absent
- **WHEN** `project-audit` or `project-upgrade` runs
- **THEN** missing SkillGuard packages, skills, contracts, router state, or
  prompts do not create a finding or block FlowGuard readiness

#### Scenario: Zero-write path fails
- **WHEN** adoption or upgrade fails before its FlowGuard transaction commits
- **THEN** it leaves no `.skillguard` directory, SkillGuard marker, process, or
  author-maintenance evidence

### Requirement: Project upgrade validates the installed consumer suite
Project audit and upgrade SHALL validate the installed global consumer
projection against the single package-owned authority and distribution
ownership manifest. The ordinary target repository and author checkout SHALL
NOT become suite authorities or fallback readers.

#### Scenario: Ordinary project has no author controls
- **WHEN** an ordinary project has no `.skillguard` directory or local
  FlowGuard skill suite and the installed consumer projection is exact
- **THEN** project audit and upgrade pass suite reconciliation without writing
  author controls or a local skill suite

#### Scenario: Installed consumer suite is unresolved
- **WHEN** the installed consumer suite is missing, mismatched, or contains an
  unregistered reserved FlowGuard member
- **THEN** project upgrade blocks before mutation and does not consult an
  author or target-local suite map

### Requirement: Ordinary-project guidance uses the one global consumer authority
Generated project adoption, audit, and upgrade guidance SHALL direct agents to
the current clean global consumer projection described by the package-owned
authority. It SHALL NOT require or authorize a project-local FlowGuard skill
suite, target-local suite map, FlowGuard source-repository script, or
author-maintenance dependency.

#### Scenario: Managed project block is generated
- **WHEN** FlowGuard renders its managed `AGENTS.md` block for an ordinary
  project
- **THEN** it identifies `$CODEX_HOME/skills/flowguard/SKILL.md` as the default
  consumer entry
- **AND** it states that the target project does not copy the suite into local
  `.agents/skills`

#### Scenario: Required revalidation is generated
- **WHEN** project adoption, audit, or upgrade emits required revalidation
- **THEN** `python -m flowguard project-audit --root . --json` is the
  package-owned executable project audit
- **AND** no executable item requires a checkout-local `python scripts/`,
  target-local suite map, or project-local FlowGuard skill tree

#### Scenario: Project-local legacy suite exists
- **WHEN** an ordinary target still contains a legacy project-local FlowGuard
  suite
- **THEN** that tree does not become current suite authority
- **AND** the global consumer projection remains the sole runtime skill
  authority without alias, fallback, or dual reader

### Requirement: Ordinary project zero-write behavior
FlowGuard project use, read-only audit, installed-currentness checking, and
adoption MUST NOT create or mutate SkillGuard files, prompts, processes,
receipts, router state, or project records.

#### Scenario: Empty project is adopted
- **WHEN** `project-adopt` runs in an ordinary project
- **THEN** it writes only FlowGuard-owned target-project records and leaves
  `.skillguard` and SkillGuard prompt markers absent

#### Scenario: FlowGuard check runs
- **WHEN** a native FlowGuard scenario or model check runs in an ordinary
  project
- **THEN** the process tree and resulting project tree contain no SkillGuard
  execution or state

### Requirement: Non-editable project upgrade uses packaged consumer authority
FlowGuard project audit and writing upgrade SHALL validate the current global
consumer projection against one immutable consumer-suite authority shipped
inside the installed package. Runtime project adoption SHALL NOT read an
author suite map, require an editable checkout, inspect a target-local suite,
or select a fallback authority.

#### Scenario: Empty ordinary project upgrades under a non-editable install
- **WHEN** an exact non-editable FlowGuard installation runs
  `project-upgrade` in an empty ordinary project
- **AND** the matching global consumer projection is current
- **THEN** the command writes the current managed `AGENTS.md` block and
  `.flowguard/project.toml`
- **AND** the project contains no `.agents/skills`, `.skillguard`, suite map,
  or copied FlowGuard skill directory

#### Scenario: Packaged authority is unavailable
- **WHEN** the installed package lacks a readable current consumer authority
- **THEN** project upgrade exits nonzero before mutation and does not consult
  an author checkout or target-local suite map
