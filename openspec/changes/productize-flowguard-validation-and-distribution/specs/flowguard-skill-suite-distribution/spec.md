## ADDED Requirements

### Requirement: Idempotent Skill Lifecycle Commands
FlowGuard SHALL provide install, check, uninstall, and dry-run operations for its skill suite. Repeated install/check operations with unchanged source and target SHALL make no changes. Uninstall SHALL remove only installer-owned files whose disposition is safe.

#### Scenario: Install runs twice
- **WHEN** the same suite version is installed twice into a temporary `CODEX_HOME`
- **THEN** the second operation reports no changes and the installed tree remains identical

#### Scenario: Installed file was user-modified
- **WHEN** uninstall finds an installer-owned path whose hash no longer matches the recorded installed hash
- **THEN** it preserves the file and reports a conflict instead of deleting it

### Requirement: Complete Tree Parity
Distribution validation SHALL compare the complete relative-path sets and required hashes for source skills, formal repository skills, shadow workspace skills, and installed skills. Missing files, extra files, raw mismatches, semantic mismatches, and explicitly excluded environment-local evidence SHALL be reported separately.

#### Scenario: Installed tree has an extra obsolete file
- **WHEN** an installed skill contains a file absent from the canonical source tree and not explicitly excluded
- **THEN** parity validation fails with an extra-file finding

#### Scenario: Only two representative files match
- **WHEN** `SKILL.md` and `work-contract.json` match but another reference differs
- **THEN** complete-tree parity fails and no full-sync claim is emitted

### Requirement: Layout Neutral References
Every distributed skill reference and metadata path SHALL resolve in both repository and installed layout profiles without depending on a developer's workspace path.

#### Scenario: Installed skill points to repository docs
- **WHEN** a direct reference exists only relative to `.agents/skills` in the repository
- **THEN** temporary-install validation fails with the unresolved installed-layout path

### Requirement: Release Distribution Closure
Distribution SHALL be considered released only after local source/formal/shadow/installed parity passes, package version/changelog/tag metadata agree, GitHub publication succeeds, and the full verification contract is rerun against the published tag/assets.

#### Scenario: GitHub release exists but post-check fails
- **WHEN** the tag and release are published but published-artifact parity or full verification fails
- **THEN** release status remains incomplete and requires a new corrective version rather than moving the tag
