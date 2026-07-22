## Context

The current portable verifier has three clear layers: one explicit finite `PortableModel`, one canonical finite checker, and a token-level `check_composition()` that verifies component-local passes, assumption providers, and declared guarantee conflicts. The Behavior Commitment Ledger assigns all of that behavior to `commitment:portable-compositional-verification`, primary owner `.flowguard/compositional_verification_kernel/model.py`, and `path:portable-compositional-verification:canonical-checker`.

That path cannot currently expose an emergent integration defect whose witness depends on event delivery order, duplicate delivery, retry identity, or shared-resource mutation. ModelMesh, topology hazard review, ContractExhaustionMesh, Model-Test Alignment, and TestMesh can discover or govern pieces of such a case, but none owns product-state execution.

The design must preserve those ownership boundaries, use immutable current component fingerprints, stay finite and inspectable, and fail closed whenever a pass would otherwise depend on an omitted dependency or an exhausted exploration bound.

## Goals / Non-Goals

**Goals:**

- Represent a bounded network of existing portable model references, typed event interfaces, shared-resource contracts, explicit atomic/interleaved step rules, and owner-bound system safety plus existing portable temporal projections.
- Derive an exact affected slice over the declared system graph from task-local changed-model roots, event relationships, resource co-use, and property dependencies.
- Explore cross-model schedules and produce the shortest available cross-model counterexample.
- Preserve one verdict engine by compiling the joint graph to a `PortableModel` and using the existing portable checker.
- Make local-model, token-composition, executable-composition, truncation, and code/test mapping evidence distinct.
- Expose a stable public API/CLI and three benchmark families with bad and repaired variants.

**Non-Goals:**

- No unbounded or probabilistic verification, wall-clock timing proof, infinite queues, arbitrary Python serialization, or production-conformance claim.
- No automatic inference that code or runtime traces are true model authority.
- No automatic permanent model mutation. AI-generated model deltas remain agent/process candidates until an owner accepts them with replacement/freshness evidence and produces a new current product artifact.
- No universal full-repository Cartesian product, no general temporal-system property language in this increment, and no claim that every integration bug is discoverable.
- No new public satellite skill, duplicate model registry, generic local-model interpreter, or second successful checker path.

## Decisions

### Extend the existing behavior commitment and canonical path

The system-composition surface is a stronger mode of the existing portable-compositional-verification intent. The ledger, primary owner model, and primary path remain singular. Public API and CLI surfaces delegate to the same implementation and cannot promote token closure to an executable pass.

Alternative considered: create a new `flowguard-system-composition` satellite and behavior commitment. Rejected because the external intent and verdict authority overlap the existing portable verifier, while discovery, case generation, evidence governance, and process sequencing already have established satellite owners.

### Compile a bounded system slice to the existing portable checker

The implementation has two product modules and three distinct public artifact identities:

- `portable_system.py` owns strict current-schema artifacts, canonical identity, validation, loading/writing, and affected-slice derivation. `PortableSystemDefinition` is stable system authority, `SystemCompositionRequest` carries task-local changed roots/property selection/bounds, and `PortableSystemSlice` is a derived closure with its own fingerprint.
- `system_composition.py` owns deterministic joint-step expansion, joint-state compilation, portable-checker delegation, and system-trace projection.

The compiler produces one explicit finite `PortableModel`. A compiled state is a stable tuple of selected component states. Queue, outbox, shared-resource, clock, fault, and retry behavior are represented by ordinary finite component models instead of a second system-state DSL. A compiled transition records one declared joint step and every exact component transition reference and event/resource relation; optional code/runtime targets remain non-semantic provenance for downstream alignment. Violating state patterns and temporal patterns are projected into ordinary `PortableInvariant` and `PortableTemporalObligation` rows. The existing `check_portable_model()` remains the sole safety, liveness, fairness, and semantic counterexample verdict engine.

The system compiler may select a candidate reachable safety witness, but only the canonical checker can confirm it. A complete compiled graph is checked once. A truncated graph with no candidate safety witness returns `blocked` before semantic checking. A truncated prefix may support `fail` only when one canonical checker invocation confirms a monotonic reachable safety-invariant witness; temporal dead ends, cycles, eventuality, bounded progress, or fairness findings require a complete graph and otherwise remain `blocked`.

Alternative considered: a native `SystemExplorer` with its own graph traversal and invariant verdict logic. Rejected for this increment because it would duplicate reachability, counterexample, status, and claim-boundary behavior before benchmark evidence proves a separate engine is necessary.

Alternative considered: generate only integration/property tests. Rejected as the primary path because it cannot provide deterministic finite-graph completeness or a canonical model-level counterexample, but generated tests remain downstream evidence through Model-Test Alignment.

### Use strict references and typed operational bindings

The stable `PortableSystemDefinition` contains:

- component refs: model id, exact portable fingerprint, and an optional `behavior`, `queue`, `resource`, `clock`, or `fault` role;
- declared/unresolved dependency ids and discovery-evidence identity, but not task-local changed roots;
- event ports: model, direction, transition ids, event/schema ids, identity/correlation fields, delivery semantics, ordering scope, and persistence boundary;
- bindings: exact producer/consumer ports, business-identity mapping, queue component plus enqueue/deliver/duplicate/drop transition refs, synchronization, delivery/ordering policy, and compatibility contract id;
- shared resources: the finite resource component, exact reader/writer transition refs, transaction domain, identity fields, and consistency/visibility declarations;
- system steps: one stable id, one or more component transition refs, event/resource relation ids, optional code/runtime targets, and an explicit atomicity label;
- named system state patterns over exact component states;
- system safety invariants and temporal obligations: one explicit owner plus forbidden, trigger, target, or fairness pattern/step ids;
- the scheduler semantics version. The task-local `SystemCompositionRequest` supplies changed-model roots, selected property ids, requested subset, and an explicit joint-state bound.

Every required semantic field must change enabled joint steps, generated state/transitions, declared-graph slice closure, or a deterministic invalid/blocked decision. Explanatory code/runtime targets and other provenance fields are optional and do not strengthen the model-level verdict.

The current schema accepts `at_most_once` and `at_least_once`; it does not treat `exactly_once` as a primitive. Exactly-once behavior must be modeled as a property of delivery, identity, deduplication, and transaction boundaries.

Unknown fields, duplicate ids, unsupported primitives, missing semantic identities, unowned properties, or unknown transition/resource references are `invalid`. Stale component fingerprints, uncovered reachable component transitions, ambiguous or unresolved dependencies, omitted closure members, and clean truncation are `blocked`. Declared semantic violations on otherwise valid/current evidence are `fail`. A later stage that did not execute is `not_run` and can never be projected as pass. There is no compatibility reader or alias schema.

### Define one finite and explicit joint-step scheduler

For one compiled state, every enabled declared system step is a successor:

1. a one-reference step executes one component transition and interleaves normally with other enabled steps;
2. a multi-reference step executes transitions from distinct components atomically;
3. producer plus queue-enqueue, queue-deliver plus consumer, business plus resource read/write, or commit plus outbox transitions are expressed as explicit multi-reference steps;
4. queue redelivery, drop, delay, retry, late acknowledgement, clock advance, fault, and compensation are ordinary transitions of their finite owner components and receive their own step rules.

Delay is represented by choosing another enabled system step while the queue component remains pending. Delivery and business-identity semantics are constrained by the queue model plus the typed binding. Commit/emit separation, crash cuts, late acknowledgement, retry, or compensation must appear as explicit component transitions and step rules; the compiler never invents an atomicity boundary.

Every included component transition must appear in at least one system step, so an omitted interaction cannot silently disappear from the graph. Reaching the joint-state bound with an unexplored frontier marks the compilation truncated. A canonical-checker-confirmed reachable safety witness remains a valid failure with truncation residual risk; a temporal candidate or otherwise clean truncated search returns `blocked`, never `pass`.

### Derive a change-scoped closure, not a whole-network product

Starting from `SystemCompositionRequest.changed_model_ids`, affected-slice derivation reaches a fixed point over the current declared system graph:

- producer/consumer event bindings in both directions;
- all queue/resource/clock/fault components and peer models referenced by a binding or resource contract touched by an included model;
- all models referenced by a state pattern or property that intersects the slice;
- declared dependency ids.

The definition, request, and slice each have independent fingerprints. The slice records included/excluded model, binding, resource, property, and unresolved dependency ids. A requested subset that omits a required closure member is blocked. The compiler never treats an unknown declared edge as evidence of no impact and never claims discovery of undeclared code/runtime dependencies.

### Keep handoffs typed and non-owning

- Existing Model Preflight discovers current models/owners, existing system-definition references, proposed relation candidates, freshness facts, and selects `compose_existing_models` when warranted. It does not create current bindings.
- ModelMesh emits or consumes a composite reference only when a real parent/child or sibling reattachment is in scope; it does not become the entrypoint for ordinary peer composition or execute child graphs.
- Topology Hazard emits anchored interaction candidates only, reuses an already resolved owner, and returns `owner_missing` when no owner exists.
- ContractExhaustionMesh varies owner-declared policies, initial environments, fault profiles, malformed boundaries, and shards; it does not re-enumerate the fixed scheduler graph or execute cases.
- Model-Test Alignment binds invariant → scenario → minimal trace step → code/runtime target → current regression.
- TestMesh consumes the canonical report through `ProofArtifactRef.artifact_fingerprints` and stores terminal evidence without running or interpreting the checker.
- DevelopmentProcessFlow applies its current lifecycle order, peer-write handling, background-liveness, installation-domain, and evidence-freshness rules without owning system semantics.

### Benchmark the product claim, not merely API availability

Each benchmark family contains local component artifacts, one token-closed bad system, one repaired system, malformed boundary cases, and one deliberately truncated profile. The required chain is:

`all local models pass → token composition passes → bad executable composition fails with a cross-model trace → repaired composition passes → malformed/truncated variants block`.

The initial families are payment/order retry identity, authorization revocation/cache invalidation, and deletion/index/export propagation. Metrics include local-green count, system failures found, false findings, trace length, affected/full model counts, and explored-state reduction.

### Activate through one public cohort and clean skill projection

The public cohort exposes the schema constant, artifact/report types, load/write/validate/slice helpers, and `check_system_composition`. Internal compiler helpers remain private. `portable-system-check` accepts one system artifact plus exact component model files and emits canonical JSON or a concise human projection.

Author-skill updates occur only after the executable capability and benchmark evidence exist. SkillGuard compiles affected author contracts, runs target-owned native checks under one frozen unit plan, and builds the clean `$CODEX_HOME/skills` projection without `.skillguard`, OpenSpec, evidence, or repository-only state.

## Risks / Trade-offs

- [State growth remains exponential] → Exact impact slicing, finite domains, deterministic deduplication, queue/state limits, and fail-closed truncation bound the claim. Partial-order reduction is deferred until benchmark evidence shows where it is safe.
- [A wrong system model can be internally consistent] → Reports retain domain-truth and production-conformance residual risk; current fingerprints, code/runtime target ids, Model-Test Alignment, and runtime evidence remain separate gates.
- [Unbound local transitions may over-approximate the environment] → Every trace labels unbound actions, and benchmark/system authors can narrow them with input ports and initial-event declarations. Over-approximation can find a candidate, not prove production reachability.
- [Authors could declare an over-wide atomic joint step] → Every step exposes its exact transition refs and atomicity rationale; non-atomic/atomic known-bad pairs are required in tests and topology/alignment review.
- [Queue/resource components add modeling work] → Reusing ordinary PortableModel semantics avoids an unproved second DSL and makes every delivery, retry, resource version, and fault transition directly checkable by the existing engine.
- [Prompt activation could outpace executable support] → Prompt/skill changes occur after focused product checks and benchmark acceptance, then undergo SkillGuard and installed-projection validation.
- [The 0.59.0 base branch already has deferred release work] → This change keeps its own OpenSpec identity and evidence, advances directly to the new `0.60.0` capability release, and does not check off or reuse the earlier change's deferred task receipts.
- [Parallel agents may change the shared checkout] → Re-read and preserve peer writes, freeze branch/HEAD/path fingerprints and one owner before each write or heavy check, and stale only affected evidence; never roll back peers to recover an older green state.

## Migration Plan

1. Add the new model/spec/test obligations and update the existing behavior commitment in change mode.
2. Implement strict system artifacts, slice derivation, compiler/checker delegation, report projection, and public API/CLI.
3. Add benchmark families, known-bad proofs, repaired variants, malformed cases, and focused tests.
4. Update documentation, the default kernel and Existing Model Preflight, and only evidence-proven additional skill handoffs; compile and validate affected author contracts with the latest stable SkillGuard available after source freeze.
5. Run focused checks, then controlled background model regressions with durable terminal evidence.
6. Freeze source/toolchain/owner plan and run exactly one final full validation.
7. Advance package/project/installed projections to `0.60.0`, create one scoped local commit, install the exact source and clean 15-skill projection, run the final frozen-snapshot gate, then push the branch and immutable tag and publish one source-only GitHub Release.

Before publication, rollback is one local source commit reversal plus restoration of package and skill projections from the same authoritative revision. After an immutable tag/Release is published, correction requires a new version; no tag movement, dual current schema, or fallback command is allowed.
