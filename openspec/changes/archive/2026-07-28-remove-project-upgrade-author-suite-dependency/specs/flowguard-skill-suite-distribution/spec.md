## MODIFIED Requirements

### Requirement: Canonical suite validation supports ownership-backed mixed roots
FlowGuard suite validation SHALL distinguish the canonical FlowGuard consumer
suite from unrelated skills co-located in the same skill root only when the
package-owned consumer authority proves the exact current canonical member and
file boundary. Membership MUST be derived from that authority and MUST NOT be
repeated as a fixed literal list.

#### Scenario: Official suite is co-located with unrelated skills
- **WHEN** the package-owned authority names every current FlowGuard consumer
  member and owns every required member file
- **AND** every authority-declared member directory and required file exists
- **AND** additional non-FlowGuard skill directories also contain `SKILL.md`
- **THEN** suite validation passes for the authority-declared FlowGuard set
- **AND** it reports the unrelated directories separately as co-located skills
  outside the validation claim

#### Scenario: Mixed root lacks valid ownership evidence
- **WHEN** undeclared skill directories exist
- **AND** the package authority is missing, unsupported, incomplete, or stale
- **THEN** validation remains blocked and reports the authority defect

#### Scenario: Undeclared FlowGuard-like skill is present
- **WHEN** a valid package authority exists
- **AND** an undeclared skill id uses a FlowGuard-reserved id or prefix
- **THEN** validation reports that id as `extra_discovered_member`
- **AND** the suite remains blocked

#### Scenario: Canonical member is missing from a mixed root
- **WHEN** a valid package authority exists
- **AND** any authority-declared member directory or required file is missing
- **THEN** validation reports the existing missing-member or missing-file
  finding
- **AND** co-located skills do not satisfy or hide the missing obligation

### Requirement: Release Distribution Closure
Distribution SHALL be considered released only after the selected current
version identity, documentation, OpenSpec state, model authority, and source,
formal, shadow, and installed consumer projections are frozen; the unique
full-validation parent passes for the frozen validation and release manifests;
commit and immutable tag metadata agree; a source-only GitHub Release is
published with zero uploaded assets; and read-only published identity
comparison succeeds. Published verification MUST NOT restart heavy validation
producers.

#### Scenario: GitHub release exists but post-check fails
- **WHEN** the tag and release are published but remote tag, tree, receipt,
  version, target, installation, or asset-count comparison fails
- **THEN** release remains incomplete and requires a new corrective version
  rather than moving the immutable tag

### Requirement: Separate Validation And Release Manifests
Local release verification SHALL freeze two non-interchangeable manifests.
`ValidationInputManifest` SHALL bind exact functional owner-scoped source,
current model authority, toolchain, environment, check and obligation
inventories, dependencies, and installed consumer projection.
`ReleaseTreeManifest` SHALL enumerate the exact source-only tag tree by
canonical relative path, Git mode, raw content or blob identity, the selected
current package-version identity, and the zero-uploaded-assets policy. The
verified terminal full-parent receipt SHALL bind both fingerprints. Commit,
local and remote tags, and GitHub Release target SHALL be compared only to
`ReleaseTreeManifest`.

#### Scenario: Only mtime changes
- **WHEN** governed file contents and every functional identity remain
  identical but mtimes change
- **THEN** current release evidence remains reusable

#### Scenario: Content changes with preserved mtime
- **WHEN** validation input or release-tree content changes while its mtime is
  restored
- **THEN** the affected manifest fingerprint changes and the prior final
  parent cannot authorize publication

#### Scenario: Local validation input is not tag content
- **WHEN** environment, toolchain, or installed-projection identity is
  required for validation but is not a source-tree file
- **THEN** it remains in `ValidationInputManifest` and is not fabricated into
  `ReleaseTreeManifest`

#### Scenario: Required public file is ignored or untracked
- **WHEN** a file required for public runtime, documentation, or model
  authority is absent from the exact tag tree
- **THEN** `ReleaseTreeManifest` validation blocks release even if the working
  copy contains the file

#### Scenario: Tag points to different content
- **WHEN** release commit, local tag, remote tag, or GitHub Release target
  resolves to a tree different from the receipt-bound `ReleaseTreeManifest`
- **THEN** remote release verification blocks and the immutable tag is not
  moved

## ADDED Requirements

### Requirement: Parity roots declare projection roles
Every configured parity root SHALL declare one current role:
`author_source` or `consumer_distribution`. The author source MAY contain
maintenance controls; staged, installed, and shadow consumer roots SHALL be
compared against the clean package-owned consumer projection and SHALL reject
author controls. Role labels MUST NOT change the package-authority member set.

#### Scenario: Installed tree is compared as author source
- **WHEN** an installed consumer root is missing a role or is labeled
  `author_source`
- **THEN** parity blocks rather than treating author-only controls as consumer
  files

### Requirement: Release authority is source only
Every selected FlowGuard release SHALL use its immutable source commit and tag
tree as the sole published artifact authority. Wheels, source distributions,
and uploaded GitHub Release assets are outside the release authority and MUST
remain absent under the source-only policy.

#### Scenario: Package archive is present
- **WHEN** local or published verification finds a package archive or uploaded
  release asset for the selected release identity
- **THEN** source-only release verification fails
