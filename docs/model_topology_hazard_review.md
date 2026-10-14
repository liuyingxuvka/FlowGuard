# Model Topology Hazard Review

Model Topology Hazard Review is the FlowGuard route for the question: "the
model is green locally, but what future-use problem does this topology suggest?"

It is not a generic AI risk checklist. A hard finding must name a concrete
topology anchor: state, edge, side effect, terminal node, old/new compatibility
path, external boundary, shared writer, parent/child compression landmark, or
business path. Unanchored AI concerns stay as observations.

## Public Helpers

- `UsageIntent`: local, CLI, library, plugin, service, release, migration,
  final claim, history/compatibility possibility, and goal.
- `BusinessPathIdentity`: stable path id, business intent, trigger, expected
  terminal, state writes, side effects, equivalence, exclusivity, superseded
  old paths, compatibility disposition, and source/runtime evidence ids.
- `TopologyDigest`: compact model shape with nodes, edges, landmarks, and usage.
- `TopologyHazardCandidate`: one anchored future-use hazard and its disposition.
- `TopologyHazardReviewPlan` and `TopologyHazardReport`: executable review
  input and output.
- `infer_topology_digest(...)`, `infer_topology_hazard_plan(...)`, and
  `review_topology_hazards(...)`.

## Confidence Rules

- Unanchored hard candidates are downgraded to observation-only.
- Anchored scoped hazards keep confidence scoped until handled or consciously
  scoped with reason.
- Anchored blocking hazards block broad confidence until the follow-up route
  handles them and its models or tests have been rerun and pass.
- Old/new compatibility paths need an explicit preserve, migrate, block,
  delete, latest-schema-first cleanup, or scoped-out disposition.
- Duplicate, conflicting, unproven, or unresolved old/new business paths are
  anchored hazards. A model that runs locally can still stay scoped or blocked
  if it cannot say which useful business path was proven.

## Handoffs

Each candidate carries a route code (`TOPOLOGY_ROUTE_*`) and a disposition
(`TOPOLOGY_DISPOSITION_*`) that say what to do next:

- Coarse terminal states and parent/child compression: refine the model itself
  (`model_miss_review`) or split it with ModelMesh.
- Testable model obligations route to Model-Test Alignment.
- Local-only or process evidence overclaim routes to DevelopmentProcessFlow.
- Old/new compatibility decisions route to Architecture Reduction.
- Duplicate business paths route to Architecture Reduction with an explicit
  `CanonicalRelation` between the paths.
- Conflicting or unproven business paths need a model refinement plus
  Model-Test Alignment tests that show which path the real code takes.
- Broad final confidence (`development_process_flow` route) means: state the
  confidence only after the models and tests that cover the hazard have been
  rerun and pass, and keep anything unproven listed as a gap.

Pass the plan as `FlowGuardCheckPlan(topology_hazard_plan=..., usage_intent=...)`
to get a topology section in `run_model_first_checks(...)`, or call
`review_topology_hazards(...)` directly.

Starter template (prints the files; add `--write .` to write them):

```powershell
python -m flowguard template topology-hazard
```

Run the generated check script. After later code changes,
`python -m flowguard change` lists which models to rerun.
