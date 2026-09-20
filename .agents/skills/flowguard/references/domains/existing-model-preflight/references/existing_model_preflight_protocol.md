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

## Conditional detailed preflight

Load `references/existing_model_preflight_change_details.md` only when implementation or model change is requested, current intent is missing/ambiguous, a whole-target blueprint/qualification claim is explicit, or executable composition/path-quality handoff is required. It contains Detailed affected preflight, Required Hazards, whole-target blueprint handoff, Path-Quality Lookup And Handoff, Executable composition handoff, Maturation Handoff Boundary, Blueprint Layer Contribution, and ModelMaturation handoff. Otherwise keep these sections `not_triggered` and use only the compact lookup below.
Light lookup does not enumerate candidates; detailed candidate composition remains trigger-bound.

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
