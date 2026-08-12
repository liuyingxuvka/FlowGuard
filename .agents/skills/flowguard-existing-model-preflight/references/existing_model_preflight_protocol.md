# Existing Model Preflight Protocol

Existing Model Preflight prevents agents from designing a parallel system before
they understand the FlowGuard models that already describe the current system.

It is a companion route. Pair it with the downstream route that owns the actual
work:

- non-trivial bug repair or bug after runtime/test evidence: Model-Miss Review;
- parent/child model or stale child evidence: ModelMesh;
- parent/child/leaf proof chain or finite code boundary matrix: ModelMesh,
  Model-Test Alignment, TestMesh, then layered boundary proof;
- code refactor or public entrypoint split: StructureMesh;
- implementation structure recommendation: Code Structure Recommendation;
- field additions, migrations, replacements, prompt/config fields, schema keys,
  or old-field disposition: FieldLifecycleMesh;
- UI state, control, journey, or implemented UI claim: UI Flow Structure;
- validation hierarchy or slow/stale tests: TestMesh;
- staged development or release confidence: DevelopmentProcessFlow;
- evidence-backed contraction of an existing mapped implementation boundary:
  ArchitectureReduction, only after its observable contract and proof status
  are explicit;
- unclear or ordinary behavior/state modeling: model-first kernel.

When the downstream work will make a final confidence claim, preserve model ids,
evidence ids, scoped gaps, and reuse decisions for the Risk Evidence Ledger.
Preflight identifies the existing owner; it does not prove test or runtime
evidence by itself.

## Trigger

Use this protocol for non-trivial discussion, analysis, proposal, feature,
bug-fix, refactor, UI, test, prompt, skill, agent-workflow, or process change
inside an existing modeled system.

For bug-fix work, the preflight should identify the existing model boundary
that owns the failed behavior before Model-Miss Review adds the root-cause,
same-class, model-code-test, or legacy-path closure evidence.

For field-bearing changes, the preflight should also identify existing
FieldLifecycleMesh owners, behavior field ids, and any unresolved field
lifecycle gap before code or model changes begin.

Do not use it for typo-only changes, formatting-only work, direct command
answers, pure read-only explanations, or greenfield work that has no existing
model context.

## Plane-First Commitment Lookup

Before repository path discovery, query the canonical BCL with the task
summary and any exact commitment id, path, tool, workflow family, or observed
error signature. Record `behavior_lookup_status`, selected
`primary_behavior_plane`, primary commitment hits, typed related hits, plane
ambiguity, match explanations, owner models, and `ledger_fingerprint`.

Primary hits come from one selected plane. A related product/process/AI row may
explain context only through a typed relation and cannot become the primary
owner through shared wording. If the ledger is missing or stale, fall back to
the existing path/model scan and say so. If several planes remain plausible,
keep their candidates separate and block full-confidence downstream selection
until caller context selects one.

## Light Mode

Light mode is enough for early thinking. It should say:

- which existing model boundary seems relevant;
- which existing responsibility should be reused or extended;
- the accepted revision/effective-view fingerprints and exact affected-owner
  intent binding, or the visible current-intent gap;
- where duplicate-boundary risk might appear;
- which downstream route is likely.

Light mode should not claim implementation readiness.

Light mode and ordinary full mode remain affected-only. They select the
current commitment/model/path owner closure and use the normalized blueprint
index to load only exact affected shards, referenced objects, and required
ancestors; they do not construct or scan the whole target merely because a
blueprint exists.

## Path-Quality Lookup And Handoff

For every selected existing model owner, look up the compact current
path-quality subject/result/detail fingerprints attached to the accepted
revision. Report its mode, trigger ids, bounded conclusion, unresolved ids,
producer, and currentness without loading deep candidate or witness bodies.
Verify that model, purpose, complete effective intent, obligation, provider,
dependency, code, test, oracle, evidence, retained-element inventory, and
affected-topology identities still match.

An unchanged result is reusable only when all those identities remain exact.
A new or materially changed model, a mismatched identity, or a missing/stale/
unresolved row becomes a typed ModelMaturation handoff. Preflight may report
the current lightweight structural finding or cross-model relation that
supplies an exact deep-review trigger, but it does not enumerate candidates,
compare costs, create necessity witnesses, or decide model path quality.

Keep `observed` current behavior separate from a cleaner `normative_target`.
The same provider-neutral lookup applies to other programming languages and to
non-code workflows; a path or Python symbol is never required as semantic
authority. Preflight reads current model authority only; it never creates
another authority, route, CLI, reader, or pointer.

## Full Mode

Full mode is required before implementation, OpenSpec proposal, major
architecture changes, or risky behavior changes.

Use `ExistingModelPreflight` and `review_existing_model_preflight(...)` when
possible. A full report should include:

- `model_search_performed=True`;
- search paths or inventory consulted;
- relevant `ModelContextHit` rows, or `no_model_found` with a reason;
- `ExistingOwnershipSnapshot` for FunctionBlocks, state, side effects,
  public entrypoints, behavior fields, and responsibilities when models are
  found;
- accepted revision and effective-view fingerprints, plus the exact active
  intent contribution ids bound to every selected model owner;
- layered proof status for parent models with children: evidence id, parent
  coverage, child disjointness, child reattachment, and leaf boundary-matrix
  status;
- a reuse decision;
- `DuplicateBoundaryRisk` rows for any overlapping ownership;
- downstream FlowGuard routes;
- `field_lifecycle_mesh` as a downstream route when behavior-bearing fields or
  old/replaced fields are in scope;
- rationale and stale evidence notes.

When an external business intent is affected, full mode also declares the
expected surface inventory independently from the supplied candidate list. Add
typed rows for UI, API, CLI, alias, adapter, wrapper, helper, and compatibility
surfaces with their stable intent, commitment, path, expected terminal,
material state writes/side effects, owner, freshness, and evidence. Preserve
unknown or scoped rows explicitly. If external semantics match an existing
current path, hand that commitment/path to BCL/PPA and recommend reuse or
extension. A new page, command, or wrapper alone is not a new behavior.

### Explicit whole-target blueprint handoff

Enter this handoff only when the task explicitly claims, exports, or qualifies
a whole-target blueprint, or when a current qualification obligation names that
scope. Consume the frozen profile plan and independent applicable inventory rather than
deriving the implementation denominator from models, CodeContracts, BCL, or a
caller-supplied file list. Preserve:

- target descriptor/profile, provider registry/results, and snapshot identities;
- accepted revision/effective-view identity, complete independent model-owner
  denominator, exact owner bindings, and any missing or foreign owner ids;
- implementation inventory id/fingerprint and declared software boundary;
- exact required, dispositioned, and unresolved file/surface ids;
- inventory findings including parse, dynamic, adapter, path, and freshness gaps;
- downstream owners for bidirectional binding, structure partition, model
  topology, resource/oracle closure, and process freshness.

Preflight does not copy internal inventory rows into BCL, interpret source
semantics, qualify the blueprint, or export shards.

## Required Hazards

Known-bad variants should fail or be reported:

- route selected before model search;
- implementation work using only a light note;
- relevant model found but ownership evidence missing;
- new boundary proposed without explaining why existing models cannot carry it;
- duplicate state, side-effect, FunctionBlock, entrypoint, or responsibility
  owner without resolution;
- behavior-bearing field changed without field lifecycle ownership or a
  downstream FieldLifecycleMesh route;
- no model found but search path and reason omitted;
- stale model evidence treated as green;
- a known affected same-intent surface omitted from the expected inventory;
- an opaque similarity id used instead of materialized surface/commitment/path/evidence rows;
- an equivalent current path ignored while a new same-intent boundary is proposed;
- a wrong-plane text match promoted over the selected plane;
- a related-plane hit treated as an executable instruction or merged owner;
- missing/stale ledger lookup silently treated as current commitment evidence;
- parent model found but parent coverage, child disjointness, child
  reattachment, or leaf boundary-matrix status is unknown when the downstream
  work needs parent/child confidence.
- a whole-software blueprint inferred from model/contract declarations without
  an independent current implementation inventory;
- ordinary affected work widened into a whole-repository inventory scan;
- static blueprint completeness promoted beyond its exact evidence boundary;
- a parent, sibling, prior revision, installed projection, or caller-authored
  flag used to manufacture a missing current path-quality result;
- deep candidates loaded or compared during ordinary owner lookup;
- a normative target reported as the current observed path;
- ArchitectureReduction proposed from size, style, or cost alone without a
  current model/code map and observable behavior-preservation evidence.
- a legacy revision, latest revision delta, historical concatenation, root
  intent, or matching words reported as the current affected-owner intent.

## Output Shape

Recommended short report:

```text
Existing Model Preflight

Task:
- ...

Model search:
- paths:
- hits:

Existing ownership:
- FunctionBlocks:
- State:
- Fields:
- Side effects:
- Public entrypoints:
- Responsibilities:

Reuse decision:
- reuse_existing / extend_existing / add_child_model / new_boundary / no_model_found / skip_with_reason

Duplicate-risk check:
- ...

Recommended downstream route:
- ...

Blueprint handoff (only when explicitly triggered):
- inventory fingerprint:
- required/unresolved surface ids:
- binding/structure/topology/process owners:
```

## Boundary

This protocol decides whether the agent has understood the current model map.
It does not prove the planned change is correct. Downstream FlowGuard routes and
ordinary tests still provide the behavioral, structural, and release evidence.

If the downstream claim depends on layered proof, preflight should identify the
existing parent model, child models, leaf models, current evidence ids, and any
duplicate-boundary risks before a new model or test boundary is added. A model
reference plus ordinary test mention is not the same as complete finite leaf
boundary proof.

## Authority-first lookup

Begin with `model-system-audit`, the sole observed `ModelSystemSnapshot`, and
its accepted `ModelRevisionSet`. A current hit binds logical model id, exact
model and runner fingerprints, resolved input inventory, purpose closure,
subject revision, snapshot fingerprint, accepted revision fingerprint,
complete effective-view fingerprint, and that model owner's exact active
intent binding. Whole-target scope also reports the independent owner
denominator and its missing/foreign binding ids. Behavior-ledger, path, source, docs, and
OpenSpec discovery may add candidate context, but they cannot independently
set `evidence_current=true`.

Keep the observed implementation, normative target, and counterfactual
experiment in separate subject lanes. Full preflight blocks when the observed
head is missing or invalid, when a referenced current model is absent from the
snapshot, or when a target/experiment is presented as current. Report explicit
authority gaps and route target changes to ModelMesh plus
DevelopmentProcessFlow.

Use select-before-materialize for ordinary lookup. First select same-plane
commitment owners, changed-path owners, identity matches, and one-hop declared
relations. Read only that bounded closure. An omitted changed path never means
"read every model"; broad authority inventory requires an explicit broad
scope. Light mode returns identities, paths, fingerprints, and ownership
without loading model bodies or class inventories. Full mode adds those details
only for the selected closure.

## Executable composition handoff

When two or more current portable models have a candidate event, identity,
retry, ordering, shared-resource, cache, external-confirmation, atomicity,
compensation, or owner-bound property relation, emit `compose_existing_models`.
The handoff names exact current model fingerprints, any existing
PortableSystemDefinition reference, proposed relation anchors, candidate
changed roots, discovery-evidence identity, and unresolved facts. Candidate
relations remain proposed until the portable-system owner accepts them. Full
preflight blocks broad executable-composition confidence when required relation
or freshness facts remain ambiguous; it does not copy ports, bindings,
resources, steps, or properties into a second authoritative preflight schema.

## Read-only WorkContext

Attach all declared WorkContexts only after canonical plane-first commitment
lookup. Preserve context id, adapter id, native work id, native owner, subject
lane, current fingerprint, read-only flag, generic artifact roles, artifact
ids, source references, and content fingerprints. Planning context cannot own
product behavior.

Missing lookup, unknown adapter, path escape, stale context, mutable access,
missing required roles/artifact identities, a wrong subject lane/primary
owner, or any provider execution/session/cache/receipt bridge blocks full
preflight. No provider-task-to-test-owner reconciliation is performed here.

## Maturation Handoff Boundary

Full preflight means the current same-plane owner map, affected surfaces,
stable identities, and duplicate boundary are completely accounted for. It is
not a sufficiency or implementation-ready verdict. Emit those exact owner,
surface, commitment, intent, path, and unresolved-angle facts as one current
typed Model Maturation contribution; Model Maturation decides depth and
DevelopmentProcessFlow decides implementation admission.

## Blueprint Layer Contribution

Existing Model Preflight contributes only to the inventory and traceability
owners declared by the frozen target plan. For explicit whole-software scope it consumes the project definition, the
independent implementation inventory, the complete `ProjectTestInventory`
embedded in the project blueprint, its current independent source-audit
fingerprint, current observed
model/effective-intent lineage, exact owner/path/symbol bindings, and terminal
dispositions. It reports the matching and missing ids; it does not derive the
denominator from models, contracts, BCL rows, or a caller file list.

Preflight cannot mark `independent_semantics`, `model_code_test`,
`resource_oracle`, or `static_blueprint` complete.
Return any supplied canonical `deepest_proven_layer` unchanged plus the first
unresolved native owner/evidence gap introduced by lookup. Missing, duplicate,
ambiguous, or stale project ownership blocks; the FlowGuard self-model and
authoritative-model-system root are never fallback owners for target software.

Whole-software lookup needs an explicit blueprint/export/qualification or
named release/self-qualification task fact. Ordinary full and light preflight
stay affected-only. Keep user choice, maturation, and admission separate.

When supplied a normalized blueprint index, verify its logical fingerprint and
use `AffectedBlueprintReader` to load only exact affected shards, referenced
objects, and ancestors. Return referenced primary behavior owners and
supporting-surface relations as observations. Do not accept a small result
derived after a whole bundle was already materialized.
Missing shared objects or a fingerprint mismatch blocks; Preflight never fills
in a missing `BehaviorBlockContract`, resource, intent, oracle, or test row.

For a portable blueprint handoff, carry the exact canonical projection,
independent owner denominator, provider/profile identity, and subject revision.
Report static, portable, and execution status separately and keep compact
omitted counts and unresolved ids. Do not copy inventories into a second
authority or replace a target's real adapter with Python.
