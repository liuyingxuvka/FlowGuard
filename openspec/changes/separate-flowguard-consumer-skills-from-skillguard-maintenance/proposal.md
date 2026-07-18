## Why

FlowGuard's author repository is legitimately maintained with SkillGuard, but its 17 graduated skills, installer, and project-adoption path currently carry SkillGuard contracts and prompt dependencies into consumer machines and ordinary business projects. FlowGuard must preserve its own models, native checks, and project records while treating SkillGuard as author-only release supervision.

## What Changes

- **BREAKING** Split FlowGuard's SkillGuard-maintained source inventory from its independent 17-skill consumer distribution.
- **BREAKING** Exclude `.skillguard/**`, SkillGuard prompt blocks, commands, imports, receipts, router state, and Portfolio state from every FlowGuard consumer skill.
- **BREAKING** Remove SkillGuard and SkillGuard Global Router from FlowGuard project adoption and installed-layout requirements.
- **BREAKING** Replace specification-provider integration with official OpenSpec
  proposal, design, specification, task, and derived-status context only;
  remove other-provider adapters, provider sessions, caches, check execution,
  owner plans, reconciliation, and receipt projection.
- Add separate maintainer-source and consumer-distribution inventories with explicit validation and release manifests.
- Make consumer installation staged, rollbackable, ownership-aware, and safe when withdrawing previously installed SkillGuard files.
- Restrict shadow-workspace synchronization to explicitly registered maintainer worktrees.
- Preserve FlowGuard's `.flowguard` project adoption, native scenario/model checks, public skill behavior, and author-side SkillGuard maintenance.
- Keep the existing uncommitted SkillGuard V2 contract-source changes as a separately validated migration rather than silently folding them into consumer separation.

## Capabilities

### New Capabilities

- `flowguard-consumer-independence`: Clean 17-skill consumer projection, isolated installation, zero SkillGuard dependency, and ordinary-project zero-write behavior.
- `flowguard-maintainer-consumer-inventories`: Separate source-maintenance and consumer-distribution inventory authorities with exact parity checks.
- `spec-context`: Current, project-bounded, read-only official OpenSpec authoring context with no execution or evidence authority.

### Modified Capabilities

- `flowguard-skill-suite-distribution`: Distribution construction and installation exclude all SkillGuard author-control material.
- `flowguard-suite-inventory`: Inventory validation distinguishes author source requirements from consumer release allowances and prohibitions.
- `project-adoption-version-gate`: Ordinary project adoption installs only FlowGuard-owned `.flowguard` state and instructions.
- `spec-provider-work-packages`: Retire the provider-neutral work-package,
  reconciliation, session, cache, receipt, and execution bridge.
- `flowguard-skill-contract-governance`: SkillGuard contract material remains an author-source concern and is not an installed-skill layout requirement.

## Impact

- The 17 `skills/flowguard-*` and `skills/model-first-function-flow` source packages, their installed projections, and prompt content.
- `flowguard/distribution_sync.py`, `flowguard/skill_suite.py`,
  `flowguard/project_adoption.py`, the read-only OpenSpec context reader, and
  public package APIs.
- `scripts/install_flowguard_skills.py`, `scripts/sync_shadow_workspace.py`, author-maintenance checks, distribution manifests, and related tests.
- Existing FlowGuard models for skill contracts, suite distribution, project
  adoption, read-only OpenSpec context, and development-process validation.
- Local installed FlowGuard skills, clean `CODEX_HOME` fixtures, ordinary project fixtures, source and installed Git synchronization.
