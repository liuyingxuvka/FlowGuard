## Context

FlowGuard now has three adjacent governance surfaces:

- hierarchical model mesh for splitting FlowGuard models;
- TestMesh for splitting test evidence;
- the new StructureMesh for splitting software structure.

StructureMesh should be useful during a facade-first refactor where a large
script remains as a compatibility entrypoint while behavior moves into smaller
modules. It should not parse source code or perform the refactor itself. It
reviews a structured plan and evidence summary created by an adapter or agent.

## Goals / Non-Goals

**Goals:**

- Keep old public entrypoints visible until compatibility is intentionally
  retired.
- Bind functions, modules, state writes, configuration reads, side effects, and
  behavior contracts to explicit owners.
- Catch duplicate state or side-effect ownership across child modules.
- Expose dependency cycles and configuration/default drift.
- Require behavior parity evidence before a split can support parent
  confidence.
- Distinguish routine refactor confidence from release confidence.

**Non-Goals:**

- Do not rewrite source code automatically.
- Do not build an import graph parser.
- Do not replace unit tests, conformance replay, or manual code review.
- Do not force every small refactor into StructureMesh.
- Do not merge StructureMesh into TestMesh or hierarchical model mesh.

## Decisions

1. **StructureMesh is a helper layer, not a new modeling language.**
   It consumes dataclass summaries and returns structured findings. This keeps
   it consistent with `review_hierarchical_mesh(...)` and
   `review_test_mesh(...)`.

2. **Facade retention is explicit.**
   `ModuleStructureEvidence` records whether a child or parent module preserves
   compatibility facade behavior. `PublicEntrypointEvidence` records old/new
   entrypoint compatibility and parity evidence.

3. **Ownership is partition based.**
   `StructurePartitionItem` names functions, modules, state fields, config
   reads, side effects, or behavior contracts and binds each to `child`,
   `parent`, `read_only`, or `shared_kernel` ownership.

4. **Release scope is stricter than routine scope.**
   Routine scope may carry release obligations visibly. Release scope blocks if
   release-required parity or facade evidence is missing.

5. **Known-bad hazards must fail.**
   Tests and the rollout model must prove StructureMesh rejects missing owners,
   unregistered owners, duplicate state/side-effect ownership, removed
   entrypoints, facade removal, dependency cycles, config drift, missing parity,
   and release overclaims.

## Risks / Trade-offs

- **Risk: agents treat StructureMesh as proof of behavior preservation.** →
  Mitigation: docs and findings state that parity evidence comes from tests,
  replay, logs, or review; StructureMesh only reviews the evidence contract.
- **Risk: too much ceremony for small refactors.** → Mitigation: Skill trigger
  is limited to large scripts, broad modules, facade-first refactors, and
  ownership/entrypoint/side-effect changes.
- **Risk: overlap with TestMesh.** → Mitigation: StructureMesh reviews code
  ownership and public behavior contracts; TestMesh reviews validation evidence
  execution.
- **Risk: overlap with model mesh.** → Mitigation: model mesh reviews
  FlowGuard model boundaries; StructureMesh reviews production software
  structure boundaries.
