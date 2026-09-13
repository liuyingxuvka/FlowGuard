## Context

See `proposal.md` for the motivation and `specs/` for observable contracts. The current repository already has content-addressed snapshots, accepted `ModelRevisionSet` transitions, affected-closure helpers, light/affected/full profiles, supervised process execution, and direct-current SkillGuard contracts. The gaps are at the seams: first bootstrap produces a generation that the ordinary loader rejects, light preflight performs a global audit before selecting an owner, completion identity mixes functional and release inputs, and the self-maintenance input includes pointer metadata.

## Goals / Non-Goals

**Goals:**

- Make a finite one-to-two-model consumer usable from first adoption through local current navigation and one affected update.
- Keep the existing single observed authority and pointer-last revision transaction, while separating semantic functional inputs from transaction bindings.
- Make local completion and release qualification explicit scopes with a stable work budget and bounded process cleanup.
- Ensure the author-maintained FlowGuard skill source can be refreshed once, frozen once, and finally validated once under SkillGuard ownership.
- Keep convergence target-neutral: an external target supplies its own functional parent, version, source/assets, and checks; FlowGuard is only the verifier identity. Recursive model composition uses one bottom-up walk for any finite depth and never starts a full run per level.

**Non-Goals:**

- Rewriting the existing five-layer ModelMesh/TestMesh semantics or proving arbitrary software's entire Cartesian state space.
- Removing content hashes, stale/corrupt/foreign evidence gates, exact release verification, or the single-authority rule.
- Deleting or relocating temporary evidence, historical receipts, structure-reduction candidates, or other projects.
- Making ordinary consumer use depend on SkillGuard, author shadow/install roots, remote CI, Linux, or release publication.

## Decisions

### 1. Use a typed initial-intent gap for first adoption

The existing normal revision builder correctly rejects an empty same-source revision. First adoption therefore creates a private pending snapshot whose unresolved gap is `initial_current_intent_unaccepted:<logical_model_id>` for every materialized consumer model. The existing typed affected-closure and v5 revision verifier consume those gaps; closing them requires real intent, owner binding, and leaf/connection evidence. This preserves the ordinary empty-revision rejection and avoids changing a snapshot name or source comment merely to manufacture a diff.

Alternative rejected: make generation-one bootstrap readable as current. That would create a second success contract and leave incomplete intent hidden.

### 2. Select a local owner before global audit

Existing authority integrity is checked without re-reading the entire live inventory. The reader resolves exact model, runner, input, intent, contract, and typed relation paths from the accepted snapshot, reads only the selected closure once, and returns integrity, selected-source currentness, and execution-evidence statuses separately. A requested deep projection remains a separate blocked claim when missing. No lexical or root-wide fallback is added.

Alternative rejected: suppress all audit failures globally. Corrupt, unsafe, foreign, or selected-content-stale objects still block the claims that rely on them.

### 3. Split semantic fingerprints from authority binding

The semantic projection of `.flowguard/project.toml` retains engine/schema/policy/toolchain and true selected-content inputs. Generation, head, snapshot path, activation receipt, reverse binding, report, and task-checkbox fields are transaction/output context. A pointer-last commit validates candidate reachability, CAS, and binding integrity once, then writes the sole pointer. Functional owner identities are computed from the semantic projection and selected model payload, not from the transaction IDs.

Alternative rejected: ignore the whole project file. That would allow real policy or toolchain changes to bypass freshness.

### 4. Separate local validation from release claims

`claim_scope=local_validation|release` travels through owner plan, parent receipt, completion epoch/readiness, run manifest, and release verification. Local validation does not build a release tree. Release combines exact current local evidence with a separate release-tree/install identity and never relabels local evidence. Existing release reachability (boundary, predecessor, rollback chain) remains required only for release scope.

### 5. Make work identity stable and process execution bounded

`completion_work_id` is distinct from mutable objective fingerprints, output paths, and epochs. One work item permits one initial production plus one typed repair. Plan/readiness/reuse/report operations do not consume attempts. Git and producer subprocesses use one supervised tree-kill implementation, byte-preserving I/O, per-query deadlines, and a finite aggregate observation budget. Cleanup-unconfirmed evidence is never reusable.

### 6. Make change scope explicit

Patch regression receives a signed/current `flowguard.patch_change_manifest.v1`. Its `planned_changed_paths` selects owners. `observed_drift_paths` records whether inputs changed during execution and invalidates a receipt when functional inputs drift. Empty semantic delta means no activation, not all-model authorization. Typed relation endpoints determine review ownership; alphabetical or substring guesses are rejected.

### 7. Keep author projection as a final frozen phase

All 15 registered source skills, contracts, self-blueprint, consumer authority, shadow/install projections, and model review inputs are reconciled before the one final author full. Ordinary consumer tests never call this author full. Existing `SkillGuard` direct-current rules remain in force; there is no compatibility reader or alternate writer.

### 8. Use one target-neutral release consumer

The release verifier accepts an explicit target descriptor and a functional parent. The descriptor carries the target's version/tag/repository/branch/distribution policy and required target-owned checks; it does not infer these from FlowGuard's own package metadata. FlowGuard's tool identity is recorded separately. A target may be FlowGuard itself, but self-publication has no separate verifier fast path. Candidate, tag, and published records consume the same candidate binding and never become functional inputs.

## Risks / Trade-offs

- **[Risk]** A two-model fixture may not expose every topology error in a large system. → Keep existing five-layer and cross-boundary native tests, and require a real dependent-connection negative scenario in the consumer fixture.
- **[Risk]** Removing global gating from light reads could hide unrelated drift. → Return `authority_integrity` and selected currentness separately; global drift still blocks explicit whole-system/release claims.
- **[Risk]** Pointer metadata may be incorrectly classified as semantic. → Use one typed projection function and tests for policy-versus-pointer changes; never ignore the whole file.
- **[Risk]** A bounded attempt budget can stop before a genuine repair is complete. → Permit one typed repair with exact failed owner/input evidence, then return a durable finite failure rather than silently looping.
- **[Risk]** Existing dirty or parallel work can race the final CAS. → Freeze and compare exact manifests under the existing lock; on conflict preserve candidate and diagnostics and do not overwrite the peer head.

## Migration Plan

1. Implement the affected modules and tests under the new OpenSpec change while preserving historical receipts and existing authority objects.
2. Run targeted tests after each bounded area; do not invoke the final full until source, contracts, model inputs, and projections are frozen.
3. For a consumer with no authority, use the new first-adoption transaction. For the existing author repository, keep the current generation and use one accepted revision only if actual selected content changed.
4. Refresh direct-current source contracts and projections once under SkillGuard, then run one final author validation and one reuse-only terminal check.
5. If implementation must be rolled back, restore only the newly written current pointer under its CAS contract; retain immutable candidate, receipts, and diagnostics. No legacy reader or migration path is introduced.

## Open Questions

None. Any new behavior, owner, external release claim, or schema change outside these decisions is a new scoped change, not an executor choice.
