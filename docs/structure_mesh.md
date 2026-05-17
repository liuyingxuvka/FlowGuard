# Structure Refactor Mesh

StructureMesh is FlowGuard's helper layer for splitting large scripts and
modules into parent/child structure without losing compatibility. It lets an
agent describe the planned split as owned partitions, child module evidence,
public entrypoint evidence, dependency evidence, and routine/release parity
obligations.

It does not move code or infer architecture by itself. A project adapter,
agent, or maintainer collects source inventory and passes structured evidence
into `review_structure_mesh(...)`.

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
  modules, public entrypoints, allowed shared ownership, and routine/release
  scope.
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
    EVIDENCE_ABSTRACT_GREEN,
    ModuleStructureEvidence,
    PublicEntrypointEvidence,
    StructureMeshPlan,
    StructurePartitionItem,
    review_structure_mesh,
)


plan = StructureMeshPlan(
    parent_module_id="legacy_reporter",
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
- duplicate partition owner;
- duplicate state, side-effect, or config owner;
- public entrypoint removed;
- compatibility facade missing;
- unsafe dependency cycle;
- config/default drift;
- missing or stale behavior parity;
- insufficient evidence tier;
- missing release-required parity under release scope.
