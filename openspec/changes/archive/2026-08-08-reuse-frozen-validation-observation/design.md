## Context

The current validation-owner primitives correctly fail closed, but high-level model operations repeatedly call the complete planning and verification stack. A 51-model full regression had about 13 minutes of child tool time while parent construction added several more minutes, and one six-owner model-revision evidence build spent roughly eight minutes repeatedly rebuilding the same child closure. See `proposal.md` for motivation and the three delta specifications for the required observable boundaries.

The important constraint is that performance work must not convert current evidence into a cache or remove the final time-of-check/time-of-use protection. FlowGuard also has one canonical receipt store and one observed model head; neither may gain an alternate authority.

## Goals / Non-Goals

**Goals:**

- Represent a complete validation observation as an immutable, typed, invocation-local value.
- Resolve and natively verify each exact-current child once per frozen operation, then derive distinct owner aggregates from exact subsets.
- Perform one fresh final identity observation before publishing a parent or revision bundle.
- Make execution, reuse, observation, and composition cost visible without turning timing into proof.
- Preserve every current failure, ambiguity, lifecycle, ownership, and freshness condition.

**Non-Goals:**

- No persistent cache, daemon, database, compatibility format, fallback reader, alternate receipt store, or cross-process shared authority.
- No weakening of behavior-block detail, model/test/code bindings, negative cases, native child execution, or activation gates.
- No attempt to make unrelated model runners parallel without their existing shard-safety proofs.
- No broad rewrite of the validation framework or public API solely to obtain a smaller line count.

## Decisions

### 1. Use an immutable invocation-local observation

Add a typed observation that owns the resolved repository manifest, canonical receipt inventory, resolved current owner contexts, verified child receipts, source identity, and a canonical observation fingerprint. High-level callers create it at a named phase and pass it explicitly; global variables and implicit memoization are prohibited.

This is preferred over a persistent cache because exact-current evidence depends on repository, environment, toolchain, and receipt-store state. A persistent cache would create a second authority and introduce invalidation behavior more complex than the work being removed.

### 2. Separate initial semantic verification from final identity freshness

The initial observation performs normal native receipt verification and produces exact typed results. The final phase freshly resolves the governed repository and receipt identities, compares their canonical inventory with the frozen observation, and blocks on any difference. When identities match, it does not repeat native semantic verification because the verified objects are content-addressed and unchanged.

This is preferred over omitting the final phase because peer writes and receipt-store changes can occur during long operations. It is preferred over repeating the entire verifier because unchanged content-addressed objects cannot acquire different semantics within the same toolchain/environment identity.

### 3. Derive owner aggregates from exact subsets, then publish together

Model-revision evidence first derives a complete mapping from affected owners to exact child subsets. Each aggregate is built with its own subject and obligations from that frozen mapping. One bundle-level final freshness observation runs immediately before content-addressed aggregate publication, and the newly written aggregate identities are reloaded afterward; no aggregate calls the general planner independently and the output writes do not trigger another complete source/child observation.

This retains independent owner claims while removing the current per-owner repetition. If one owner mapping is missing or ambiguous, the full candidate bundle blocks before publication rather than partially mixing old and new evidence.

### 4. Let full-model parent composition consume the same planned observation

The model-regression operation carries its verified child decisions through to parent composition. Parent writing does not rediscover and reverify all model children. The resolver used by later independent consumers still performs its own fresh operation because cross-invocation trust is explicitly out of scope.

The final repository observation happens after all selected native model runners
have terminated and before their validation-owner receipts are published.  Its
fresh owner contexts are the publication contexts for every newly executed
leaf.  Leaf publication therefore does not rebuild an owner current from the
filesystem once per child.  After the content-addressed leaf receipts are
written, one receipt-store reconciliation verifies only the newly supplied
identities and completes the parent freshness boundary without a third
repository scan.

This ordering is preferred over publishing each leaf immediately after its
runner because immediate publication repeats scoped source discovery for every
executed model.  It is preferred over trusting the initial observation because
the final repository observation still catches peer or runner source drift.
No leaf from the bounded batch can support the parent until both the final
source comparison and the post-publication receipt reconciliation pass.

### 5. Instrument counts and phase times in canonical results

Results include observation count, verified-child count, reused-child count, executed-child count, and bounded phase durations. Tests assert the number of complete observations, not an absolute wall-clock threshold, so slow machines do not create flaky correctness failures.

## Risks / Trade-offs

- **[A caller mutates a supposedly frozen value]** → Use frozen dataclasses/tuples and canonical fingerprints; copy mutable JSON inputs into canonical immutable projections at construction.
- **[Final identity comparison misses a governed input]** → Derive the final inventory with the same canonical manifest and receipt-discovery owners as the initial observation, and add mutation-between-phases tests for source, receipt, owner, dependency, toolchain, and environment identities.
- **[Sharing a child accidentally merges owner semantics]** → Store exact child subsets per aggregate and continue native aggregate verification for subject, obligation, dependency, and owner identity.
- **[Instrumentation becomes another authority]** → Mark timing/count fields diagnostic and exclude them from pass/current decisions except for structural assertions such as a missing final phase.
- **[Refactor temporarily stales current model authority]** → Finish code and focused tests first, then create one new affected ModelRevisionSet and run one final release gate after all OpenSpec changes are archived.

## Migration Plan

1. Add the observation value and exact comparison helper behind internal call sites; keep existing public result schemas unless new optional diagnostic fields are explicitly versioned.
2. Convert model-revision evidence production and verification to the shared observation path and prove per-owner semantic separation plus drift rejection.
3. Convert full-model planning/parent composition to carry the same observation and prove one initial plus one final identity pass.
4. Publish executed leaf receipts from the one final fresh owner-context projection, then reconcile the new receipt identities once; remove per-child source-current rebuilds from the bounded batch path.
5. Update affected self-models, normative specs, and focused tests; remove any now-unused duplicate collection helpers only after reference and behavior-equivalence review.
6. Build one new observed ModelRevisionSet, complete OpenSpec verification/archive, and reserve the full release validation for the frozen integration snapshot.

Rollback is direct source rollback before activation. No compatibility path is needed because the observation is internal and non-persistent.
