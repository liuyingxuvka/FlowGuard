# flowguard-skill-suite-distribution Specification

## Purpose
This capability defines how FlowGuard is distributed and explained as an
AI-agent skill suite, including the package-owned clean consumer projection,
public `flowguard` entry, executable check-script role, and installed-skill
parity evidence needed before claiming active agent behavior is current.
## Requirements
### Requirement: FlowGuard is distributed as an AI-agent skill suite
FlowGuard public onboarding SHALL present the package-authority clean consumer
projection under `$CODEX_HOME/skills/` as the AI-agent install and read
surface. The repository `.agents/skills/` tree is author source, not installed
runtime authority.

#### Scenario: Agent reads public onboarding
- **WHEN** an AI agent reads the README or project integration guide
- **THEN** it MUST learn that complete agent setup means access to
  `AGENTS.md` and every authority-declared FlowGuard consumer skill under
  `$CODEX_HOME/skills/`
- **AND** it MUST NOT treat Python package installation as the skill install
  surface

#### Scenario: Default skill entry is visible
- **WHEN** an AI agent loads the FlowGuard skill suite
- **THEN** the public `flowguard` skill MUST be identified as the default
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
from unrelated skills co-located in the same skill root only when the
package-owned consumer authority proves the exact current canonical member and
file boundary. Membership MUST be derived from that authority and MUST NOT be
repeated as a fixed literal list.

#### Scenario: Official suite is co-located with unrelated skills
- **WHEN** the package-owned authority names every current FlowGuard consumer
  member and owns every required member file
- **AND** every authority-declared member directory and required file exists
- **AND** additional non-FlowGuard skill directories also contain
  `SKILL.md`
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
Provider-neutral prompt maintenance SHALL remain inside the existing SkillGuard maintenance unit for the FlowGuard suite and SHALL cover the exact FlowGuard-owned source members selected by the frozen affected-component graph. The contract SHALL NOT hardcode a fleet count that can drift from the changed component set. Every selected member SHALL update its contract source, compiled contract, exact check manifest, target-owned semantic checks, consumer projection, and installed projection without creating a new provider unit or satellite. Official OpenSpec, Spec Kit, Superpowers, and other third-party provider skills SHALL remain outside this maintenance authority.

#### Scenario: This blueprint-integrity change freezes its affected prompt set
- **WHEN** this change freezes prompt/protocol edits for `flowguard`, `flowguard-existing-model-preflight`, `flowguard-model-test-alignment`, `flowguard-architecture-reduction`, `flowguard-structure-mesh`, and `flowguard-development-process-flow`
- **THEN** those exact six members enter the affected owner and projection plan
- **AND** unrelated FlowGuard or third-party skills are not enrolled by a fixed fleet list

#### Scenario: One affected prompt source changes
- **WHEN** a provider-neutral wording or route rule changes in one FlowGuard prompt source
- **THEN** SkillGuard SHALL invalidate only the exact declared owners and projections that consume the changed component, execute their native checks, and include them in the unit's one frozen final validation plan

#### Scenario: A third-party provider skill is installed nearby
- **WHEN** SkillGuard inventories the FlowGuard maintenance unit and discovers an official or third-party provider skill in the environment
- **THEN** it SHALL NOT enroll, copy, validate, package, or install that external skill as a FlowGuard unit member

#### Scenario: The affected prompts disagree on provider semantics
- **WHEN** any selected prompt surface retains OpenSpec-only, provider-executing, receipt-owning, or provider-status-as-evidence guidance
- **THEN** the unit's native semantic validation SHALL remain blocked and SHALL NOT publish a clean consumer projection

### Requirement: Clean consumer installation is transactional and authority-bounded
The FlowGuard consumer distribution SHALL include only the frozen clean
package-owned prompt projection after the existing maintenance unit has
current native validation and SkillGuard closure. Installation SHALL stage and
verify the exact authority member and file set before transactional activation,
compare the installed projection with that package authority, and restore the
previous active projection if a required post-activation currentness check
fails. Consumer installations SHALL exclude SkillGuard private contracts,
manifests, receipts, run stores, maintenance state, author-only tests, models,
fixtures, and notes.

#### Scenario: An older OpenSpec-only prompt is installed
- **WHEN** staged or active consumer content contains the retired OpenSpec-only prompt semantics instead of the frozen provider-neutral projection
- **THEN** installed currentness SHALL fail and activation SHALL be refused or rolled back

#### Scenario: A read-only currentness check runs
- **WHEN** the installer or project audit checks whether the active prompt projection matches its authority
- **THEN** the check SHALL compare exact projection identity and content without launching native validation, provider commands, smoke tests, or a SkillGuard resume

#### Scenario: A consumer has no SkillGuard runtime
- **WHEN** a clean consumer installation uses the validated FlowGuard skills for ordinary domain work
- **THEN** the skills SHALL remain complete and usable without SkillGuard contracts, receipts, router state, or runtime dependencies

#### Scenario: Consumer prohibition scan covers every staged file
- **WHEN** a staged consumer projection is prepared for activation
- **THEN** every file is scanned for author paths, author controls, SkillGuard
  dependencies, retired public entries, and unresolved placeholders

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
Distribution SHALL be considered released only after the selected current
version identity, documentation, OpenSpec state, model authority, and source,
formal, shadow, and installed consumer projections are frozen; the unique
full-validation parent passes for the frozen validation and release manifests;
commit and immutable tag metadata agree; a source-only GitHub Release is
published with zero uploaded assets; and read-only published identity
comparison succeeds. Published verification MUST NOT restart heavy validation
producers.

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
content/blob identity, the selected current package-version identity, and the
policy of zero uploaded release assets. The terminal full parent receipt SHALL
bind both fingerprints.
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

### Requirement: Consumer prohibition scan
The consumer builder and installed-layout validator MUST scan every staged
FlowGuard consumer file and reject SkillGuard author controls, private paths,
maintenance dependencies, receipts, router onboarding, retired public skill
entries, and unresolved placeholders.

#### Scenario: Hidden contract is present
- **WHEN** a staged consumer skill contains `.skillguard/**` or another
  author-control file
- **THEN** distribution activation blocks and reports the exact prohibited
  paths

#### Scenario: Prompt contains maintenance dependency
- **WHEN** a consumer prompt references a SkillGuard command, contract trio,
  receipt, router onboarding, or managed marker
- **THEN** prompt and distribution validation block

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

### Requirement: Distribution owner publishes typed current suite evidence
The distribution workflow SHALL own current suite identity, clean installation projection, and source/install parity evidence in a form that downstream process gates can verify without duplicating distribution semantics.

#### Scenario: Installed projection is stale
- **WHEN** the source projection identity differs from the installed suite identity
- **THEN** distribution evidence is not current and downstream release confidence remains blocked

### Requirement: Blueprint-related skill changes remain target-owned and cleanly projected
Changes to affected FlowGuard skill prompts and protocols SHALL remain inside the existing FlowGuard maintenance unit and SHALL be validated by each target skill's native checks under SkillGuard author-side supervision. Consumer installation SHALL contain only the clean target skill projection and SHALL NOT include SkillGuard receipts, author registries, execution-owner metadata, or a new `DNA` skill.

#### Scenario: A blueprint prompt changes in one maintained skill
- **WHEN** the frozen impact plan maps the changed component to one or more affected skill owners
- **THEN** only those exact native owners and consuming projections require affected revalidation before the final full gate
- **AND** an unmapped prompt change blocks instead of falling back to an indiscriminate run-all

#### Scenario: Consumer projection is installed
- **WHEN** all affected target-owned checks and the singular frozen maintenance-unit gate pass
- **THEN** installation projects the current consumer files transactionally
- **AND** no SkillGuard author evidence or alternate runtime route is copied into the consumer tree

#### Scenario: A new DNA skill appears in the projection
- **WHEN** source or installed inventory contains a standalone DNA skill or duplicate blueprint route
- **THEN** distribution validation reports an unexpected consumer member and ownership conflict
- **AND** installation or release closure is blocked

### Requirement: Source installation Git and release identities close independently
Distribution SHALL preserve separate current evidence for the authoritative source skill inventory, package source, editable installation, installed consumer skill inventory, local repository commit, remote branch, tag, and GitHub Release. Synchronization or success in one identity domain SHALL NOT imply success in another.

#### Scenario: Source checks pass before installed projection sync
- **WHEN** target-owned source checks pass but an affected installed consumer file has a different fingerprint
- **THEN** source validation remains reported separately and installation parity remains incomplete
- **AND** Git or release publication is not reported ready

#### Scenario: Final source changes after the frozen full gate
- **WHEN** any maintained source or toolchain component changes after the singular final validation receipt
- **THEN** the affected source and projection evidence becomes stale
- **AND** the old receipt cannot authorize installation, tag, or release

#### Scenario: Patch release closes every identity
- **WHEN** the authorized patch release has current target-owned checks, SkillGuard unit closure, clean install parity, exact package version, committed source, pushed commit, matching tag, and matching GitHub Release
- **THEN** distribution MAY report release closure for those exact identities
- **AND** every current result retains its own exact identity and claim boundary

### Requirement: Blueprint release freezes behavior and reduction evidence
Before installation or source publication for a blueprint-qualified FlowGuard release, the distribution owner SHALL consume the frozen behavior-block qualification and self-reduction evidence identities in addition to the existing source, skill, model, test, OpenSpec, and parity owners.

#### Scenario: Installed projection is current but behavior qualification is stale
- **WHEN** clean consumer installation parity passes but the behavior-block qualification fingerprint does not match the release tree
- **THEN** installation status MAY remain current for that projection
- **AND** GitHub release publication SHALL remain blocked

### Requirement: Consumer prompts share provider-neutral blueprint semantics
Every affected maintained FlowGuard prompt and protocol SHALL describe target-system blueprint work in provider-neutral terms and preserve affected-only lightweight use. No consumer projection SHALL add a standalone DNA or language-specific blueprint skill.

#### Scenario: Source prompt is generalized
- **WHEN** a maintained FlowGuard member changes its target-system or readiness guidance
- **THEN** the exact affected member checks and SkillGuard maintenance-unit evidence SHALL be refreshed
- **AND** the clean installed and shadow projections SHALL contain the same current guidance

### Requirement: Patch release closes generalized blueprint identities
The authorized patch release SHALL separately prove authoritative source, target-owned model and test validation, current provider-neutral skill projection, editable package installation, shadow parity, local commit, remote branch, patch tag, and GitHub Release identities.

#### Scenario: Static blueprint passes but provider prompt is stale
- **WHEN** the static blueprint result is current but an affected installed prompt retains the Python-only route
- **THEN** distribution and release closure SHALL remain blocked
- **AND** the static blueprint result SHALL remain reported separately

### Requirement: Affected FlowGuard skills close through one author unit
Changes to maintained FlowGuard skill prompts, references, routes, or native checks SHALL be compiled and validated inside `unit:flowguard-suite` with one exact owner plan and target-owned check results before consumer projection.

#### Scenario: One source skill changes
- **WHEN** an affected source skill changes a mapped component
- **THEN** SkillGuard SHALL invalidate only declared consuming owners and projections
- **AND** unmapped impact SHALL block rather than run every owner by fallback

### Requirement: Consumer and installed skills remain clean and independently current
The FlowGuard consumer projection and installed skills SHALL contain only target-owned skill material and SHALL exclude `.skillguard`, author contracts, receipts, router state, private paths, and maintenance-only evidence. Source validation, projection parity, and installation currentness SHALL remain separate results.

#### Scenario: Source checks pass but installed skill is stale
- **WHEN** the author source passes while an installed consumer file differs from the frozen projection
- **THEN** installation SHALL remain not current
- **AND** source success SHALL NOT substitute for installation parity

### Requirement: Release self-maintenance owner publishes a bounded terminal result
The release validation owner SHALL execute the complete composed self-blueprint and architecture-reduction review and SHALL publish the strict compact projection as its terminal command result. Compact publication SHALL reduce output size only; it SHALL NOT reduce the model, denominator, candidates, proofs, retain decisions, freshness checks, or cleanup readiness calculation.

#### Scenario: Full release validation reaches self-maintenance review
- **WHEN** the frozen release plan executes the self-maintenance validation owner
- **THEN** the owner command SHALL request composed architecture reduction, compact publication, and machine-readable output
- **AND** its receipt SHALL bind the full review fingerprint, projection fingerprint, exit status, execution owner, and frozen inputs

#### Scenario: Complete review exceeds its frozen supervision boundary
- **WHEN** the complete composed review does not reach a terminal producer result within the release owner's declared timeout
- **THEN** the supervised episode SHALL be non-reusable and publication SHALL remain blocked
- **AND** the implementation SHALL contract duplicate computation rather than omit a model, denominator, candidate, proof, retain decision, freshness check, or cleanup gate

### Requirement: Shadow synchronization preserves the author-source projection
FlowGuard SHALL provide one explicit full-suite synchronization operation for an author-source shadow skill tree. The operation SHALL project the complete current author inventory, including author-only contract artifacts, and SHALL NOT generate consumer release files or use the consumer installation route as an alternate implementation.

#### Scenario: Installer-owned consumer tree becomes an author shadow
- **WHEN** the target contains the exact unchanged FlowGuard consumer projection recorded by its installer ownership authority
- **AND** the caller explicitly requests author-source synchronization
- **THEN** the operation replaces the complete managed FlowGuard suite with the current author projection
- **AND** it removes only exact installer-owned consumer-only artifacts
- **AND** it records the resulting author-source ownership and current tree identity

#### Scenario: Already-current author shadow is synchronized again
- **WHEN** the target ownership authority and complete managed tree already equal the current author projection
- **THEN** the operation succeeds without changing any file
- **AND** reports an idempotent current result

#### Scenario: Consumer installation is requested
- **WHEN** the caller requests the ordinary install operation
- **THEN** FlowGuard continues to produce only the clean consumer distribution
- **AND** no author-only contract or maintenance artifact enters the installed consumer tree

### Requirement: Author synchronization is ownership-bounded and repository-local
Author-source synchronization SHALL examine only the declared FlowGuard skill-suite members and its own ownership authority. It SHALL preserve co-located skills and every file outside that boundary, SHALL reject unsafe paths or modified/unowned collisions, and SHALL NOT copy, reset, clean, or otherwise synchronize the surrounding repository.

#### Scenario: Other project work is co-located with the shadow skills
- **WHEN** the target repository contains unrelated skills, source files, reports, OpenSpec changes, or peer-agent edits outside the managed FlowGuard member boundary
- **THEN** author synchronization leaves all of them unchanged
- **AND** its claim is limited to the synchronized FlowGuard author tree

#### Scenario: Managed target file was modified after installation
- **WHEN** a target path that would be replaced or removed no longer matches its recorded ownership hash
- **THEN** synchronization preserves the target and fails with an exact conflict
- **AND** no partial author projection is activated

#### Scenario: Dry-run inspects a role transition
- **WHEN** the caller requests a dry-run from an exact consumer projection to author source
- **THEN** the result lists the exact copies, removals, ownership transition, and preserved co-located paths
- **AND** the target remains byte-for-byte unchanged

### Requirement: Author projection synchronization has one current owner
FlowGuard author projection synchronization SHALL use the current atomic installer-owned author-sync operation as its sole maintained owner. Tests and documentation for a retired whole-workspace shadow synchronization script SHALL be removed rather than preserved through an import shim, compatibility command, or duplicate synchronization path.

#### Scenario: Retired shadow script tests remain
- **WHEN** tests still import or patch the retired whole-workspace shadow synchronization module
- **THEN** those tests SHALL be retired or replaced by tests of the current atomic author-sync owner before final validation

#### Scenario: Author shadow starts empty
- **WHEN** a new isolated author-shadow target has no accepted FlowGuard author projection
- **THEN** the current installation projection SHALL establish the bounded target and the atomic author-sync operation SHALL then prove exact author parity

#### Scenario: Consumer projection remains clean
- **WHEN** author-source validation and synchronization complete
- **THEN** the installed consumer projection SHALL exclude SkillGuard contracts, receipts, author registries, maintenance evidence, and whole-workspace synchronization machinery
