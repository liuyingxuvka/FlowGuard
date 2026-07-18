## Context

FlowGuard has two legitimate but currently conflated lives. In its canonical author repository, SkillGuard can cultivate the 17 skills, compile contracts, execute target-declared checks, and gate release. On a consumer machine, those same 17 skills must be ordinary independent FlowGuard skills. The current suite inventory, installed-layout tests, target prompts, distribution sync, project adoption, shadow sync, and former specification work-package implementation allow author-control state to cross that boundary.

Five uncommitted files in the working tree separately move SkillGuard V2 authority from compiled contracts toward source and manifest ownership. Their focused native-check tests pass, but the full related group currently fails because the 17 generated contracts have not been regenerated. This change preserves that work and treats it as a separate input migration, not as proof of consumer separation.

The existing FlowGuard model and OpenSpec owners remain authoritative. This change revises them in place and adds no parallel installer, suite, adoption, or specification bridge.

## Goals / Non-Goals

**Goals:**

- Keep complete SkillGuard maintenance in the FlowGuard author repository.
- Produce and install 17 independent consumer skills containing no SkillGuard state or runtime dependency.
- Make ordinary FlowGuard project adoption write only FlowGuard-owned `.flowguard` state and FlowGuard instructions.
- Preserve all FlowGuard native behavior, routes, prompts, references, scripts, assets, checks, and claim boundaries.
- Treat official OpenSpec authoring artifacts as read-only development context.
- Safely withdraw previously installed SkillGuard files only when installer ownership and unchanged hashes prove removal is safe.
- Preserve dirty peer work and independently validate the V2 contract-source migration.

**Non-Goals:**

- FlowGuard does not replace SkillGuard's author-side contract compiler or release supervision.
- FlowGuard does not maintain, wrap, or modify official OpenSpec skills.
- This change does not retain old consumer contract layouts, receipt bridges, sessions, caches, aliases, or fallback readers.
- It does not delete user-modified installed files.
- It does not claim that package installation alone proves agent behavior.

## Decisions

### 1. Two explicit inventories

`MaintainerSourceInventory` validates the canonical author tree and may require `.skillguard` control material. `ConsumerDistributionInventory` validates the 17 target-owned release trees and rejects `.skillguard`, SkillGuard markers, commands, imports, receipts, Portfolio data, and router state.

Both inventories derive the same 17 stable skill identities and target-owned required files from one canonical member table. They have separate allowed-path and prohibited-path policies, separate hashes, and separate reports.

Alternative considered: one validator with an optional flag. Rejected because a permissive mode makes it too easy to validate the wrong projection and hides which claim was proven.

### 2. Consumer artifacts are built, not copied from author roots

Distribution sync constructs a staged consumer tree from explicit target-owned paths. It never recursively copies each author skill directory and then deletes `.skillguard`. The staged tree is scanned, checked for declared reference completeness, and atomically activated.

Alternative considered: copy-then-filter. Rejected because new author-only paths could escape the filter and because deleting hidden runtime after copying is unsafe.

### 3. Withdrawal is ownership-aware

The install manifest records every consumer-owned path and hash. During an upgrade from an old release, a now-retired `.skillguard` file is removed only when the previous FlowGuard installer manifest owns it and its current hash still matches. Modified or unowned files remain in place and are reported as conflicts.

No broad recursive `.skillguard` deletion is allowed.

### 4. Project adoption is FlowGuard-only

`project-adopt`, `project-audit`, and `project-upgrade` operate on `.flowguard/project.toml` and a FlowGuard-managed `AGENTS.md` block. They do not discover, require, install, or repair SkillGuard, its router, contracts, or project state. Eligibility and report schemas explicitly assert `skillguard_project_writes: 0`.

### 5. Shadow sync is maintainer-only

Shadow synchronization requires a repository-owned registry entry identifying the target as a maintainer worktree. It may synchronize author material only between registered FlowGuard maintenance roots. Arbitrary project roots and consumer installations are rejected before writes.

### 6. Specification context has no execution plane

`SpecContext` contains the fixed provider id `openspec`, a project-bounded change
id, project-relative proposal/design/specification/task paths and hashes, task
checkbox counts, and derived status. It contains no other-provider adapter,
provider version contract, obligation mapping, target relation, command, check
owner, session, cache, input snapshot, receipt id, archive-readiness
projection, or SkillGuard state.

FlowGuard uses this material only to understand requested scope and plan its
own work. DevelopmentProcessFlow and TestMesh own FlowGuard evidence
independently; they do not reconcile OpenSpec tasks into execution owners or
project FlowGuard completion back into OpenSpec.

Alternative considered: retain receipt projection but stop cross-skill reuse. Rejected because even a non-reused provider receipt still makes provider state part of FlowGuard validation authority.

### 7. Prompt and contract projections are separated

Consumer `SKILL.md` files retain target-specific activation, workflow, hard gates, output, and claim boundaries, but remove `SkillGuard Maintenance`, runtime rules, contract trio, receipt consumption, and router onboarding. Author contract sources remain in the canonical author repository and may fingerprint the consumer prompt as an input.

### 8. The dirty V2 migration is a separate validation slice

The five existing uncommitted files are preserved. Native-check authority changes are tested separately. Assertions about removing `depth_profile` from compiled contracts are accepted only after the SkillGuard compiler authority and all 17 generated author contracts are frozen and regenerated. Consumer installed-layout tests stop using author compiled-contract shape as a release-layout requirement.

## Risks / Trade-offs

- **[A consumer file referenced from `.skillguard/runtime` is lost]** → Block the build on reference/import/data scanning and relocate target runtime before exclusion.
- **[Author contracts stop seeing the exact consumer prompt]** → Fingerprint the staged consumer entrypoint in maintainer-control compilation and parity checks.
- **[Upgrade removes a user's local file]** → Require prior installer ownership plus exact unchanged hash; otherwise preserve and report.
- **[Two inventories drift]** → Derive stable membership from one canonical table and reject duplicate private member lists.
- **[Dirty V2 work is accidentally normalized as passing]** → Keep separate focused tests and do not mark its generated-contract tasks complete until all 17 author contracts agree.
- **[OpenSpec context is mistaken for proof]** → Mark every projection
  `read_only_external`, include an explicit claim boundary, and reject any
  session/cache/receipt/execution fields.

## Migration Plan

1. Freeze current source, dirty-file hashes, installed layouts, and the 17-member canonical identity set.
2. Update existing FlowGuard models for maintainer source, consumer distribution, project zero-write, shadow eligibility, and read-only specification context.
3. Introduce the two explicit inventory types and failing consumer-prohibition tests.
4. Build the staged consumer distribution and ownership-aware installer/withdrawal path.
5. Remove SkillGuard sections from all 17 consumer prompts and update prompt-parity validation.
6. Contract project adoption and shadow sync.
7. Replace the provider-neutral specification work-package bridge with
   read-only official OpenSpec `SpecContext`.
8. Resolve and regenerate the separate V2 author-contract migration.
9. Run focused tests, then install into a clean `CODEX_HOME` and adopt an empty project.
10. Synchronize the local installed 17-skill projection and author source, freeze one final owner, and run one final full validation.

Rollback restores the previous complete consumer installation transaction and leaves author-maintenance source/evidence intact. It never enables an old receipt bridge or consumer SkillGuard fallback.

## Open Questions

None. The author/consumer boundary, official OpenSpec exclusion, same-unit evidence rule, dirty-work preservation, and complete local synchronization were explicitly selected.
