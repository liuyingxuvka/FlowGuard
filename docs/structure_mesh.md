# Structure Refactor Mesh

StructureMesh is FlowGuard's helper layer for splitting large scripts and
modules into parent/child structure without losing compatibility. It lets an
agent describe the planned split as owned partitions, child module evidence,
FlowGuard model-derived target structure, public entrypoint evidence,
dependency evidence, and routine/release parity obligations.

It does not move code or parse source files. For existing large-script or
large-module splits, it requires the target child structure to be derived from a
FlowGuard functional model before ownership and compatibility evidence are
trusted.

## Use Cases

Use StructureMesh when:

- one large script or package is split into smaller child modules;
- public imports, CLI commands, API routes, data shapes, or plugin entrypoints
  move;
- state, config, caches, side effects, or durable writes are divided between
  children;
- dependency cycles might be introduced by extraction;
- routine refactor work can proceed while release-only compatibility checks
  remain deferred but visible.

StructureMesh is not the direct entry point for no-code architecture planning.
Use Code Structure Recommendation for that. StructureMesh consumes the same
structured recommendation shape when an existing large code boundary is being
split.

## Public API

The main objects are:

- `StructurePartitionItem`: one function, state item, config key, side effect,
  public surface, or behavior contract in the parent boundary.
- `ModuleStructureEvidence`: one parent, facade, or child module with owned
  functions, state, side effects, config, dependencies, facade status, and
  behavior parity evidence.
- `PublicEntrypointEvidence`: one public CLI/API/import/data-shape entrypoint
  with compatibility and facade evidence.
- `StructureMeshPlan`: the parent refactor plan that connects partitions,
  model-derived target structure, modules, public entrypoints, allowed shared
  ownership, and routine/release scope.
- `StructureMeshReport`: the structured review result.
- `review_structure_mesh(plan)`: the executable checker.

## Routine And Release Scope

Routine scope is for day-to-day refactor confidence. It can defer
release-required modules or entrypoints when `release_deferred_allowed=True`,
but the report keeps those obligations visible.

Release scope is for publish, deployment, tag, broad compatibility, or final
completion claims. Release scope blocks on stale or missing release-required
parity evidence.

## Example

```python
from flowguard import (
    CodeStructureRecommendation,
    EVIDENCE_ABSTRACT_GREEN,
    ModuleStructureEvidence,
    PublicEntrypointEvidence,
    StructureMeshPlan,
    StructurePartitionItem,
    TargetModuleRecommendation,
    review_structure_mesh,
)


target_structure = CodeStructureRecommendation(
    "legacy-reporter-target-structure",
    source_model_id="legacy-reporter-functional-model",
    parent_module_id="legacy_reporter",
    target_modules=(
        TargetModuleRecommendation(
            "cli",
            owns_function_blocks=("parse_args",),
            public_entrypoints=("python -m reporter",),
            rationale="the CLI facade remains the public entrypoint owner",
        ),
        TargetModuleRecommendation(
            "renderer",
            owns_function_blocks=("render_report",),
            owns_state=("render_cache",),
            owns_side_effects=("write_report",),
            rationale="rendering owns cache state and report writing",
        ),
    ),
    function_block_map=(("parse_args", "cli"), ("render_report", "renderer")),
    state_owner_map=(("render_cache", "renderer"),),
    side_effect_owner_map=(("write_report", "renderer"),),
    public_entrypoint_map=(("python -m reporter", "cli"),),
    facade_module_id="cli",
    validation_boundaries=("cli parity test", "render replay"),
    rationale="the functional model separates CLI intake from render effects",
)

plan = StructureMeshPlan(
    parent_module_id="legacy_reporter",
    target_structure=target_structure,
    partition_items=(
        StructurePartitionItem("parse_args", owner_module_id="cli"),
        StructurePartitionItem("render_report", owner_module_id="renderer"),
    ),
    child_modules=(
        ModuleStructureEvidence(
            "cli",
            owns_functions=("parse_args",),
            behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN,
        ),
        ModuleStructureEvidence(
            "renderer",
            owns_functions=("render_report",),
            owns_state=("render_cache",),
            owns_side_effects=("write_report",),
            behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN,
        ),
    ),
    public_entrypoints=(
        PublicEntrypointEvidence(
            "python -m reporter",
            old_path="reporter.py",
            new_path="reporter/__main__.py",
            parity_evidence_tier=EVIDENCE_ABSTRACT_GREEN,
        ),
    ),
)

report = review_structure_mesh(plan)
print(report.format_text())
```

For a ready scaffold, run:

```powershell
python -m flowguard structure-mesh-template --output .
```

## Known-Bad Hazards

Representative bad variants should fail before parent refactor confidence is
trusted:

- missing or unregistered partition owner;
- missing model-derived target structure;
- target structure not derived from a FlowGuard functional model;
- target structure missing FunctionBlock, state, side-effect, facade, or
  validation mapping;
- duplicate partition owner;
- duplicate state, side-effect, or config owner;
- public entrypoint removed;
- compatibility facade missing;
- unsafe dependency cycle;
- config/default drift;
- missing or stale behavior parity;
- insufficient evidence tier;
- missing release-required parity under release scope.
