# Architecture Reduction Protocol

Use Architecture Reduction when an existing implementation has grown through
repeated branches, handlers, adapters, modules, state phases, UI surfaces, or
validation paths and the current software DNA must decide what is still
necessary. The route can keep a needed surface, contract structure while
preserving behavior, intentionally retire behavior through complete current
proof, or leave the decision unresolved.

Architecture Reduction is a model-to-code bridge. It does not refactor code,
parse the whole program, or replace StructureMesh. Agents collect existing
model ownership, code-boundary mapping, observable behavior, candidate
reductions, and proof evidence, then pass that evidence into
`review_architecture_reduction(...)`.

When Existing Model Preflight or a current canonical-relation handoff supplies
a same-intent or duplicate-boundary relation, derive one required-surface universe independently
from the separately materialized candidate inventory and keep distinct
fingerprints for both. Every alias, adapter, wrapper, helper, fallback, facade,
public entry, provider, test responsibility, resource, and duplicate handler
needs exactly one necessity decision: `retain`, `contract-equivalent`,
`retire-behavior-with-complete-current-proof`, or `unresolved`. The stored
universe row remains direct-current: an ordinary action-bearing candidate uses
`contract`, and a behavior-retirement candidate additionally carries
`target_action=retire_behavior`, `proof_status=authorized_retirement`, and the
typed current retirement proof. This is one current decision path, not a
compatibility alias or second reader. Missing proof does not authorize
`retain`, and candidate absence cannot produce a retain or retirement record.
Materialize each in-scope canonical relation and code-obligation id on
concrete candidates, target nodes, and target actions; plan-level opaque ids
are not contraction proof. Parse, dynamic, adapter, owner, caller, or test gaps
remain unresolved. Inventory/source revision changes stale the review.

## Trigger

Create or update an Architecture Reduction review when any of these are true:

- a staged development task has accumulated multiple adapters, phases, or
  fallback branches around the same behavior;
- an existing-model preflight finds overlapping model or implementation
  ownership and the user wants a simpler architecture;
- a refactor is shrink-oriented, not just a parent/child split;
- ModelMesh finds sibling boundaries that express the same code
  responsibility;
- Model-Test Alignment finds duplicate test evidence caused by duplicate
  implementation paths;
- UI Flow Structure finds repeated UI states, controls, displays, or journeys
  and the implementation should become smaller.

Skip the route for greenfield module planning, model-only cleanup, trivial
edits, and formatting-only work.

## Necessity-First Decision

Judge each surface against the exact-current product/DNA goal from the accepted
revision's complete `CurrentEffectiveIntentView`, its exact model-owner binding,
observed model authority, Behavior Commitment Ledger, and
model-code-test-interface bindings. The revision-local delta remains change
history; historical concatenation, matching words, a root intent, or the latest
delta cannot authorize retain, contraction, or retirement.
Historical existence, former importance, old route membership, implementation
size, or the mere presence of tests is context only; none is a retain reason.

- `retain`: one exact-current needed commitment and one current owner still
  require the behavior or responsibility. Cite its model, code, tests/oracles,
  public/consumer boundary, and current-goal rationale. For implementation
  members, record one candidate-independent current necessity witness whose
  semantic fingerprint contains only normalized source-independent semantic
  content. Paths, symbols, model/owner/spec/oracle/test/receipt ids, candidate
  ids, and raw structure-derived semantics are evidence, not semantic
  differences. Consumer evidence is member-local: use the exact current
  implementation binding or an active reviewed external commitment. A
  candidate-level aggregate caller set is discovery context and must never be
  copied onto every member as retain authority.
- `contract-equivalent`: the behavior remains necessary, but duplicate or
  over-complex structure can shrink. Use an ordinary `contract` action and
  prove the complete `ObservableArchitectureContract` through current
  equivalence or facade delegation.
- `retire-behavior-with-complete-current-proof`: the current goal no longer
  needs the behavior. Use `retire_behavior` plus `authorized_retirement` and
  one `ArchitectureRetirementProof` that dispositions every current
  responsibility and proves all required owner transfers or migrations.
- `unresolved`: current necessity, ownership, consumers, equivalence, or
  retirement responsibility is absent, stale, ambiguous, or incomplete. Keep
  the gap visible; never turn uncertainty into retain or deletion.

These are decision classes, not four alternate execution routes. Ordinary
contraction and intentional retirement remain two explicitly typed actions
inside the one Architecture Reduction owner.

## Retained-Route Internal Steps

Keeping a route does not automatically keep every step inside it. Reuse the
same current implementation, reverse-caller, model, test/oracle, state, effect,
error, and responsibility inventories to review internal scans, builders,
normalizers, reflections, projections, fingerprints, evidence joins, and other
workflow steps. Do not perform another whole-target scan merely to classify
those steps.

Every in-scope internal step receives exactly one action:

- `retain`: the step still has one current purpose and owner, with current
  necessity evidence;
- `merge`: equivalent work moves into named replacement step(s), with complete
  caller coverage and observable-equivalence evidence;
- `delegate`: the step stops owning the work and calls named replacement
  owner(s), with complete caller coverage and responsibility rebinding;
- `remove`: the step has no required behavior left, or all behavior has proven
  replacement owners, and no caller or safety/evidence responsibility is
  orphaned;
- `explicit_on_demand`: the work is not part of the ordinary path and runs only
  from one or more named explicit triggers, with ordinary callers and
  responsibilities accounted for;
- `unresolved`: any current owner, caller, equivalence, replacement, trigger,
  or safety/evidence-owner proof is missing, stale, duplicated, or ambiguous.

For `merge`, `delegate`, `remove`, and `explicit_on_demand`, require the
complete caller inventory, the relevant equivalence or replacement evidence,
the complete safety/evidence responsibility inventory, and one exact
post-action owner binding for every surviving responsibility. A costly step
that alone owns a rejection rule, invariant, cleanup guarantee, release gate,
or final evidence remains unresolved or retained until that responsibility is
transferred and proved. Cost never erases responsibility.

Record measured operation count, invocation count, payload bytes, and estimated
token count as current, fingerprinted `ArchitectureReductionStepCost` evidence.
Use it only to order which steps deserve attention first. It cannot make a step
ready, substitute for equivalence, or authorize deletion. Return the complete
`ArchitectureReductionStepAssessment` rows and a deterministic
`cost_priority_step_ids` projection from the same review object.

## Relationship To Model Path Quality

ModelMaturation owns the path shape of one model. Architecture Reduction may
consume its compact current `PathQualityResult` only when exact blueprint
bindings map the cited model elements to concrete functions, helpers, modules,
adapters, facades, public entries, or validation layers. The result is
provenance for candidate discovery; it is never code-deletion, equivalence,
facade, consumer, effect, retirement, or affected-test proof, and this route
does not run a second model optimizer.

For any consumed model-path candidate, require the exact subject/currentness
and detail fingerprint. Preserve the faithful `observed` implementation path;
a behavior-changing improvement stays `normative_target` until code,
model-code-test bindings, affected topology, and current evidence match. A
missing, stale, unresolved, aggregate-only, or normative-as-observed result
remains a typed gap rather than a reason to retain or contract code.

Model path comparison and architecture step priority both obey hard semantics
before cost. Equivalent-path ranking uses current named dimensions and Pareto
dominance with no default scalar sum, implicit zero, caller-selected tie break,
or unrestricted optimum. Architecture step cost continues to rank review
attention only; the independent observable-contract or retirement proof below
still decides whether an implementation action is ready.

## Observable Contract

Before considering ordinary behavior-preserving contraction, declare the
behavior that must not change:

- source FlowGuard model id;
- source code boundary id;
- public entrypoints;
- observable outputs;
- observable state;
- observable side effects;
- validation boundaries;
- rationale.

This contract is the boundary for "same behavior." Internal proof fields may be
removed or merged only when the declared public behavior is preserved or the
report explicitly downgrades the proof to property-only. A property-only result
cannot authorize ordinary contraction. Intentional behavior retirement does
not pretend to satisfy equivalence; it uses the separately typed retirement
proof below.

## Intentional Behavior Retirement

Use `retire_behavior` only when the complete effective current product/DNA goal explicitly no
longer needs the behavior. It requires `proof_status=authorized_retirement` and
one exact-current `ArchitectureRetirementProof` that binds:

- the current-goal rationale and independently complete retirement inventory;
- retired Behavior Commitment Ledger commitments and behavior-block ids;
- model, code, test, public-interface, consumer, route, skill, prompt,
  topology-relation, release-claim, and negative-case identities;
- one disposition for every responsibility: `retire`, `replace`, `migrate`, or
  `retain_history`;
- every replacement or migration owner as exact-current and unambiguous;
- the complete required affected-validation route set and governed identity
  fingerprints.

Core DNA protections do not vanish just because a historical wrapper or route
is no longer needed. Required input/output, state/effect, topology,
model-code-test binding, negative-case/oracle, and bug-to-model-depth feedback
responsibilities must either remain under one current owner, move to one named
current owner with evidence, or receive an explicit product-level behavior
retirement disposition. Unknown responsibility is `unresolved`.

Retirement must leave zero alias, compatibility reader or adapter, fallback,
forwarder, alternate automatic success path, dangling current reference, or
retained runtime authority. Historical documents and immutable evidence may
remain only as archive history; they cannot keep runtime authority.

## Model-To-Code Mapping

Map model elements to implementation nodes before recommending contraction:

- FunctionBlock -> function, class, handler, command, component, or module;
- state field -> dataclass field, storage key, UI state, config, or record;
- side effect -> file write, API call, database write, subprocess, UI effect;
- public entrypoint -> CLI, API, export, UI route, command, or plugin surface.

If this mapping is absent, the review should block rather than producing a
code-level recommendation from model-only simplification.

## Candidate Types

Use `ArchitectureReductionCandidate` rows for candidate contractions:

- `merge_handlers`: two or more handlers can become one owner;
- `merge_modules`: modules can share one target module;
- `collapse_adapter`: an adapter only forwards or normalizes without owning
  behavior;
- `remove_branch`: a branch is dead, subsumed, or behavior-equivalent to
  another branch;
- `remove_state_field`: a state field is not part of the observable contract
  and does not affect required properties;
- `merge_state_phase`: two phases are behavior-equivalent at the observable
  boundary;
- `remove_duplicate_validation`: repeated validation paths prove the same
  obligation;
- `keep_public_facade`: internals can shrink but compatibility facade stays;
- `manual_review`: the candidate is intentionally deferred.

## Compatibility Surfaces

When a candidate exists because of an old, alternate, or compatibility-like
surface, add `CompatibilitySurfaceClassification` rows before deciding whether
the candidate is ready. Classify old command aliases, event names, input
shapes, migration branches, old/replaced fields, field aliases, public facades,
pass-through compatibility adapters, retired validation artifacts, and negative
legacy tests.

Use these classifications:

- `current_contract`: still active behavior; remove/collapse is blocked;
- `boundary_adapter`: edge stays but should translate into the current owner
  contract; public surfaces require StructureMesh;
- `negative_legacy_test`: evidence that retired input is rejected; do not
  delete unless replacement rejection evidence is cited;
- `archive_only`: historical evidence only; runtime authority blocks;
- `prune_candidate`: obsolete surface that can contract when proof status is
  ready;
- `evidence_needed`: insufficient evidence; linked candidates are not ready.

This classification is pre-reduction guidance. It does not replace
`LegacyPathDisposition` for post-repair closure when an old executable path
remains reachable.
It also does not replace FieldLifecycleMesh disposition when an old or
compatibility-like field remains reachable.

A retained same-intent facade preserves only an external entry boundary. It
must name the stable intent, active commitment, selected primary path, and owner
contract, with current evidence that it delegates to that path. Independent
business success, primary side effects, terminal mutation, or delegation to a
different same-intent path blocks keep-facade readiness.

A behavior selected for retirement cannot survive through a retained facade,
boundary adapter, old command/event/input alias, compatibility reader,
fallback, or forwarder. If an external contract is still required, classify it
as `retain` or migrate it to one current replacement owner; do not call the old
runtime path retired.

## Proof Status

Every candidate must have one proof status:

- `safe_by_equivalence`: preserves declared observable behavior;
- `safe_by_public_facade`: internals can shrink while the public facade stays;
- `authorized_retirement`: may end explicitly identified obsolete behavior
  only when the complete exact-current retirement proof passes;
- `property_only_safe`: preserves selected invariants only, not full behavior;
- `needs_conformance_replay`: needs real-code replay before code contraction;
- `risky_keep`: looks duplicate but should stay visible;
- `blocked_by_missing_evidence`: do not contract yet.

For ordinary actions, only `safe_by_equivalence` and
`safe_by_public_facade` can become ready contraction candidates.
`authorized_retirement` is ready only with `target_action=retire_behavior` and
one complete current `ArchitectureRetirementProof`; it is invalid on an
ordinary contract action. Property-only and replay-needed candidates are
useful diagnostics, not safe deletion or retirement proof.
Scoped, risky, or evidence-needed candidates that remain relevant should be
recorded as maintenance obligations with their owner route instead of prose
TODOs.

## Target Actions

Ready candidates produce target architecture actions:

- `merge`;
- `collapse`;
- `remove`;
- `keep_facade`;
- `retire_behavior`;
- `manual_review`.

Public-entrypoint candidates must route through StructureMesh or equivalent
public parity evidence. Removing observable state or changing observable side
effects without full equivalence proof must block for ordinary actions. An
intentional retirement may change those observables only when its complete
current retirement proof and all required affected routes pass.

## Companion Route Handoff

Architecture Reduction is usually called by or hands off to another route:

- Existing Model Preflight supplies ownership and duplicate-boundary evidence.
- Code Structure Recommendation turns ready target actions into module
  ownership.
- StructureMesh governs the production refactor and public-entrypoint parity.
- DevelopmentProcessFlow governs edit order, retirement/replacement lifecycle
  accounting, evidence freshness, affected validation, and done/release claims.
- ModelMesh supplies sibling model overlap and parent/child boundary evidence.
- Model-Test Alignment supplies obligation and test duplication evidence.
- FieldLifecycleMesh supplies old-field ids, replacement field ids, and
  disposition evidence for field compatibility surfaces.
- UI Flow Structure supplies UI state/control/display duplication evidence.
- Layered boundary proof may expose duplicate child ownership; reduce the
  duplicated implementation or route the ownership conflict back to ModelMesh
  before adding more leaf tests.

## Required Hazards

Before trusting the route, make these known-bad variants fail:

- missing existing model grounding;
- retain justified only by history, age, former importance, route membership,
  or the existence of tests;
- missing observable contract;
- missing model-to-code mapping;
- unclassified candidates;
- intentional behavior change hidden inside an ordinary `contract` action;
- `authorized_retirement` attached to an ordinary action;
- `retire_behavior` without one complete exact-current retirement proof;
- missing, stale, duplicated, unknown, or ambiguous retirement owner or
  responsibility disposition;
- retired wrapper removes a still-required DNA protection with no current
  replacement owner and no explicit product-level retirement decision;
- retirement orphans a negative case, rejection rule, oracle, or
  bug-to-model-depth feedback responsibility;
- alias, compatibility reader/adapter, fallback, forwarder, alternate success,
  dangling current reference, or runtime authority survives retirement;
- unclassified compatibility surfaces around old paths or old fields;
- hidden proof status;
- risky candidates silently treated as deletions;
- current contracts treated as obsolete compatibility;
- negative legacy rejection tests deleted without replacement evidence;
- archive-only evidence retaining runtime authority;
- public entrypoint contraction without StructureMesh;
- missing target structure handoff;
- missing companion route triggers;
- direct production-code rewrite by the review route;
- hidden validation or parity gates.
- scoped or risky reduction candidates disappear instead of being preserved as
  maintenance obligations.
- illegal child overlap treated as a testing problem instead of a duplicate
  ownership or architecture-reduction candidate.
- expected same-intent candidate or canonical relation side omitted;
- canonical-relation/code-obligation ids left only in plan metadata;
- retained facade able to succeed without the selected primary path.
- target or experiment structure presented as current authority;
- old model owner retained as an alternate current success path after its
  commitment moved to the replacement owner;
- reduction applied to only part of a multi-model revision set;
- necessity decided from a latest delta, legacy revision, historical fold,
  root intent, or foreign model-owner binding.
- a retained route implicitly retaining all internal steps without individual
  current necessity decisions;
- repeated scans, reflections, evidence projections, fingerprints, or large
  token-facing payload builders escaping step assessment;
- merge, delegation, removal, or on-demand conversion with an incomplete caller
  inventory, missing equivalence/replacement evidence, or missing post-action
  safety/evidence owner;
- on-demand conversion without a named explicit trigger;
- a high-cost or low-value label used as deletion proof;
- a unique safety or final-evidence owner removed merely because it is costly;
- a second whole-target scan launched for step review instead of reusing the
  current inventory and reverse caller index.

## Reporting

For non-trivial reviews, show a compact user-facing diagram with current code
boundary, current DNA goal, source model, the four-way necessity decision,
observable contract or retirement proof, compatibility-surface classification,
reduction candidates, proof status, target structure, and required next route.
The diagram explains the review and does not replace tests, conformance replay,
retirement responsibility disposition, LegacyPathDisposition, or StructureMesh
evidence.

## Blueprint Layer Boundary

Architecture Reduction consumes exact-current `inventory`, `traceability`,
`independent_semantics`, and affected `model_code_test` evidence when judging a
candidate. It owns the current-necessity classification, ordinary
observable-contract equivalence decision, and evidence-bound intentional
retirement decision for that candidate. It does not upgrade consumed layers or
qualify `resource_oracle` or `static_blueprint`.

Ordinary work reads only the affected current model/inventory closure. A
whole-target reduction inventory runs only for an explicit blueprint self-audit
or named release-cleanup obligation; even then, this review authorizes no
deletion or refactor. Uncertain
necessity/equivalence, incomplete retirement responsibilities, missing
candidate coverage, or missing/duplicate/ambiguous native ownership stays
unresolved or blocked with no fallback.

Return any supplied canonical `deepest_proven_layer` unchanged plus the first
unresolved necessity/owner/equivalence/retirement/evidence gap. Keep user
choice, maturation, and implementation admission independent.

For FlowGuard self-cleanup, accept only the exact typed self-blueprint built
once from the current target root. Match its subject revision, implementation and
test inventories, manifest, behavior report, and complete typed fingerprint;
reject label-only objects and caller-authored identity wrappers. Independently
derive a complete denominator covering oversized
modules, repeated shapes, command routes, branches, adapters, wrappers/facades,
builders, serializers, unreferenced helpers, fallback/alias/compatibility paths,
providers, public entries, resources, tests, and repeated validation paths. The
universe and candidate inventory have different source identities.
Every surface and signal receives one independently evidenced four-way
necessity decision. An owned singleton may be `retain` only when its exact
source surface has one complete current necessity witness binding accepted
effective intent, one exact behavior/model/code owner, normalized semantic
specifications, resolved consumers or one active reviewed external behavior
commitment, and model-code-test evidence. Load and review the BCL once per
audit; accept an external commitment only when that review binds the exact
current primary model, the same blueprint owner contract, and current test
evidence. A public role alone is not a current
promise. A maintenance-like name is a classification signal only; materialize
a name-related candidate only when two or more current surfaces have an exact
shared call or structure relation. A candidate cannot retain merely because
its sources or structural ids differ: bind the comparison to the candidate,
require one witness per member, and prove that every normalized current
semantic-obligation fingerprint is pairwise different. Any repeated semantic
fingerprint, including a partial repeat inside a larger group, remains
`unresolved` plus `risky_keep`. An ordinary `contract-equivalent` decision
requires current observable equivalence or facade delegation. A
`retire-behavior-with-complete-current-proof` decision requires the exact
retirement action/status/proof and full responsibility closure described
above. Zero ready contraction or retirement candidates is a valid clean audit
result.
Every candidate records exact callers/consumers, behavior/model owners, state,
effects, errors, bound tests, current receipt identities, missing proof
obligations, and all required next routes. StructureMesh owns public or large
structural parity; DevelopmentProcessFlow owns the edit,
retirement/replacement lifecycle, evidence freshness, affected validation, and
release boundary for every contraction or retirement that is actually applied.

Before accepting a proof, use the repository's one current validation-owner
store. A read-only review discovers strict proof records only from canonical
aggregate receipts, reconstructs them from exact evidence context, ignores
stale receipts as history, and blocks duplicate exact-current authorities; it
does not accept caller-supplied proof records or a second registry. An explicit
proof action freezes one bundle and candidate inventory, selects a finite batch
by exact candidate id and fingerprint, and reuses exact-current aggregate
evidence before executing missing work. Run each selected candidate's exact test owner and candidate-level caller/consumer,
state, side-effect, and error parity owner under bounded process-tree
supervision under one batch producer; only terminal zero-exit children with
confirmed cleanup may be saved. Compose those real current children with the
child-bound owner receipt path and publish one aggregate batch authority.
Reload the aggregate and each child from the same canonical store,
rebuild their current owner contracts and source/projected/dependency/
toolchain/environment contexts, and run the native verifier. A caller-written
leaf pass, alternate receipt root, unrelated test, missing parity obligation,
skipped or blocked child, timeout, failed command, unclean process tree, or
relabeled suite receipt remains unresolved. Receipt, proof-artifact, result,
child-execution, and owner-execution identities are unique per candidate;
different wrappers cannot reuse them across candidates.

For a composed self-maintenance or release-cleanup pass, build the exact
self-blueprint once and pass that in-memory bundle to the reduction reviewer.
Build one deterministic reverse call-alias index over the governed surfaces;
do not rescan the complete surface inventory for every candidate member. The
reduction result must bind the consumed blueprint, implementation inventory,
and behavior-report fingerprints. Do not persist or silently reuse a stale
blueprint cache, and do not split the composed pass into duplicate validation
owners that rebuild the same authority.
Immediately before publishing the read-only result, independently recompute the
typed build-input identity over model authority, the accepted revision's
complete effective-intent view and owner bindings, observed
snapshot, the complete classified file inventory, semantic mesh, and provider
contracts, and recheck every proof-owner identity. Do not rebuild all behavior,
coverage, normalized, and candidate objects a second time. A concurrent write
makes the review stale instead of allowing the earlier in-memory bundle to claim
currentness.
When compact output is requested, project its bounded fields directly from the
in-memory reviews. Do not expand the complete blueprint or reduction payload
only to discard it before emission.
Reuse the exact canonical fingerprint already computed by immutable large
behavior evidence; do not rebuild the complete evidence payload for every
downstream review.
When several candidates consume the same exact tests, coverage rows, dimensions,
and current receipt ids, materialize that evidence neighborhood once in the
direct-current content-addressed catalog. Each candidate keeps its local caller,
behavior, model, owner, state, effect, and error fields plus one exact catalog id
and fingerprint. The composite candidate identity binds both parts. Proof
consumers resolve the complete semantic contract and reject missing, stale,
foreign, duplicated, ambiguous, fingerprint-mismatched, or inline-fallback
evidence; immutable proof receipts remain self-contained.
Affected-object and topology-edge integrity checks likewise build the exact
validated object-id denominator once and reuse it for every edge. Every object
payload still receives its own real fingerprint check; denominator reuse never
authorizes trusting an expected fingerprint or skipping an edge.
For large normalized payloads, stream the exact canonical representation into
the digest and byte counter. Release the logical payload before constructing
the physical projection; several complete serialized copies must never coexist.
