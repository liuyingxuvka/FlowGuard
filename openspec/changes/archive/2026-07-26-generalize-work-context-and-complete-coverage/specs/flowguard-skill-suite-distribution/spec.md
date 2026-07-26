## ADDED Requirements

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
