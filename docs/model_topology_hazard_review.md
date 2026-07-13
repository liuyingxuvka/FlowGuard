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
- Anchored blocking hazards block broad confidence until current route evidence
  handles them.
- FlowGuard skill/runtime old/new paths must be blocked or deleted. An ordinary
  software compatibility path may be preserved only by an explicit bounded
  requirement and owner.
- Duplicate, conflicting, unproven, or unresolved old/new business paths are
  anchored hazards. A model that runs locally can still stay scoped or blocked
  if it cannot say which useful business path was proven.

## Handoffs

- Coarse terminal states and parent/child compression route to Model Maturation.
- Testable model obligations route to Model-Test Alignment.
- Local-only or process evidence overclaim routes to DevelopmentProcessFlow.
- Old/new compatibility decisions route to Architecture Reduction and Risk
  Evidence Ledger.
- Duplicate business paths route to Architecture Reduction, Model Similarity,
  and Risk Evidence Ledger.
- Conflicting or unproven business paths route to Model Maturation,
  Model-Test Alignment, and Risk Evidence Ledger.
- Broad final confidence routes to Risk Evidence Ledger.

Use the starter template:

```powershell
python -m flowguard topology-hazard-template --output .
python .flowguard/model_topology_hazard_review/run_checks.py
```
