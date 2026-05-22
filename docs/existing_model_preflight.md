# Existing Model Preflight

Existing Model Preflight is FlowGuard's companion route for work inside an
existing modeled system. It makes the current model map visible before an agent
discusses, proposes, or implements a non-trivial change.

Use the plain rule:

```text
Understand the existing FlowGuard model boundary before creating a new one.
```

## Use Cases

Use it when a task touches an existing modeled system and involves:

- feature or behavior changes;
- bug fixes or post-runtime model misses;
- architecture proposals or module split ideas;
- UI flow, UI state, or UI implementation changes;
- test strategy, validation, or evidence changes;
- prompt, skill, or agent-workflow changes;
- parent/child model, release, or process confidence changes.

Skip it for typo-only edits, formatting-only work, direct command answers, pure
read-only explanations, or greenfield work with no existing model context.

## Light And Full Modes

Light mode is for discussion and early analysis. It records likely relevant
models, existing ownership, a reuse-first direction, and the likely downstream
FlowGuard route.

Full mode is for implementation, OpenSpec proposals, major architecture
decisions, and risky behavior changes. It records searched paths, relevant
models, ownership snapshots, reuse decisions, duplicate-boundary risks,
downstream routes, and stale or no-model-found gaps.

## Public API

The main objects are:

- `ModelContextHit`: one existing model that may own the requested behavior.
- `ExistingOwnershipSnapshot`: FunctionBlock, state, side-effect,
  public-entrypoint, and responsibility ownership extracted from model hits.
- `DuplicateBoundaryRisk`: an overlap between a proposed boundary and an
  existing owner.
- `ExistingModelPreflight`: the light or full preflight report.
- `ExistingModelPreflightReport`: structured review output.
- `review_existing_model_preflight(preflight)`: the executable checker.

## Example

```python
from flowguard import (
    ExistingModelPreflight,
    ExistingOwnershipSnapshot,
    ModelContextHit,
    REUSE_DECISION_EXTEND_EXISTING,
    review_existing_model_preflight,
)


preflight = ExistingModelPreflight(
    "router-preflight",
    "Extend router scheduling behavior",
    mode="full",
    model_search_performed=True,
    search_paths=(".flowguard/router", "docs"),
    relevant_models=(
        ModelContextHit(
            "router-flow",
            model_path=".flowguard/router/model.py",
            responsibilities=("route scheduling",),
            function_blocks=("RouteTask",),
            state_owned=("pending_tasks",),
            side_effects_owned=("dispatch_task",),
            public_entrypoints=("router.dispatch",),
        ),
    ),
    ownership_snapshot=ExistingOwnershipSnapshot(
        function_block_owners=(("RouteTask", "router-flow"),),
        state_owners=(("pending_tasks", "router-flow"),),
        side_effect_owners=(("dispatch_task", "router-flow"),),
        public_entrypoint_owners=(("router.dispatch", "router-flow"),),
    ),
    reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
    downstream_routes=("development_process_flow",),
    rationale="The existing router model owns task dispatch, so extend it.",
)

report = review_existing_model_preflight(preflight)
print(report.format_text())
```

For a ready scaffold, run:

```powershell
python -m flowguard existing-model-preflight-template --output .
```

## Relationship To Other Routes

Existing Model Preflight does not implement the change. It supplies the model
map to the route that owns the concrete work:

- Code Structure Recommendation derives implementation structure.
- ModelMesh governs parent/child model confidence.
- Layered boundary proof joins parent coverage, child disjointness, child
  reattachment, and leaf boundary-matrix status when parent confidence depends
  on child models.
- StructureMesh governs existing code splits.
- UI Flow Structure governs UI behavior and implemented UI evidence.
- Model-Miss Review repairs models after runtime/test failures.
- DevelopmentProcessFlow governs staged work and evidence freshness.
- Risk Evidence Ledger consumes the relevant model ids, evidence ids, scoped
  gaps, and reuse decisions before a final full-confidence claim.

The preflight catches a different failure: proposing a new system before
checking the one already modeled. Its output tells the ledger which existing
model boundary owns the risk; it does not prove the tests or runtime evidence
by itself.

When layered proof is in scope, preflight should surface the existing parent,
child, and leaf model ids plus any duplicate-boundary risks before a new model
or test boundary is added.
