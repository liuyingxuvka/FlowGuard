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
Distribution SHALL be considered released only after version `0.64.0`,
documentation, OpenSpec state, current model authority, and
source/formal/shadow/installed consumer parity are frozen; the unique final
full parent gate passes for the frozen manifest pair; commit and immutable tag
metadata agree; a source-only GitHub Release is published with zero uploaded
assets; and read-only published identity comparison succeeds. Published
verification MUST NOT rerun heavy validation producers.

#### Scenario: GitHub release exists but post-check fails
- **WHEN** the tag and release are published but remote tag, tree, receipt, version, target, or asset-count comparison fails
- **THEN** release status remains incomplete and requires a new corrective version rather than moving the tag

### Requirement: Separate Validation And Release Manifests
Local release verification SHALL freeze two non-interchangeable manifests.
`ValidationInputManifest` SHALL bind exact functional validation inputs,
including owner-scoped source content, current model authority, toolchain,
environment, check and obligation inventories, dependencies, and installed
consumer projection. `ReleaseTreeManifest` SHALL enumerate the exact
source-only tag tree by canonical relative path, Git mode, and raw
content/blob identity, and SHALL bind version `0.64.0` and the policy of zero
uploaded release assets. The terminal full parent receipt SHALL bind both
fingerprints.
The release commit, local and remote tags, and GitHub Release target SHALL be
compared only to `ReleaseTreeManifest`.

#### Scenario: Only mtime changes
- **WHEN** governed file contents and every functional identity remain identical but mtimes change
- **THEN** current release evidence remains reusable

#### Scenario: Content changes with preserved mtime
- **WHEN** validation input or release-tree content changes while its mtime is restored
- **THEN** the affected manifest fingerprint changes and the prior final parent cannot authorize publication

#### Scenario: Local validation input is not tag content
- **WHEN** an environment, toolchain, or installed-projection identity is required for validation but is not a source-tree file
- **THEN** it remains in `ValidationInputManifest` and is not fabricated into `ReleaseTreeManifest`

#### Scenario: Required public file is ignored or untracked
- **WHEN** a file declared necessary for public runtime, documentation, or model authority is absent from the exact tag tree
- **THEN** `ReleaseTreeManifest` validation blocks release even if the working copy contains the file

#### Scenario: Tag points to different content
- **WHEN** release commit, local tag, remote tag, or GitHub Release target resolves to a tree different from the receipt-bound `ReleaseTreeManifest`
- **THEN** remote release verification blocks and the immutable tag is not moved
