# ModelMesh Handoff

This kernel-side file is a compact handoff stub. The detailed protocol is
owned by the direct satellite skill `flowguard-model-mesh`.

Load:
`.agents/skills/flowguard-model-mesh/references/model_mesh_protocol.md`

Use this route when the affected topology crosses model boundaries, a model is
oversized, child evidence is stale, parent/child partitioning changes, target
split derivation is needed, or affected-sibling/whole-flow review controls the
confidence claim. Several unrelated models do not trigger ModelMesh by count.

Keep the hard gates: inventory child evidence ids, prove freshness, avoid
expanding every child state graph, reattach repaired children to the parent,
and treat background progress as liveness until final artifacts and exit status
exist.
