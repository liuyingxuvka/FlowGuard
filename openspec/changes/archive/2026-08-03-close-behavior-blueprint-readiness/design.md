## Context

See `proposal.md` for motivation. The current v0.68.6 candidate already has a project-neutral Python blueprint builder, independent implementation/test inventories, 65 observed model owners, static depth reporting, intent contribution types, clean consumer distribution, and explicit `empirical_reconstruction=not_run`. The audit found that most semantics, oracles, and test evidence are still shared at model-owner granularity; the full binding projection repeats shared evidence heavily; intent lineage and resource completeness can pass from empty or caller-defined denominators; and an interrupted final validation left ordinary leases plus a child pointer that could be mistaken for parent success.

The worktree contains a large staged candidate produced alongside other agents. The implementation must preserve all existing staged paths, avoid broad rollback or repo-wide rewriting, and treat any later peer write as an invalidation signal only for affected evidence.

## Goals / Non-Goals

**Goals:**

- Make FlowGuard mechanically know whether it has owner-level structure, behavior-block detail, reconstruction readiness, or empirical reconstruction evidence.
- Require exact behavior/test/resource/intent denominators without making every internal helper an external contract.
- Let FlowGuard help supported external projects build honest candidate blueprints whose unknowns remain visible.
- Keep ordinary use affected-only and make the full logical blueprint much smaller through normalization.
- Close interruption, self-reduction, installation, validation, and release evidence boundaries.

**Non-Goals:**

- Running clean-room or full reconstruction during ordinary work, audit, cleanup, install, or release.
- Reproducing byte-identical source or embedding production source text in the blueprint.
- Adding a standalone DNA skill, a second model authority, compatibility reader, fallback owner, or run-all recovery path.
- Providing deep non-Python discovery in this patch.
- Requiring direct unit tests for every pure helper.

## Decisions

### 1. Keep the existing seven blueprint layers and add explicit sub-decisions

The canonical layer order remains `inventory`, `traceability`, `independent_semantics`, `model_code_test`, `resource_oracle`, `static_blueprint`, and `empirical_reconstruction`. `static_blueprint` gains separately reported owner-structure and behavior-block closure components, and a new derived `reconstruction_readiness` decision sits beside—not above or inside—empirical reconstruction.

This preserves current consumers and the sole observed authority while preventing an owner-level green result from licensing the stronger claim. Adding a new DNA mode or a second blueprint authority was rejected because it would duplicate ownership and encourage ordinary tasks to widen scope.

### 2. Model important behavior blocks, not every helper

Independent inventory classification already distinguishes behavior-bearing and supporting surfaces. Every behavior-bearing surface receives a `BehaviorBlockContract`; a pure helper closes through one unique `supports`/`calls` edge to a behavior block. Each block records dimension applicability and concrete semantics. Owner-level defaults may seed candidates but can never complete a block.

This avoids both current over-coarseness and the opposite failure of forcing thousands of meaningless helper contracts.

### 3. Normalize shared objects and add exact coverage edges

Owner contracts, semantic rules, oracles, test nodes, assertions, native-check members, and receipts become content-addressed shared objects. `BehaviorCoverageBinding` rows reference them and record surface-specific dimensions and case roles. Canonical logical serialization expands references deterministically for equality/fingerprint review, while physical shards store shared objects once.

The current approach of copying an owner's whole test set onto every surface is retired by direct replacement. No compatibility reader or dual emitter will be added.

### 4. Separate test design from current execution

Static blueprint closure requires complete exact test/checker design bindings and a terminal execution disposition for every row. `not_run` remains visible and never becomes pass. Reconstruction readiness can evaluate whether a reimplementation has sufficient tests and oracles without executing them; release confidence separately requires current terminal success from the native execution owners.

This keeps the model useful before code and avoids turning every readiness query into a full test run.

### 5. Derive independent resource and intent denominators

Resource discovery combines declared project boundaries, registered language/build adapters, manifests, imports, configuration and migration surfaces, explicit external-service declarations, and test/runtime launch contracts. Every category and member has a terminal disposition. It does not package secrets or live data.

Intent inventory is projected from explicit WorkContexts, OpenSpec, changelog/history, and task facts. Non-trivial revisions must consume the inventory or an evidence-bound no-intent rationale. Source prose alone cannot create accepted intent.

### 6. Candidate generation never self-licenses

The candidate builder reuses the same project-neutral inventory adapters and returns an in-memory definition plus gaps. Possible owners and source-derived semantics are `candidate`/`unresolved` until accepted through current model, intent, contract, or oracle evidence. Explicit export is a separate command and still does not reconstruct.

### 7. Reconstruction readiness is a pure review

`review_reconstruction_readiness(...)` consumes immutable fingerprints for behavior blocks, coverage bindings, resources, intents, oracles, topology, and canonical projection. It returns `ready|incomplete|stale|blocked`, all findings, deepest proven layer, first gap, and claim boundary. It has no file-system, process, network, install, authority, or reconstruction side effects.

### 8. External-interrupt settlement is exact and evidence-producing

An external settlement API accepts an exact plan id, exact residual lease ids/owners, the former process identity, a current zero-descendant observation, and an operator reason. Under the lifecycle lock it revalidates every lease, writes one immutable interrupted incident, and removes only those exact lease files. Any live, changed, foreign-plan, unknown, or already-replaced lease blocks the transaction.

Child runs publish child-local current pointers. The parent pointer is written only in the parent's terminal composition path. Existing partial child successes remain ordinary child evidence but are never promoted to the interrupted parent.

### 9. Self-reduction is a first-class release child

FlowGuard self-qualification derives the expected reduction candidate ids from the current blueprint and same-intent inventory, runs ArchitectureReduction in review-only mode, and stores a machine report bound to the blueprint fingerprint. Actual contraction continues through StructureMesh and DevelopmentProcessFlow; the review itself never edits code.

### 10. One frozen final gate follows all source and installation changes

Affected tests and model checks run during development. After OpenSpec, model authority, version, docs, SkillGuard validation, package/editable install, consumer projection, and shadow parity are stable, the release workflow freezes one owner plan. The final parent includes the existing owners plus explicit `self_blueprint` and `architecture_reduction_review` children. It runs under one foreground owner; unrelated diagnostics may run in parallel earlier, but no unattended full validation, scheduled retry, or background resume is permitted.

## Risks / Trade-offs

- **[Behavior contracts could explode in count]** → Keep helper surfaces supporting, group only genuinely identical behavior cells, and shard by owner/affected neighborhood.
- **[Source-derived candidate semantics may appear authoritative]** → Use typed unresolved status and require independent acceptance before closure.
- **[Assertion parsing is incomplete for dynamic tests]** → Preserve unknown case/fixture generation as blockers and allow exact native-check members with explicit boundaries.
- **[Resource discovery cannot infer secrets or unavailable external data]** → Record external/blocked dispositions and required shape/oracle contracts without copying private values.
- **[Changing blueprint schemas can invalidate large evidence sets]** → Direct-current replacement, component-edge invalidation, affected-only checks during development, and one full gate after freeze.
- **[Interrupted lease settlement could remove another owner's live lock]** → Exact plan/lease/process match, fresh zero-descendant proof, lifecycle lock, immutable incident, and all-or-nothing transaction.
- **[Large staged peer-owned work may drift during implementation]** → Re-read changed paths at each milestone, never rollback, and invalidate only affected evidence.

## Migration Plan

1. Add schemas, pure review APIs, and known-bad regressions without changing current authority.
2. Replace owner-wide copied bindings with normalized shared objects and exact behavior coverage rows; reject old projection schema directly.
3. Add candidate/resource/intent/readiness and interruption settlement APIs plus read-only CLI surfaces.
4. Update FlowGuard self definition, models, skills, docs, and release owner plan; run focused checks.
5. Use the new exact settlement path for the ten known dead-process residual leases and retain the interrupted incident as non-reusable evidence.
6. Build and accept one atomic ModelRevisionSet for every affected model and activate the new observed snapshot last.
7. Complete OpenSpec verification/archive, SkillGuard affected and final unit checks, install/package/consumer/shadow synchronization, and README/privacy review.
8. Freeze and run one final parent validation. Only after terminal pass, commit, tag, push, publish the source-only patch release, and verify remote identities.

Rollback before publication restores the previous source/model head only when all changed state is restorable; after publication, any defect receives a new patch version rather than moving the tag.
