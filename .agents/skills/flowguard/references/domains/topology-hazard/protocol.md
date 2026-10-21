# Topology Hazard Review
Reuse the current owner model and tests. Create a persistent scaffold only for a new
reusable boundary; apply the regression examples relevant to this change.

Use this after a model is green and someone wants to call the work done, released or
production-ready. The bug class is "green locally, broken in real use", found from the
model's shape: one state written by two paths, a database write or email that a retry
replays, success reported before an external confirmation, an old path still reachable
next to the new one, two business paths doing the same job or racing on the same state.
Each hazard must point at a real node, edge or business path of the model. A worry with
no anchor stays an observation and never blocks.

## Use when

- A model in `map.json` passes and the claim is broad: done, release, publish, production.
- The modeled blocks have `side_effects` (db, file, network, emit) and inputs can repeat.
- Two components or blocks write the same state, or `map discover` shows several writers.
- An old/legacy/compat path or schema history still exists next to the new path.
- Two business paths share a trigger and state but differ in result or side effects.

## Do not use when

- No model exists for the behavior. Write one first (plain modeling, model recipes).
- A model was green and a test then failed. Use model-miss.
- You must decide to delete, migrate or keep an old path. Use architecture-reduction;
  this review only says that a decision is missing.

## Inputs

- `python -m flowguard read --component ID`: `entrypoints`, `state`, `side_effects`,
  `depends_on`, `tests`, `models`. `side_effects` and `state` become block `side_effects`/`writes`.
- `python -m flowguard map discover --component ID`: `effects` by kind,
  `entrypoint_effect_reach`, `state_writers` (a state with two writers is a real shared writer).
- The owning model file (listed in `models`), its `Workflow` blocks with `reads`,
  `writes`, `side_effects`, and its `initial_states` and `external_inputs`.
- The final claim and usage: local only, CLI, library, plugin, service, release, migration;
  whether old data or old callers exist.
- Important business paths: id, intent, trigger, expected terminal, writes, side effects,
  and the test ids that exercise each one.

## Steps

1. Reuse the owner's native hazard review/model; only a missing reusable boundary needs
   `python -m flowguard template topology-hazard --write .`, which writes
   owner `model.py`, `.flowguard/verification/owners/model_topology_hazard_review/run_checks.py` and notes.
   Its blocked demo exits 1; a passing real review exits 0. Keep per-case asserts (step 6).
2. Build the usage intent: `UsageIntent(usage_modes=(TOPOLOGY_USAGE_RELEASE,), final_claim="release",
   compatibility_policy=TOPOLOGY_COMPAT_UNKNOWN, persistent_history_possible=...)`.
   `infer_usage_intent(goal=, final_claim=, project_kind=)` guesses one from text; check it.
3. Declare business paths as `BusinessPathIdentity(path_id, business_intent=, trigger=,
   expected_terminal=, state_writes=, side_effects=, equivalent_to=,
   exclusive_with=, supersedes=, compatibility_disposition=)`.
4. Build and run the review:

```python
from dataclasses import replace
from flowguard import (BusinessPathIdentity, UsageIntent, TOPOLOGY_USAGE_RELEASE,
    infer_topology_hazard_plan, derive_topology_hazard_candidates, review_topology_hazards)
plan = infer_topology_hazard_plan(workflow=build_workflow(), initial_states=(State(),),
    external_inputs=(Submit(),), business_paths=PATHS, plan_id="orders",
    usage_intent=UsageIntent(usage_modes=(TOPOLOGY_USAGE_RELEASE,), final_claim="release"))
report = review_topology_hazards(plan)
print(report.format_text())   # decision, confidence, findings, unresolved_hazard_ids
```

5. Resolve each unresolved hazard. Fix the model or code, or add the evidence, then mark it:
   take `derive_topology_hazard_candidates(plan.digest)`, `replace(c, handled=True)` for a
   hazard now covered by a named test, or `replace(c, disposition=TOPOLOGY_DISPOSITION_SCOPED_OUT,
   scoped_reason="...")` with a concrete reason, and rerun with `replace(plan, candidates=...)`.
   Pass every candidate: a non-empty `candidates` turns off automatic candidates.
   Each candidate's `required_routes` names the follow-up (for example `model_miss_review`,
   `model_test_alignment`, `architecture_reduction`, `development_process_flow`).
6. Review the intended plan and relevant broken cases directly or in the existing owner; assert the intended
   one gives `report.ok` and that relevant broken plans give their expected codes. A persistent runner returns 0 only then.
7. If a persistent runner was created or changed, register it in the owner's `models`; run the
   selected registered owner once with `python -m flowguard map models <id>`. Direct review needs no runner.
   Then use `python -m flowguard change` and execute affected checks not already current.

## What blocks

| Code / hazard | Meaning |
|---|---|
| `topology_hazard_unresolved` (blocker) | An anchored hazard is open and blocks the broad claim. |
| `topology_hazard_unresolved` (confidence_gap) | Open hazard; result is `scoped`, not a clean pass. |
| `unknown_topology_anchor` | A candidate names an anchor id not in the digest (stale or typo). |
| `topology_hazard_scoped_out_without_reason` | Hazard scoped out with an empty `scoped_reason`. |
| `topology_hazard_scoped_out` | Scoped out with a reason; confidence stays `scoped`. |
| `unanchored_hazard_observation_only` | Info only: a worry with no anchor; it cannot block. |
| `hazard:repeatable-side-effect:*` | Repeatable edge with side effects; blocks broad usage. |
| `hazard:compatibility:*` | Old/compat keyword or history; blocks broad usage if `compatibility_policy` is unknown. |
| `hazard:business-path-conflict:*` | Paths share trigger and a write or effect but differ in terminal or effects. |
| `hazard:business-path-legacy:*` | Path `supersedes` old ones with no `compatibility_disposition`. |
| `hazard:business-path-duplicate:*` | Two paths do the same job (gap, not a blocker). |

Decision values: `topology_hazard_pass`, `topology_hazard_scoped_confidence`, `topology_hazard_blocked`.

## Risk-specific regression examples

- A SaveRecord block with `side_effects=("database_write",)`, repeatable input, release
  claim, no idempotency evidence: must give a blocker on `hazard:repeatable-side-effect:*`.
- A hard candidate with no anchor ("users may dislike it"): must stay
  `unanchored_hazard_observation_only` and must not block.
- Two business paths with the same intent, trigger and expected terminal, one with
  `source_labels=("legacy adapter",)`: must give `hazard:business-path-duplicate:*`, not pass.
- A hazard scoped out with an empty reason: must give `topology_hazard_scoped_out_without_reason`.

## Done when

- [ ] The selected direct native review or existing-owner model passes; relevant broken plans give
      their expected codes. Any new/changed persistent runner is registered and run once through `map models`.
- [ ] Every remaining hazard is handled with a named test, or scoped with a written reason.
- [ ] Scoped confidence is reported as scoped, never as a clean pass.
- [ ] The tests that cover handled hazards pass and are listed in the component's `tests`.
- [ ] `python -m flowguard change` is clean; you report what ran, what was skipped, and why.

## Limits

- It reads declared shape only (`reads`, `writes`, `side_effects`, names, business paths).
  It does not run the code or prove idempotency; pair it with real tests.
- State/effect edges of one workflow block share one writer; two distinct blocks still flag shared state.
- Substring keyword match: "threshold" and "hold" match "old" (legacy landmark, a blocker under
  broad usage). Workaround: rename the block, or set that candidate to observation with a note.
- Any `external_inputs` mark every edge repeatable. Liveness and fairness are not checked here.
