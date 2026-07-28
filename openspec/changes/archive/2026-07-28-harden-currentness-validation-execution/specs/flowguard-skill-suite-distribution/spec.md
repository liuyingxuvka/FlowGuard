## MODIFIED Requirements

### Requirement: Canonical suite validation supports ownership-backed mixed roots
FlowGuard suite validation SHALL distinguish the canonical FlowGuard suite
from unrelated skills co-located in the same skill root only when the supported
package-owned consumer authority proves the exact current canonical member and
file boundary. The current suite membership MUST be derived from that authority
and MUST NOT be repeated as a second fixed literal list.

#### Scenario: Official suite is co-located with unrelated skills
- **WHEN** the package-owned authority names exactly the current canonical
  FlowGuard members and owns every required member file
- **AND** every canonical member directory and required file exists
- **AND** unrelated skill directories are co-located in the root
- **THEN** suite validation passes for the canonical set
- **AND** reports unrelated directories separately as outside the FlowGuard
  validation claim

#### Scenario: Mixed root lacks valid ownership evidence
- **WHEN** undeclared skill directories exist
- **AND** package-owned authority is missing, unsupported, incomplete, or stale
- **THEN** validation remains blocked and reports the authority defect

#### Scenario: Undeclared FlowGuard-like skill is present
- **WHEN** a valid authority exists
- **AND** an undeclared skill uses a FlowGuard-reserved id or prefix
- **THEN** validation reports `extra_discovered_member` and remains blocked

#### Scenario: Canonical member is missing from a mixed root
- **WHEN** any authority-declared member directory or required file is missing
- **THEN** validation reports that exact missing member or file and co-located
  skills do not satisfy the obligation

### Requirement: Clean consumer installation is transactional and authority-bounded
The FlowGuard consumer distribution SHALL include only the frozen clean
package-owned prompt projection after the existing maintenance unit has current
native validation and SkillGuard closure. Installation SHALL stage and verify
the exact authority member and file set before transactional activation,
compare the installed projection with that package authority, and restore the
previous active projection if a required post-activation currentness check
fails. Consumer installations SHALL exclude SkillGuard private contracts,
manifests, receipts, run stores, maintenance state, author-only tests, models,
fixtures, and notes.

#### Scenario: An older public route projection is installed
- **WHEN** staged or active consumer content contains a retired public skill,
  alias, fallback, fixed old member inventory, or stale prompt semantics
- **THEN** installed currentness fails and activation is refused or rolled back

#### Scenario: A read-only currentness check runs
- **WHEN** the installer or project audit checks the active prompt projection
- **THEN** it compares exact authority and content identity without launching
  native validation, smoke, provider commands, or SkillGuard resume

#### Scenario: A consumer has no SkillGuard runtime
- **WHEN** a clean consumer installation uses the validated FlowGuard skills
  for ordinary domain work
- **THEN** the skills remain complete without SkillGuard contracts, receipts,
  router state, commands, or runtime dependencies

#### Scenario: Consumer prohibition scan covers every staged file
- **WHEN** a staged consumer projection is prepared for activation
- **THEN** every file is scanned for author paths, author controls, SkillGuard
  dependencies, retired public entries, and unresolved placeholders

### Requirement: Release Distribution Closure
Distribution SHALL be considered released only after the current version,
documentation, OpenSpec state, model authority, and source, formal, shadow, and
installed consumer projections are frozen; the unique full-validation parent
passes for the frozen validation and release manifests; commit and immutable
tag metadata agree; a source-only GitHub Release is published with zero
uploaded assets; and read-only published identity comparison succeeds.
Published verification MUST NOT restart heavy validation producers.

#### Scenario: GitHub release exists but post-check fails
- **WHEN** tag and release exist but remote tag, tree, receipt, version, target,
  installation, or asset-count comparison fails
- **THEN** release remains incomplete and requires a new corrective version
  rather than moving the immutable tag

### Requirement: Separate Validation And Release Manifests
Local release verification SHALL freeze two non-interchangeable manifests.
`ValidationInputManifest` SHALL bind exact functional owner-scoped source,
current model authority, toolchain, environment, check and obligation
inventories, dependencies, and installed consumer projection.
`ReleaseTreeManifest` SHALL enumerate the exact source-only tag tree by
canonical relative path, Git mode, raw content or blob identity, current
package version, and zero-uploaded-assets policy. The verified terminal
full-parent receipt SHALL bind both fingerprints. Commit, local and remote tags,
and GitHub Release target SHALL be compared only to `ReleaseTreeManifest`.

#### Scenario: Only mtime changes
- **WHEN** governed contents and functional identities are identical but mtimes
  change
- **THEN** current release evidence remains reusable

#### Scenario: Content changes with preserved mtime
- **WHEN** validation input or release-tree content changes while its mtime is
  restored
- **THEN** the affected manifest changes and the prior full parent cannot
  authorize publication

#### Scenario: Local validation input is not tag content
- **WHEN** environment, toolchain, or installed projection identity is required
  for validation but is not a source-tree file
- **THEN** it remains in `ValidationInputManifest` and is not added to
  `ReleaseTreeManifest`

#### Scenario: Required public file is ignored or untracked
- **WHEN** a file required for public runtime, documentation, or model authority
  is absent from the exact tag tree
- **THEN** release-tree validation blocks even if the working copy has the file

#### Scenario: Tag points to different content
- **WHEN** release commit, local tag, remote tag, or GitHub Release target
  resolves to a tree different from the receipt-bound release manifest
- **THEN** remote release verification blocks and the immutable tag is not moved
