## Context

See `proposal.md` for motivation. FlowGuard already owns model coverage through ModelMaturation, hierarchy through ModelMesh, implementation contraction through Architecture Reduction, process order through DevelopmentProcessFlow, and current observed publication through ModelRevisionSet. The missing part is a reusable decision about the quality of each model's own path shape.

The repository is concurrently modified and is also migrating cumulative current intent and observed authority to a stricter v5 shape. Path-quality authority therefore must join that same revision and cannot create another current pointer. The feature must work for code in any language and for non-code workflows, so the core accepts provider-neutral model facts rather than parsing Python as its semantic authority.

## Goals / Non-Goals

**Goals:**

- Add one general, provider-neutral path-quality contract for every new or materially changed model.
- Keep ordinary work cheap and deep work explicitly triggered and finite.
- Prove hard semantic equivalence before comparing costs.
- Preserve multi-dimensional trade-offs and narrowly licensed conclusions.
- Attach compact current results to existing maturation, blueprint, mesh, revision, readiness, and evidence owners.
- Use the same capability to improve FlowGuard's own models and release path.

**Non-Goals:**

- Reconstructing target software as a routine proof exercise.
- Searching every possible model or implementation path.
- Claiming global optimality.
- Adding a public optimizer skill, route, command, model owner, or current pointer.
- Letting a cleaner normative model replace faithful observed behavior before implementation.
- Letting model-only contraction authorize code deletion.

## Decisions

### Keep one internal ModelMaturation owner

The new behavior is an internal ModelMaturation subdecision. The implementation uses one canonical module and one result schema, while the public route remains the existing FlowGuard kernel/ModelMaturation path. Other owners consume the typed result without recomputing it.

Alternative rejected: add a public ModelOptimizer skill or route. That would make users choose between overlapping model-completion paths and would create the same duplication this change is meant to prevent.

Alternative rejected: put the feature under Architecture Reduction. Architecture Reduction owns model-to-code contraction and public/consumer safety; a model may need representation cleanup without any code change, so it cannot be the single-model semantic owner.

### Use five cohesive internal records

The canonical representation uses five cohesive immutable records:

1. `PathQualitySubject` binds model, purpose, intent, obligation, provider, dependency, code, test, oracle, and evidence identities.
2. `PathCostVector` holds named comparable dimensions without a default scalar total.
3. `NecessityWitness` binds one retained model element to an active obligation, executable counterexample/oracle, and evidence identity.
4. `PathCandidate` describes one finite hard-semantic candidate, rewrite provenance, cost vector, and witness set.
5. `PathQualityResult` carries mode, triggers, findings, candidate ids, conclusion, unresolved ids, compact identity, and detail fingerprint.

The ordinary result may omit candidate bodies and keep only fingerprints. Deep evidence stores canonical detail outside the compact parent/revision projection.

Alternative rejected: put every optional field on the existing maturation request. That would make ordinary AI prompts and every parent model carry a deep optimizer payload even when no trigger exists.

Alternative rejected: create separate light and deep result schemas. That would create two success authorities and complicate freshness, revision, and consumer logic.

### Separate provider-neutral facts from provider extraction

The kernel consumes normalized states, transitions, FunctionBlocks, reads, writes, effects, interfaces, obligations, and evidence identities. Existing and future providers may compile those facts from Python, another language, a service definition, UI flow, workflow document, or user-authored model. Provider qualification remains responsible for faithful extraction.

The initial native adapter reads FlowGuard's portable workflow/model structures. Python source inspection may contribute code/helper bindings through the existing implementation inventory, but it does not define model semantics for all targets.

Alternative rejected: make Python AST analysis the core. That would contradict target neutrality and repeat provider ownership.

### Make the lightweight review deterministic and near-linear

For a normalized model with V elements and E relations, the ordinary review builds indexed adjacency, ownership, read/write, guard/effect, output-consumer, and validation-obligation maps once. It identifies:

- unreachable states and transitions;
- duplicate transitions with the same source, trigger, guard, output, state update, and effect;
- state or fields with no behaviorally observable use;
- FunctionBlocks that only forward an unchanged input/state pair;
- intermediate outputs with no consumer or terminal role;
- repeated validation of the same obligation, oracle, subject, and evidence boundary;
- duplicate exact-current owners for the same stable intent and boundary;
- strongly connected components with no terminal, progress measure, bounded retry, or explicit external-wait boundary.

The review emits deterministic findings and either `single_clear_path`, a deep trigger, or `unresolved`. It does not synthesize candidate programs.

### Trigger deep review from evidence, not ceremony

Accepted triggers are:

- explicit user or task request;
- more than one declared hard-equivalent candidate;
- material state, transition, or branch growth beyond the task's declared threshold;
- lightweight duplicate, unreachable, pass-through, repeated-work, or no-progress findings;
- a model miss whose root cause is path design;
- a retained element without a current necessity witness;
- a high-cost or release-critical model boundary declared by the affected owner.

No trigger means no deep payload. A trigger applies only to the affected model and topology-required neighbors.

Alternative rejected: run deep comparison on every routine use. This would spend time and tokens proving a negative for models that have one clear path.

### Require a hard-semantics matrix before cost

Each finite candidate must bind the same semantic subject and produce an explicit comparison row for:

- accepted and rejected inputs;
- outputs and terminal states;
- state and field transitions;
- protected errors and recovery;
- externally visible and protected internal side effects;
- order, retry, timeout, cancellation, progress, and fairness;
- permissions and authority;
- parent input and child output interfaces;
- intent and behavior commitments;
- executable oracles and evidence obligations.

Any mismatch removes the candidate from equivalent-path ranking. If the mismatch is desired, the candidate becomes normative-target evidence and follows ordinary implementation/adoption lifecycle.

Alternative rejected: compare source size or transition count first and validate behavior afterward. That can optimize away the very obligation the model exists to protect.

### Keep cost as a dominance-aware vector

`PathCostVector` has explicit optional dimensions for steps; states; transitions; branches; repeated reads; repeated writes; repeated validations; invalidated outputs; rework; coordination; side-effect exposure; latency; token/payload size; runtime resources; and maintenance complexity. Missing or differently measured dimensions remain incomparable; they are never silently zero.

Selection rules are:

- one current no-trigger model: `single_clear_path`;
- one candidate dominates within complete comparable dimensions: `preferred_within_candidates`;
- no candidate dominates: `non_dominated_within_boundary` or `unresolved` if a choice is required;
- complete named finite set plus current comparable measurements and one unique minimum: `minimum_within_exhausted_finite_set`;
- all declared rewrite rules rejected or exhausted with current evidence: `locally_irreducible_under_declared_rewrites`;
- missing semantics, evidence, witness, boundary, comparability, or tie-break: `unresolved`.

No default weighted sum exists. A route-specific caller may supply an explicit current preference order for incomparable dimensions, but the result must report it as bounded preference evidence rather than measured global optimality.

### Treat rewrite rules as finite proof obligations

The first current rewrite set covers removal of unreachable elements, merge of observationally equivalent states, collapse of pass-through blocks, common prefix/suffix factoring, deduplication of identical read/write/serialization/fingerprint/validation work, reordering of independent steps, and safe parallelism with exact dependency and execution-owner isolation evidence.

Each accepted rewrite must produce before/after model identities, affected elements, hard-semantic proof, new necessity witnesses, cost-vector delta, and required affected validation. The review recommends a model change; it does not mutate current observed authority directly.

### Make necessity evidence element-local

Each retained element has one witness with the exact obligation, counterexample, oracle, and evidence identity that would fail if the element were removed or merged. A witness cannot cite the element's mere existence, its own self-description, or the path-quality conclusion as proof.

Witnesses make “why is this still here?” answerable and provide the direct input for later Architecture Reduction when a model element maps to implementation structure.

### Publish compact summaries through the v5 revision

The compact summary contains:

- subject fingerprint;
- mode and trigger ids;
- bounded conclusion;
- finding and unresolved ids;
- candidate-set and rewrite-set fingerprints when applicable;
- necessity-witness-set fingerprint;
- detail evidence fingerprint;
- producer and currentness identity.

ModelRevisionSet includes this summary in the same candidate identity and compare-and-swap activation as the affected model, cumulative current intent, topology, blueprint bindings, and native-owner evidence. There is no `current_path_quality.json` pointer beside the model head.

The independently derived add-or-replace model set is the minimum required path-quality denominator, not an exact ceiling on the candidate payload. A small incremental revision may also carry current rows for unchanged members, including FlowGuard's complete current self-model denominator when publishing its own DNA. Every added or replaced model must still be present. Every extra row must name a model in that same candidate's current model set, share the candidate snapshot, and be exact-current, validated, and resolved. A foreign, retired, stale, cross-snapshot, unvalidated, or unresolved extra row blocks acceptance; exact equality between the changed-model set and the supplied path-quality set is therefore neither required nor sufficient.

Parents and affected projections consume compact summaries. Deep detail is dereferenced only when a triggered claim needs it. Any consumed identity change stales the result and propagates through ModelMesh.

### Integrate validation without duplicating ownership

Model-Test Alignment binds changed semantic obligations and necessity witnesses to owner code contracts and current tests/oracles. TestMesh owns test hierarchy and receipt currentness. Neither recomputes path dominance or local irreducibility.

Architecture Reduction receives a path-quality result only when blueprint bindings map model elements to concrete code/helper/module/facade/validation candidates. It then applies its independent observable-contract, consumer, side-effect, facade, retirement, and affected-validation proof.

DevelopmentProcessFlow orders requirement/intent closure, lightweight review, conditional deep review, implementation, affected tests, candidate revision, and current activation. After model-owner retirement stabilizes the denominator, one unified candidate authority and final self-audit close all coordinated changes.

### Migrate all current models directly

There is no compatibility reader or optional legacy success path. During this release, every continuing current model receives a current lightweight result. Models with triggers receive a deep or explicit unresolved disposition. Models scheduled for proven retirement are removed from the current denominator before final activation and do not receive artificial new authority merely to be deleted.

Whole-system DNA and release claims require zero unresolved required rows after the final current owner set is frozen. Smaller unrelated claims may remain affected-only and do not imply whole-system completion.

## Risks / Trade-offs

- **Provider facts omit a semantic dimension** → Treat the provider result as incomplete and keep the path decision unresolved; do not guess from source shape.
- **Lightweight heuristics report a false duplicate** → Findings trigger review but never authorize a rewrite without hard-semantic proof.
- **Deep candidate count expands** → Require a named finite set and rewrite boundary; preserve unreviewed possibilities outside the claim.
- **Cost dimensions are incomparable** → Keep a Pareto/non-dominated result or require explicit preference evidence; never invent a scalar.
- **Every-model migration becomes expensive** → Run deterministic lightweight review for all continuing models, deep review only for triggered affected neighborhoods, and store compact summaries.
- **A current observed model is cleaned ahead of code** → Keep the cleaner form normative until implementation and evidence match.
- **Path evidence duplicates model/test evidence** → Store identity references and witnesses; native owners keep their original semantics and receipts.
- **Concurrent edits stale results** → Freeze exact inputs before final candidate activation and rerun only affected owners until the unique final full gate.
- **Historical models inflate migration** → Finish responsibility transfer and remove proven historical owners before final all-current path closure.

## Migration Plan

1. Land the new specification and executable self-model obligation before production implementation.
2. Add the provider-neutral records, canonical fingerprints, lightweight reviewer, finite deep comparator, and focused unit tests.
3. Integrate the compact result with ModelMaturation and its native receipt/check path.
4. Integrate affected subject/freshness propagation with target blueprints, readiness, ModelMesh, Model-Test Alignment, DevelopmentProcessFlow, and the kernel.
5. Complete the v5 cumulative-intent/current-authority work and publish path-quality summaries through the same ModelRevisionSet candidate, treating add-or-replace members as the minimum required denominator while permitting a strictly validated complete current-DNA denominator.
6. Use the new capability to review continuing FlowGuard models; retire already-proven historical owners before the final denominator is frozen.
7. Apply evidence-ready model contractions, then route mapped implementation candidates through Architecture Reduction and affected validation.
8. Update prompts, documentation, source/install projections, and SkillGuard contracts without adding a public route.
9. Freeze all source and owner identities, create one pre-archive integrated candidate, run the supervised compact self-audit, and close all coordinated OpenSpec changes.
10. Archive the changes, refresh archive-invalidated intent/authority, run one final foreground full validation, then synchronize installation, Git, tag, and GitHub Release.

Rollback before publication is commit-level and restores the prior current model authority atomically. After publication, any behavior restoration is a new explicit requirement and release, not a compatibility fallback.
