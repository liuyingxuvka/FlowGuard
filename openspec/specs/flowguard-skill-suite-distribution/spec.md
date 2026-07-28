# flowguard-skill-suite-distribution Specification

## Purpose
This capability defines how FlowGuard is distributed and explained as an
AI-agent skill suite, including the `.agents/skills/` primary surface, default
entry skill, executable check-script role, and local installed-skill sync
evidence needed before claiming active agent behavior is current.
## Requirements
### Requirement: FlowGuard is distributed as an AI-agent skill suite
FlowGuard public onboarding SHALL present `.agents/skills/` as the primary
AI-agent install and read surface.

#### Scenario: Agent reads public onboarding
- **WHEN** an AI agent reads the README or project integration guide
- **THEN** it MUST learn that complete agent setup means access to
  `AGENTS.md` and every FlowGuard `SKILL.md` under `.agents/skills/`
- **AND** it MUST NOT treat Python package installation as the skill install
  surface

#### Scenario: Default skill entry is visible
- **WHEN** an AI agent loads the FlowGuard skill suite
- **THEN** `model-first-function-flow` MUST be identified as the default
  entrypoint
- **AND** sibling FlowGuard skills MUST be described as part of the same suite

### Requirement: Executable checks are presented as skill-attached scripts
FlowGuard documentation SHALL describe executable checks as scripts or check
engine support for the skills rather than as the primary installation product.

#### Scenario: User needs executable evidence
- **WHEN** a user or agent needs to run FlowGuard checks
- **THEN** the docs MUST route to local check scripts, examples, or
  `python -m flowguard` compatibility commands as execution paths
- **AND** those commands MUST be described as check execution, not as the
  FlowGuard skill installation

### Requirement: Local active behavior requires installed skill sync
FlowGuard SHALL verify local installed AI-agent skill content after repository
skill guidance changes before claiming that active local AI behavior is
synchronized.

#### Scenario: Repository skill wording changes
- **WHEN** repository-managed FlowGuard skill files change
- **THEN** local installed Codex skill copies MUST be refreshed or reported as
  unsynced
- **AND** verification MUST compare guidance markers from the affected skill
  files rather than relying only on package version or directory existence

### Requirement: Canonical suite validation supports ownership-backed mixed roots
FlowGuard suite validation SHALL distinguish the canonical FlowGuard suite
from unrelated skills co-located in the same skill root only when a supported
official distribution ownership manifest proves the exact canonical member
boundary. It MUST continue to require exactly seventeen declared FlowGuard
members and every required member file.

#### Scenario: Official suite is co-located with unrelated skills
- **WHEN** the ownership manifest names exactly the seventeen declared
  FlowGuard members and owns each member's `SKILL.md`
- **AND** all seventeen canonical member directories and required files exist
- **AND** additional non-FlowGuard skill directories also contain
  `SKILL.md`
- **THEN** suite validation passes
- **AND** it reports seventeen declared and seventeen discovered suite members
- **AND** it reports the unrelated directories separately as co-located skills

#### Scenario: Mixed root lacks valid ownership evidence
- **WHEN** undeclared skill directories exist
- **AND** the ownership manifest is missing, unsupported, incomplete, or does
  not name exactly the declared suite
- **THEN** validation retains strict reverse discovery
- **AND** the undeclared directories produce `extra_discovered_member`
  findings

#### Scenario: Undeclared FlowGuard-like skill is present
- **WHEN** a valid ownership manifest exists
- **AND** an undeclared skill id uses a FlowGuard-reserved id or prefix
- **THEN** validation reports that id as `extra_discovered_member`
- **AND** the suite remains blocked

#### Scenario: Canonical member is missing from a mixed root
- **WHEN** a valid ownership manifest exists
- **AND** any declared FlowGuard member directory or required file is missing
- **THEN** validation reports the existing missing-member or missing-file
  finding
- **AND** co-located skills do not satisfy or hide the missing obligation

### Requirement: Mixed-root reports preserve foreign-skill visibility
FlowGuard suite reports SHALL expose allowed co-located skill ids separately
from canonical discovered member ids and SHALL state that those skills were not
validated by the FlowGuard suite check.

#### Scenario: JSON report contains co-located skills
- **WHEN** ownership-backed mixed-root validation succeeds
- **THEN** the JSON report includes the co-located skill ids
- **AND** its claim boundary states that unrelated skills are outside the
  FlowGuard suite validation claim

### Requirement: Strategy guidance remains current across maintained skill projections
The skill-suite distribution SHALL synchronize and parity-check the current conditional DevelopmentProcessFlow skill, core protocol, conditional optimization and failure-triage references, OpenAI prompt, contract source, compiled contract, and check manifest after process-optimization maintenance under one SkillGuard validation plan. Every maintained member SHALL remain on the sole current contract/depth authority, and source, shadow, formal repository, and installed projections SHALL contain no current former-policy, fallback, alias, wrapper, or stale prompt success path before distribution currentness can pass.

#### Scenario: Installed protocol is stale
- **WHEN** the installed DPF material lacks the current activation gate, diagnostic-boundary/execution-mode contract, or inactive output boundary
- **THEN** distribution parity fails rather than accepting older six-policy or fallback guidance

#### Scenario: Retired policy survives in another current projection
- **WHEN** a maintained prompt, generated AGENTS block, template, contract, or installed skill still authorizes the former six-policy/Pareto path
- **THEN** suite distribution is blocked even if the source DPF skill itself is current

### Requirement: Managed skills declare V1 authority lifecycle
Every managed FlowGuard V2 contract source SHALL declare whether former V1 runtime surfaces are migration evidence or formally retired, and generated/installed artifacts SHALL preserve that decision.

#### Scenario: V2 exists but retirement evidence is incomplete
- **WHEN** a skill has a V2 contract trio and former V1 migration surfaces but lacks official calibration and retirement receipts
- **THEN** it SHALL resolve as `v2-migration`, V2 SHALL be the only runtime authority, and V1 SHALL NOT provide closure or release success

#### Scenario: Retired V1 surface remains
- **WHEN** a skill claims `v2-only` but a former V1 work contract, underscore check manifest, or V1 run record remains
- **THEN** runtime-authority, suite, and install validation SHALL block

#### Scenario: Formal retirement is attempted
- **WHEN** current content-addressed positive/shallow calibration, eligibility, completion, rollback, and residual-absence evidence all pass
- **THEN** the official atomic retirement workflow MAY remove only the exact former V1 runtime surfaces and prove `v2-only`

### Requirement: Provider-neutral prompt maintenance stays in the existing FlowGuard unit
The provider-neutral prompt update SHALL remain inside the existing SkillGuard maintenance unit for the FlowGuard suite and SHALL cover exactly the declared FlowGuard-owned members: `flowguard`, `flowguard-behavior-commitment-ledger`, `flowguard-existing-model-preflight`, `flowguard-development-process-flow`, and `flowguard-test-mesh`. The unit SHALL update its contract source, compiled contract, exact check manifest, and target-owned semantic checks without creating a new provider unit or satellite. Official OpenSpec, Spec Kit, Superpowers, and other third-party provider skills SHALL remain outside this maintenance authority.

#### Scenario: One of the five prompt sources changes
- **WHEN** a provider-neutral wording or route rule changes in one declared FlowGuard prompt source
- **THEN** SkillGuard SHALL invalidate only the exact declared owners and projections that consume the changed component, execute their native checks, and include them in the unit's one frozen final validation plan

#### Scenario: A third-party provider skill is installed nearby
- **WHEN** SkillGuard inventories the FlowGuard maintenance unit and discovers an official or third-party provider skill in the environment
- **THEN** it SHALL NOT enroll, copy, validate, package, or install that external skill as a FlowGuard unit member

#### Scenario: The five prompts disagree on provider semantics
- **WHEN** any of the declared prompt surfaces retains OpenSpec-only, provider-executing, receipt-owning, or provider-status-as-evidence guidance
- **THEN** the unit's native semantic validation SHALL remain blocked and SHALL NOT publish a clean consumer projection

### Requirement: Clean consumer installation is transactional and authority-bounded
The FlowGuard consumer distribution SHALL include only the frozen clean prompt projection after the existing maintenance unit has current native validation and SkillGuard closure. Installation SHALL stage and verify exact content before transactional activation, compare the installed projection with the selected source or package authority, and restore the previous active projection if a required post-activation currentness check fails. Consumer installations SHALL exclude SkillGuard private contracts, manifests, receipts, run stores, and maintenance state.

#### Scenario: An older OpenSpec-only prompt is installed
- **WHEN** staged or active consumer content contains the retired OpenSpec-only prompt semantics instead of the frozen provider-neutral projection
- **THEN** installed currentness SHALL fail and activation SHALL be refused or rolled back

#### Scenario: A read-only currentness check runs
- **WHEN** the installer or project audit checks whether the active prompt projection matches its authority
- **THEN** the check SHALL compare exact projection identity and content without launching native validation, provider commands, smoke tests, or a SkillGuard resume

#### Scenario: A consumer has no SkillGuard runtime
- **WHEN** a clean consumer installation uses the validated FlowGuard skills for ordinary domain work
- **THEN** the skills SHALL remain complete and usable without SkillGuard contracts, receipts, router state, or runtime dependencies

### Requirement: Installation freshness follows only the declared installation projection
Only components mapped to the frozen FlowGuard installation projection SHALL make the consumer installation stale. Source-only fixtures, native validation models, maintenance notes, receipts, and reports SHALL remain outside installation content and SHALL NOT trigger a consumer rewrite merely because they changed.

#### Scenario: A source-only maintenance fixture changes
- **WHEN** a fixture used by a native semantic check changes but the frozen installation projection does not
- **THEN** SkillGuard SHALL revalidate the declared affected owner while installed currentness SHALL remain a separate projection comparison

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

