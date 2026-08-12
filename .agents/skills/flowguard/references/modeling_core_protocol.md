# Core Modeling Protocol

Use this protocol before non-trivial behavior changes involving workflow order, state, retries, deduplication, idempotency, caching, side effects, or ordinary module boundaries.

## Preflight and Risk Intent

Verify `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"` and the target project's AGENTS.md managed adoption record. If the real package is unavailable, connect it or report blocked/partial; never create a replacement mini-framework.

Before constructing or materially changing a concrete model candidate, freeze a current model-instance purpose declaration: stable task and instance ids, a reviewable guarded purpose, one-or-many finite protected failure ids, and the claim boundary. The declaration belongs to this task-specific instance; a reusable model type, template, or skill is never permanently assigned one failure class.

Write a minimum valuable Risk Intent that names those protected error classes/harms, model-critical state and side effects, completion evidence, business path identity, adversarial/repeated inputs, hard invariants, representative known-bad paths, and residual blindspots. After candidate construction, bind the exact candidate fingerprint, one native known-good case, exactly one native known-bad case per declared failure, native oracle ids, and current evidence checks into the instance closure. Missing, duplicate, disconnected, post-hoc, or stale closure blocks the protection claim; there is one fixed workflow and no weaker mode or fallback.

## Finite model

1. List finite abstract input classes, including repeat/retry/partial-failure/order variants.
2. Use immutable, hashable abstract state only for facts that affect future behavior or invariants; never call live network, database, clock, random, LLM, or external services from the model.
3. Split named FunctionBlocks at behavioral boundaries. Every block implements `Input x State -> Set(Output x State)` and declares reads/writes.
4. Enumerate every possible abstract output and explicit terminal/error/no-result branch; do not hide outcomes in prose.
5. Inventory every production writer for invariant-critical state and classify modeled, scoped, or missing writers.
6. Define idempotency, deduplication, retry, cache/source-of-truth, side-effect, and ordering behavior where relevant.
7. Write hard invariants over all reachable state/trace paths; never weaken them merely to pass.
8. Use standard property factories or packs only when their declared selectors match the risk; helpers do not infer the model.

## Formal check plan

Bind `RiskIntent`, `MinimumModelContract`, and current `KnownBadProof` into
`FlowGuardCheckPlan`; call `run_model_first_checks(plan)` with finite
inputs/states and repeated-input sequences.

Template operations are a separate conditional route, not part of this formal
entry. Enter the single strict `risk_template_library` route only when the
user explicitly requests template reuse/publication or current executable
model evidence identifies a bounded stable pattern intended for use outside
the target project. Once triggered, search the public and per-machine local
libraries, record exact used ids or a reviewed no-match, and close harvest as
written, merged, duplicate-linked, or accepted not-harvestable. Ordinary
modeling, repair, maintenance, cleanup, and release do not run this route and
are not blocked by missing template evidence.

The formal runner may emit progress on stderr. Progress is liveness only. Inspect the final summary, finding ledger, counterexamples, skipped/not-run sections, and exit/result evidence.

Make one representative broken implementation/trace fail for every protected failure id, and make the declared native known-good case pass. Give counterexamples and known-bad proofs stable target ids and keep them bound to the current model-instance closure when they drive owner-code regression evidence.

Minimize failing sequences only to aid review; preserve the original trace. When a counterexample exposes a design bug, revise model and intended architecture. When it exposes model infidelity, revise the model/oracle/replay adapter. Rerun after any relevant input changes.

## Scenario and liveness review

Use scenario review for repeats, retries, refresh, queues, reprocessing, uncertain decisions, cache/deduplication, human loops, side effects, and rejected/missing-field/no-body repair packets. Broken-model expected violations are successful observations; policy uncertainty remains `needs_human_review`.

For retry/wait/refresh/queue/human-review cycles, review reachable-state SCCs, stuck non-terminals, required success reachability, terminal outgoing edges, and fairness/progress. An escape edge does not prove termination. Repeated rejected input requires repair feedback, a blocker, or a finite/progress rule.

## Per-Model Path Quality

ModelMaturation owns one provider-neutral path-quality decision for every new
or materially changed model. Build a `PathQualitySubject` from the exact model,
purpose, complete effective intent, obligations, provider, dependencies, code,
tests, oracles, evidence, retained-element inventory, and currentness identity.
For non-code targets, bind the real workflow actors, inputs, states,
transitions, outputs, resources, verification, and provider evidence; do not
invent Python code or software test layers.

Run `lightweight_path_review(...)` over normalized facts first. It checks
unreachable states/transitions, duplicate transitions, behavior-irrelevant
state/fields, pass-through FunctionBlocks, unconsumed outputs, repeated
validation, duplicate current owners, and no-progress loops. Every retained
state, transition, branch, FunctionBlock, field, effect, and validation also
needs one current non-circular `NecessityWitness` naming the obligation,
counterexample, oracle, and evidence that removal would break. Mere existence,
self-description, or the path-quality result cannot license a witness.

With one clear path and no trigger, return `single_clear_path` as one compact
`PathQualityResult`; do not enumerate candidates or build a deep payload. A
deep review is admitted only for exact current evidence of `explicit_request`,
multiple hard-equivalent candidates, material state/transition/branch growth,
a recognized structural finding, a path-design model miss, a missing necessity
witness, or a declared high-cost/release-critical boundary. The trigger applies
only to the affected model and topology-required neighbors.

Deep review compares one named finite candidate/rewrite boundary. Reject a
candidate before cost comparison if any hard semantic dimension differs:
accepted/rejected inputs, outputs/terminals, state/field transitions,
protected errors/recovery, effects, order/retry/timeout/cancellation,
progress/fairness, permissions/authority, parent/child interfaces, intent,
commitments, oracles, or evidence obligations. A desired behavior change stays
`normative_target`; it cannot replace the faithful `observed` baseline until
implementation, bindings, topology, and current evidence match.

Only hard-equivalent candidates compare current named `PathCostVector`
dimensions. Missing or differently measured dimensions remain incomparable,
never implicit zero. Use Pareto dominance without a default scalar sum and
license only `preferred_within_candidates`,
`non_dominated_within_boundary`, `minimum_within_exhausted_finite_set`,
`locally_irreducible_under_declared_rewrites`, or `unresolved` under their exact
finite evidence boundary; never claim an unrestricted optimum. Store detailed
candidates, rewrites, costs, and witnesses behind one detail fingerprint so
ordinary parents consume only the compact result.

This review evaluates the declared model path itself. The route ends in model
completeness, binding coverage, impact closure, and current evidence for the
declared boundary; it does not add a target-generation step.

## Implementation and replay

Implement production code only after the relevant model shape passes. Preserve state/side-effect ownership, idempotency, deduplication, contracts, and invariants.

Use conformance replay by default when multiple real writers, durable side effects, cleanup/finalizer paths, production-behavior claims, or projection adapters are involved. Compare projected real outputs/state/labels to representative model traces; do not demand internal state identity and do not silently diverge.

Reuse an old abstract result only when model, scenarios, oracle, invariants, risk boundary, task revision, and proof artifacts remain identical/current. Spend post-edit validation on focused tests or conformance when that is stronger; otherwise rerun.

## Core completion

Core modeling is complete only when the real engine ran, the model is faithful enough for the declared risk, the known-bad path fails, correct paths pass, counterexamples were resolved/scoped, required scenarios/liveness checks ran, and missing production/conformance evidence remains visible in the claim boundary. If the separate template route was triggered, its strict search/review/harvest closure must also be current; an untriggered route contributes no gap.

## Portable finite model boundary

Use the portable boundary only when a finite model must cross a Python process,
tool, repository, or evidence-consumer boundary. Keep Python `FunctionBlock`
models as the ordinary authoring surface and explicitly project the finite
relation into `flowguard.portable_model.v1`; never attempt to serialize an
arbitrary callable, side effect, or domain predicate.

The portable artifact must name states, inputs, outputs, transitions, initial
and terminal states, invariants, temporal obligations, assumptions,
guarantees, and conflicts. Its canonical UTF-8 JSON identity and the reference
checker report travel together. Unknown schemas, unknown fields, dangling
references, truncated exploration, or a stale identity are visible non-pass
states. There is no alternate reader or prose fallback.

Route explicit parent/child mappings to ModelMesh and topology-anchored
liveness/fairness interpretation to Model Topology Hazard Review. Both consume
the same portable checker receipts; neither reimplements the interpreter.

## Bounded declared-system composition

Use `flowguard.portable_system.v1` only when current portable component models
have a declared cross-model relation or owner-bound property that local and
token checks cannot decide. Keep three immutable identities separate:
`PortableSystemDefinition` for stable declared semantics,
`SystemCompositionRequest` for changed roots/property selection/subset,
environment guarantees and finite bound, and the derived
`PortableSystemSlice` for the exact closure inside that declared graph.

One-reference system steps are the v1 interleaving authority; multi-reference
steps are explicit atomic transitions. Queue, resource, clock, fault, retry,
cache, and external-confirmation behavior remain ordinary finite components.
The compiler may assemble and map a joint graph but cannot decide safety or
temporal truth. A complete graph is checked once by the canonical portable
checker. A truncated graph is blocked without a checker verdict unless it
contains a reachable forbidden-state safety witness, in which case a
safety-only witness graph is checked once; temporal/fairness observations from
an incomplete graph never become failures. Exact declared-graph closure does
not prove that production code has no undeclared dependencies.

## Whole-target blueprint boundary

Use the target-system blueprint API cohort only when task facts explicitly
request a complete target blueprint, deterministic export, or an
owner-declared qualification obligation. Select one frozen profile-matching
layer plan. For software, first derive the exact
tracked plus admitted non-ignored file boundary independently of declared
models and contracts. Discover language surfaces with the registered adapter,
give every file and symbol one terminal disposition, and preserve parse,
dynamic-call, hidden-writer, missing-adapter, path, and freshness uncertainty as
blockers.

Bind required model obligations to implementation surfaces in both directions.
A path and symbol prove traceability only; blueprint closure additionally needs
source-independent input/output, state/effect, error, order/retry/timeout or
decision semantics plus applicable oracles. Join build, runtime, dependency,
configuration, schema, data, asset, migration, external-service, and test-oracle
references by current fingerprint. Export canonical content-addressed shards
only on explicit request and exclude production source text by default.

The blueprint is a derived view of the target's sole observed authority, not
another head. Ordinary work reads exact affected ids, referenced objects, and
required ancestors from the normalized content-addressed index; it never first
constructs, scans, serializes, or exports the whole target.

## Blueprint Modeling Responsibilities

For explicit whole-target scope, consume the exact ordered layers from the
frozen target-profile plan without collapsing them into one completeness flag.
The canonical software plan's inventory and traceability layers
identify what exists and where it is owned. They cannot supply behavior that
was merely inferred from source. The project blueprint embeds the complete
`ProjectTestInventory`, and every read independently audits its manifest,
nodes, cases, and fingerprints against current test source. `independent_semantics` must stand alone as a
  implementation-complete contract. `model_code_test` must bind every in-scope
obligation through one owner code contract to exact test assertions and
current evidence. `resource_oracle` captures everything required to build,
start, configure, migrate, integrate, and judge the behavior.

The canonical non-code-workflow plan instead uses real workflow boundary,
target-owned actors, inputs, states, transitions, outputs, resources, intent,
and verification; it never fabricates software implementation or Python test
layers. Use only explicit target-owned identities. Unknown or conflicting ownership
is a blocker, not permission to assign a FlowGuard self-owner or generic
fallback. Ordinary modeling builds the smallest affected model and reports
which blueprint layers were consumed; it does not materialize the whole
software.

Use the sole canonical blueprint objects. Each behavior-bearing surface has one
`BehaviorBlockContract`, one
primary owner, one exact block-local portable field binding, its own concrete
good/boundary/protected-failure cases, and explicit input, state, output, effect, error, decision,
order, retry, timeout, and completion dimensions. Helper, adapter, serializer,
and storage surfaces attach through `SupportingSurfaceRelation`; they do not
become duplicate product behaviors merely because they contain code. The
direct implementation binding owns the exact behavior-block obligation. Every
supporting binding references that same obligation and the direct owner's
required dimensions without entering the primary-obligation denominator;
missing, ambiguous, or mismatched direct ownership blocks instead of creating
a helper-local fallback obligation.

Each `BehaviorCoverageEdge` binds that block to exact implementation surfaces,
source-independent semantic rules, portable binding, concrete case, oracle,
and a current real assertion or native-check member. Keep
`CoverageExecutionEvidence` separate; a static checker design may be complete
while execution remains `not_run`. Compact qualification keeps such planned
`not_run` leaves in a bounded execution-gap projection rather than a
static-blocker projection, without claiming that they passed. Static owner,
obligation, dimension, oracle, and checker-design gaps remain blockers.
Do not fan an owner-wide receipt out across all of its blocks. Every discovered
test node receives a terminal `required`, `supporting`, `scoped_out`,
`generated`, `external`, or `unresolved` disposition.

Join one exact `ProjectResourceInventory` covering build, runtime, dependency,
configuration, schema, data, asset, migration, external service, and test
oracle resources. Each non-blocked category row embeds the canonical
`BlueprintResourceReference` and therefore retains its exact owner, artifact,
content fingerprint, source-independent semantics, purpose, and lifecycle
role; the row adds only independently fingerprinted category disposition
evidence. A blocked row has no resource reference and cannot manufacture a
missing blueprint input. Join one exact `ProjectIntentInventory` from the
accepted revision's complete `CurrentEffectiveIntentView`. Keep the
revision-local delta as history, and carry the independently observed complete
model-owner denominator plus exact owner bindings into the inventory. Every
current behavior consumes non-empty effective intent through its own exact
model owner. The latest delta, a root intent, historical concatenation,
matching words, or implementation inference cannot fill a missing binding. An
empty intent set is valid only when there are no required model owners and an
evidence-bound `NoDeclaredIntentRationale`; absence or discovery failure is not
no-intent.

Normalize shared owners, contracts, semantics, oracles, tests, resources, and
intent once. A native typed behavior report may retain its review rows, but each
complete normalized coverage payload has exactly one physical owner at its
content-addressed object id. Normalized behavior views and strict current-schema
shards carry only fingerprints and ordered references; a legacy full-payload
shard is rejected without fallback. The logical projection fingerprint is
independent of shard layout. Ordinary work uses `AffectedBlueprintReader` to
load only exact shards, referenced shared objects, and ancestors and verifies
every fingerprint before use; a whole bundle followed by a small projection is
not affected-only. Full projection/export is explicit-only.
