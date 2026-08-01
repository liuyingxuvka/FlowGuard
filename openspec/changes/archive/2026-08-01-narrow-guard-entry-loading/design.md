## Context

The observed model-system snapshot already assigns this work to `guidance_compression`, `self_maintenance_mesh`, `minimum_valuable_model_entry`, `existing_model_preflight`, and `release_visibility_process`. The existing `RouteProfile` registry is the current route authority. The current prompt manifest duplicates load information and incorrectly treats `modeling_protocol.md` as absent from the kernel's guaranteed load despite the shell requiring it. Existing Model Preflight already selects observed instances correctly, but its final primary-owner projection check compares only ledger owner text to `ModelContextHit.model_id`.

The change must preserve fifteen public skills, direct satellite routing, current-only authority, task-local model maturation, peer work, and SkillGuard author supervision. It must not run the final full maintenance-unit gate, install, publish, tag, or release during this implementation work.

## Goals / Non-Goals

**Goals:**

- Make route selection cheap and deterministic enough to avoid unrelated prompt material.
- Preserve full route-native depth after a named trigger.
- Use one route/load authority and fail when documentation, manifest, or projection drifts.
- Repair exact current-owner reconciliation without partial-token fallback.
- Provide one repeatable, current-format revision builder that proves receipt freshness and exact affected-owner coverage before the existing activation transaction.
- Leave focused, reusable model and test evidence for a later frozen full gate.

**Non-Goals:**

- No new universal Guard, router, compatibility reader, or public route.
- No reduction of native closure obligations or replacement of task-local maturation with a self-rating scale.
- No installation, Git commit, push, tag, GitHub release, or final parent validation.
- No provider token estimator; source-size telemetry remains a regression proxy.
- No implicit model execution, authority activation, fallback receipt reader, or compatibility revision format in the revision builder.

## Decisions

### 1. Extend `RouteProfile`; do not create an admission service

Add structured condition ids, forbidden ids, first action, reference edges, deepening triggers, and claim boundary to the existing profile. A small deterministic selector consumes caller-extracted task facts and returns exactly-one, none, or conflict. This keeps route authority with the current topology. A standalone router was rejected because it would duplicate route ownership and require a second parity surface.

### 2. Make the skill shell the unconditional-load declaration

Use a constrained `## Local Material Routing` grammar: `Read ... before route selection` marks unconditional references; `after`, `when`, or `only when` marks conditional edges. The manifest keeps ceilings, minimum headroom, and allowed conditional paths. The checker derives unconditional paths from each selected shell and fails on manifest drift. A fully separate JSON load graph was rejected because it would become a second manual owner of prompt behavior.

### 3. Charge only guaranteed material to first-read budgets

For the kernel, the guaranteed bundle is root/project guidance, the selected shell, and `route_index.md`. `modeling_protocol.md` becomes conditional on selecting the kernel. Route protocols remain guaranteed for direct satellites only when their shell unconditionally says to read them. Reports include conditional edges but do not charge them to the initial total. Minimum headroom defaults to ten percent of the configured ceiling, with an explicit per-bundle override allowed only when documented.

### 4. Reconcile owner identities through observed instances

Build a current `OwnerIdentityIndex` from logical id, normalized path, absolute/repository-relative equivalent path, and fingerprint for each observed instance. Both lookup selection and final projection validation use this index. Exact identities and safe path form equivalence are allowed; basename and token containment are not. Multiple matches produce an ambiguity finding.

### 5. Keep deep rules in their existing unique references

The kernel shell and generated project prompt keep only route admission, first action, current-authority requirement, no-fake-adoption boundary, and conditional handoffs. Modeling, evidence, maturation, replacement, composition, release, and provider rules remain in their current single reference owners. The route index is generated or parity-checked against `RouteProfile`, and `openai.yaml` instructs route-first reading rather than eager core-protocol loading.

### 6. Extend the existing AI trigger model for missing public routes

Add task facts and scenarios for the five missing routes and add candidate-set conflict semantics. The model continues to use `Input x State -> Set(Output x State)`. Positive scenarios prove reachability; near-neighbor and forbidden scenarios prove discrimination; conflict scenarios prove fail-closed behavior.

### 7. Use affected-only validation and defer the one final gate

During implementation, run prompt-budget, route-profile/topology, trigger-model, Existing Model Preflight, project-adoption, skill-doc, contract-generation, and changed-model checks. Refresh contract source/compiled/check-manifest through the repository's existing generator. The parent task will freeze the cross-repository integration snapshot before the one final maintenance-unit validation and release flow.

### 8. Separate typed revision generation from atomic activation

Add one public Python API and one thin `model-revision-build` CLI. The builder loads the sole observed head, reconstructs the live candidate from the current manifest, derives the canonical snapshot diff and affected closure, and accepts a `ModelRevisionSet` only from one full model-regression parent receipt whose manifest, complete child set, terminal disposition, current input fingerprints, producer/toolchain identity, environment identity, obligations, and native owner coverage all verify exactly. It writes immutable content-addressed snapshot and revision JSON under the standard model-mesh store or a caller-selected output root, reports their exact paths/fingerprints, and never changes the authority pointer. The existing `model-revision-activate` command remains the sole activation owner. Handwritten revision JSON and the old release-specific helper pattern were rejected because they can silently bind stale owners or omit current models.

## Risks / Trade-offs

- **[Documentation wording becomes executable input]** → Keep the unconditional-load grammar small, test it with fixtures, and reject ambiguous `Read` directives.
- **[A compact shell accidentally drops a hard gate]** → Map every removed paragraph to one existing reference owner and run guidance-compression plus skill-doc checks.
- **[Route conditions become another keyword router]** → Conditions are stable feature ids consumed from structured task facts; near-neighbor and conflict tests forbid lexical/default-order selection.
- **[Path normalization overmatches]** → Permit only exact normalized ids, exact normalized paths, safe absolute/relative equivalence, or exact fingerprints; add basename and wrong-fingerprint known-bads.
- **[Ten-percent headroom is infeasible for one route]** → Split that route's optional protocol material by an explicit trigger; do not raise the limit merely to pass.
- **[Parallel edits stale evidence]** → Re-read touched files before every patch, preserve peer changes, and rerun only owners affected by the final merged content.
- **[A parent receipt says pass but its inputs are no longer current]** → Rebuild the current model-owner contracts, require every parent child to be the independently verified exact-current receipt, and reject any manifest, child, toolchain, environment, obligation, skip, or blocker mismatch.
- **[Generation accidentally becomes a second activation path]** → Keep the builder pointer-free and test that the observed head is byte-identical before and after generation.

## Migration Plan

1. Freeze current route, load, owner, model, and contract identities.
2. Add the derived-load checker and tests before shrinking prompt text.
3. Extend route profiles and trigger-model coverage; keep old public route ids unchanged.
4. Repair owner reconciliation and its regression cases.
5. Shrink the kernel/project prompt and refresh generated projections/contracts.
6. Run affected model and test owners, bump to `0.68.2`, and leave installation/release to the frozen parent integration phase.
7. After the final full model-regression owner produces an exact-current parent receipt, generate the accepted candidate/revision pair, activate it only through the existing atomic command, and then run authority/project audits before the frozen final gate.

Rollback before publication is a scoped source revert of this change's owned paths followed by affected revalidation. After publication, correction requires a new immutable patch version rather than moving a tag.
