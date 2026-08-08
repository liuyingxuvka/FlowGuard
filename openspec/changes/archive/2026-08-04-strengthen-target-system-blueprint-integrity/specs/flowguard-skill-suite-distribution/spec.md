## MODIFIED Requirements

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

## ADDED Requirements

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
