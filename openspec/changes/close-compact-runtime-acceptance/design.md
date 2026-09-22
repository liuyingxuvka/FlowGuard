## Context

The proposal is implemented over a dirty but identity-pinned source worktree
that already contains historical OpenSpec changes and a published `0.69.5`
release. The audit package records the exact C00-C13 order, current failures,
protected test inventories, and source/release boundaries. The design must
allow implementation agents to repair the compact runtime while keeping the
old changes as historical context and keeping source, model authority,
consumer installation, and publication as separate claims.

## Goals / Non-Goals

**Goals:**

- Use one ordered acceptance graph: prepare identity, repair native/map/model
  behavior, complete consumer and protection closure, run joint journeys,
  accept the current self-model, freeze, run one final full suite, and package
  only matching evidence.
- Keep one execution owner per semantic check and one evidence subject per
  maintenance unit; preserve exact blocked, stale, skipped, and not-run states.
- Keep FlowGuard's public map useful for selected reads and incremental growth
  while reducing producer work and avoiding all-map/fallback reads.
- Verify clean consumer independence before any installation or release claim.

**Non-Goals:**

- Reopening or mass-checking historical OpenSpec changes.
- Deleting historical tags/releases, changing the user HOME installation, or
  publishing a candidate during this change.
- Restoring compatibility readers, old schedulers, aliases, or fallback routes.
- Treating narrow CI success, source-only checks, or a model snapshot as final
  runtime, installation, or future-AI correctness evidence.

## Decisions

1. **One named change owns the closeout.** The repository-local change is
   `close-compact-runtime-acceptance`; historical changes stay immutable. A
   same-named change in SkillGuard carries the corresponding target-owned
   contract and shares only the cross-Guard acceptance boundary, never receipts.

2. **Current identity is frozen before execution.** C00 records source HEAD,
   tracked bytes, interpreter, clean workspace, package identity, and remote
   boundary. Every later receipt refers to this identity. A mismatch blocks and
   requires a new prepared identity; it is not repaired by widening the source
   scope.

3. **Typed native evidence is the owner boundary.** Producers return explicit
   typed cases and real path evidence. Output scraping and mutable global
   capture are removed because they cannot distinguish a missing case from a
   successful process. A typed result is preferred over a new parser or
   compatibility reader.

4. **Writer-bound selected reads are the map boundary.** One writer creates
   payload, shards, index, and acceptance binding. Readers consume only the
   selected accepted shards. Ancestor-cache search and full-map rescue are
   excluded because they hide stale or unrelated work and defeat bounded cost.

5. **Model acceptance is after implementation evidence.** The model candidate
   is rebuilt from actual current source inputs and relations, native evidence
   is current, and only then is the normal FlowGuard authority transaction
   allowed to accept the self-model. This avoids freezing a model that is
   immediately stale.

6. **Installation is a transaction in a clean process.** A staged projection
   is preflighted, fully rechecked, swapped, read back, and rolled back on
   failure. The clean interpreter is explicitly isolated from editable finders,
   author sources, and the other Guard. This gives installation a separate
   claim boundary without duplicating the runtime.

7. **Protection inventory is the denominator.** The C08 owner reconciles the
   exact retained/ported/retired inventory and current test distribution. Counts
   are evidence, not deletion targets; any missing or ambiguous owner blocks.

8. **Freeze precedes final validation and packaging.** C10 accepts current
   model/self evidence and records the final identity. C11 runs one full
   Windows 3.12 owner and only reads the resulting native/self identities.
   C12 validates measurements and packages source-safe evidence. C13 remains a
   later, separately authorized publication step.

## Risks / Trade-offs

- [Dirty parallel worktree] → use only the declared isolated worktree and
  record file ownership before each batch; do not reset or stage unrelated
  changes.
- [Model acceptance changes tracked authority] → accept the model before the
  final freeze, then freeze all model inputs and reject post-freeze tracked
  authority changes.
- [Legacy tests encode retired API shapes] → use the audited fixed-edit and
  protection disposition tables; do not delete a file to hide a retained
  assertion or add a compatibility shim.
- [Clean consumer import differs from source-test import] → run the target
  operation from the explicitly constructed clean interpreter and inspect
  `sys.path`, `sys.meta_path`, and `find_spec` results.
- [Remote branch or release moves] → record the exact mismatch as blocked and
  stop publication; never force-push or overwrite an existing release.

## Migration Plan

1. Execute C00 and create the prepared identity.
2. Implement and validate C04-C07 in the FlowGuard owner scope; coordinate C01-
   C03 in SkillGuard without shared files or receipts.
3. Execute C08 collection/protection migration and CI denominator repair only
   after both compact owner scopes are stable.
4. Execute C09 journeys and measurement fixture collection.
5. Execute C10 model acceptance and delivery freeze; if any identity changes,
   repeat the affected preparation and freeze rather than reusing evidence.
6. Execute C11 once, then C12 read-only verification and package generation.
7. Leave C13 blocked until the user explicitly authorizes the future patch
   publication and the remote preconditions remain true.




## 2026-09-22 audit delta

The earlier checked receipts describe the historical v0.69.6 state and are not current proof for the next patch. This change remains open until the direct-current compact contract is revalidated after the final source edits. The current public surface is exactly `read`, `change`, and `release`; retired commands, route catalogs, migration metadata, aliases, compatibility readers, and fallback paths are removed rather than interpreted. The selected-read/owner evidence, current model or contract identity, one final Windows 3.12 full-suite owner, installation parity, and release identity must all be re-established on one frozen source revision. Documentation and CI are part of that frozen source identity.
