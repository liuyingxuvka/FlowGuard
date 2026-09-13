## MODIFIED Requirements

### Requirement: Package metadata does not prove skill setup
FlowGuard project adoption and version guidance SHALL NOT treat package
metadata, an author checkout, or a directory name as proof that AI-agent skills
are available. Ordinary project audit and upgrade SHALL load the single
package-owned consumer-suite authority and independently compare its exact
member and file identities with the installed global consumer projection and
distribution ownership manifest. The author source tree and its maintenance
state SHALL NOT be required for that currentness decision.

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
- **AND** no FlowGuard author checkout, project-local `.agents/skills/` tree,
  SkillGuard registry, or author receipt store is available
- **THEN** ordinary project audit and upgrade may validate consumer currentness
  without reporting an author-dependency defect

### Requirement: Project adoption consumes strict mixed-root suite evidence
Project audit and project upgrade SHALL derive the canonical FlowGuard consumer
member and file inventory only from the single package-owned
`flowguard/consumer-suite-authority.json`, whose current authority names the
fifteen-member clean consumer projection. They SHALL compare that exact
authority with the installed global skills root and distribution ownership
manifest, accept unrelated non-FlowGuard skills as outside the claim boundary,
and block when canonical membership, file identity, or ownership evidence is
unresolved. They SHALL NOT repeat a second fixed member list or consume an
author-side suite map as authority.

#### Scenario: Project audit sees a valid mixed root
- **WHEN** the package-owned authority names the current fifteen FlowGuard
  consumer members
- **AND** the installed global skills root contains every exact declared member
  and file with valid distribution ownership evidence
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
  records and preserve unrelated skill directories
- **AND** it does not read or write author skills, SkillGuard contracts,
  receipts, router state, run stores, or a project-local suite copy

#### Scenario: Mixed root contains a missing or fake FlowGuard member
- **WHEN** an authority-declared FlowGuard member or required file is missing
  or an undeclared FlowGuard-reserved member is present
- **THEN** project upgrade remains blocked by
  `suite_inventory_unresolved`
- **AND** no project record is written merely because unrelated skills were
  classified separately

#### Scenario: Package-owned consumer authority is unavailable
- **WHEN** the installed package lacks the supported package-owned consumer
  authority or its identity cannot be validated
- **THEN** ordinary project audit and upgrade fail visibly before any write
- **AND** they do not fall back to an author checkout, project-local skill
  tree, fixed historical member count, registry scan, or alternate manifest

## ADDED Requirements

### Requirement: Ordinary project adoption has zero author-maintenance dependency
Ordinary target-project adoption, audit, installed-currentness checking, and
upgrade SHALL consume only the importable FlowGuard package, its single
package-owned consumer authority, the installed global consumer projection,
the distribution ownership manifest, and the target project's own managed
records. These operations SHALL NOT import, execute, resume, mutate, or require
FlowGuard author skills, SkillGuard, private maintenance contracts, receipts,
router state, run stores, caches, sessions, models, tests, or source checkout.
Missing or mismatched consumer authority SHALL fail visibly rather than
activating an author-side, compatibility, or fallback path.

#### Scenario: Ordinary project currentness is read
- **WHEN** project audit or installed-currentness checking runs for an ordinary
  target repository
- **THEN** it performs identity comparison without launching consumer smoke,
  native skill validation, SkillGuard validation, provider execution, or
  resume
- **AND** it writes neither the target project nor any author-maintenance
  surface

#### Scenario: Ordinary project upgrade is explicitly requested
- **WHEN** project upgrade passes package-authority and installed-projection
  preflight and is authorized to write
- **THEN** it may update only the target project's declared adoption records,
  deterministic current-format artifacts, and logs within that command's
  scope
- **AND** it does not install, synchronize, repair, or validate the author
  suite on behalf of the target project

#### Scenario: Author-only state is present beside a target project
- **WHEN** an author checkout, `.skillguard` state, private router, or
  maintenance receipt is discoverable on the same machine
- **THEN** ordinary project adoption ignores it as non-authoritative context
- **AND** no path, receipt, or status from that state enters the consumer
  currentness result

