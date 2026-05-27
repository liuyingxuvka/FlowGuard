## Context

The prior structure simplification work already landed the concrete source
changes for two visible candidates:

- table-driven file-template command registration in `flowguard.__main__`
- derived package export declaration in `flowguard.__init__`

The real Git checkout no longer contains the duplicate
`.flowguard/flowguard_closure_contract/flowguard_closure_contract` artifact,
but the local shadow workspace can still carry that stale duplicate after
partial syncs. The maintenance path needs to separate those two facts:
completed source reductions should leave the active candidate queue, while
shadow cleanup remains a bounded local sync step.

## Route

Use OpenSpec to define the release boundary, then use FlowGuard
ArchitectureReduction, StructureMesh, TestMesh, and DevelopmentProcessFlow
checks to prove that:

1. active candidates match current source state;
2. completed candidates do not remain ready work;
3. shadow cleanup preserves peer work and is not claimed as runtime behavior
   proof;
4. release evidence waits for final exits and captured artifacts.

## Non-Goals

- No broad module split for large modules such as `templates.py` or
  `ui_structure.py` in this pass.
- No public API or CLI behavior change.
- No deletion of peer-agent source work or unrelated local modifications.
