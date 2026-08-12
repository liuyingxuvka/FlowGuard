## MODIFIED Requirements

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
- **WHEN** package authority and the installed global FlowGuard projection have
  exact member, file, and ownership parity
- **AND** unrelated non-FlowGuard skills are co-located in the skill root
- **THEN** project audit does not report `suite_inventory_unresolved` for
  those unrelated skills
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
- **THEN** project upgrade remains blocked by `suite_inventory_unresolved`
- **AND** no project record is written merely because unrelated skills were
  classified separately

## ADDED Requirements

### Requirement: Non-editable project upgrade uses packaged consumer authority
FlowGuard project audit and writing upgrade SHALL validate the current global
15-skill consumer projection against one immutable consumer-suite authority
shipped inside the installed FlowGuard package. Runtime project adoption SHALL
NOT read an author suite map, require an editable checkout, inspect a
target-local suite, or select a fallback authority.

#### Scenario: Empty ordinary project upgrades under a non-editable install
- **WHEN** an exact non-editable FlowGuard installation runs
  `project-upgrade` in an empty ordinary project
- **AND** the matching global 15-skill consumer projection is current
- **THEN** the command writes the current managed `AGENTS.md` block and
  `.flowguard/project.toml`
- **AND** the post-write project audit passes
- **AND** the project contains no `.agents/skills`, `.skillguard`, suite map,
  or copied FlowGuard skill directory

#### Scenario: Packaged authority is unavailable
- **WHEN** the installed package lacks a readable current consumer-suite
  authority
- **THEN** project upgrade exits nonzero before mutation with an exact
  authority finding
- **AND** it does not consult an author checkout or target-local suite map

#### Scenario: Global projection differs from packaged authority
- **WHEN** a declared consumer member or file is missing, extra, modified, or
  contains author-control residue
- **THEN** project upgrade exits nonzero before mutation with exact parity
  findings
- **AND** it does not install, repair, alias, or downgrade the global suite

#### Scenario: Project contains an obsolete local suite
- **WHEN** the target project contains a legacy local FlowGuard suite or suite
  map
- **THEN** that local tree is not read as current authority
- **AND** the packaged authority and global consumer projection remain the
  only validation path

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
