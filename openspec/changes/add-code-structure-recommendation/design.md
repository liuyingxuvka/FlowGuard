## Context

FlowGuard currently has a compact Skill Kernel and three sibling mesh routes:
ModelMesh for model boundaries, TestMesh for validation boundaries, and
StructureMesh for existing code structure boundaries. StructureMesh is already
able to review partition ownership, duplicate state and side-effect owners,
facades, public entrypoints, dependency cycles, config drift, and parity
evidence.

The missing layer is the target structure recommendation. For a from-scratch
feature, the user may want a recommended code architecture before coding. For
an existing large script, StructureMesh must not merely accept an arbitrary
split; it should require the target child structure to be derived from a
FlowGuard functional model.

## Goals / Non-Goals

**Goals:**

- Add a parallel, optional code structure recommendation route for direct
  architecture asks and ordinary model-first work that needs implementation
  structure guidance.
- Keep ordinary core modeling lightweight; do not force every model run through
  a code-structure checklist.
- Make StructureMesh internally require model-derived target structure evidence
  when reviewing existing large-script or large-module decomposition.
- Represent the recommendation as structured evidence: source model, target
  modules, function-block mapping, state-owner mapping, side-effect-owner
  mapping, facade plan, validation plan, and rationale.
- Keep helper APIs small and consistent with existing mesh helpers.

**Non-Goals:**

- Do not make StructureMesh a no-code architecture planning entry point.
- Do not make code structure recommendation write production code.
- Do not auto-parse or refactor source files in FlowGuard core.
- Do not mechanically force one FunctionBlock into one file.
- Do not add external dependencies.

## Decisions

1. **Use a parallel route for direct recommendations.**
   `code_structure_recommendation` becomes a sibling route in the Skill Kernel.
   It is available when a user asks for an architecture recommendation or when
   an agent judges that the functional model should be translated into code
   structure before implementation. Ordinary `core_modeling` remains the
   default model-first path.

2. **Keep StructureMesh scoped to existing code splits.**
   StructureMesh still applies when an existing large script, module, package,
   command surface, or API surface is being split. Its upgrade is narrower:
   before reviewing the split, the plan must include target child structure
   evidence derived from a FlowGuard functional model.

3. **Represent target structure as evidence, not a new modeling language.**
   Add `TargetModuleRecommendation` and `CodeStructureRecommendation` objects.
   These summarize model-derived structure decisions and are consumed by
   `review_structure_mesh(...)`. The recommendation is not an executable
   workflow by itself; the FlowGuard functional model remains the executable
   design artifact.

4. **Block missing or weak target derivation in StructureMesh.**
   StructureMesh should emit blockers when an existing split lacks source model
   evidence, target modules, FunctionBlock-to-module mapping, state ownership,
   side-effect ownership, facade plan for public entrypoints, validation plan,
   or non-empty rationale.

5. **Add known-bad hazards.**
   Tests should cover arbitrary splits with no model source, monolithic target
   modules despite multiple model blocks, duplicate target owners, missing
   side-effect adapters, missing facade plans, and over-fragmented mechanical
   one-block-per-file splits where no rationale is present.

## Risks / Trade-offs

- [Risk] The new route could feel mandatory for every model-first task. ->
  Mitigation: Skill wording says it is a parallel route, and core modeling only
  references it as an option when implementation structure is actually needed.
- [Risk] StructureMesh could accidentally become a no-code architecture tool. ->
  Mitigation: StructureMesh wording stays tied to existing large scripts,
  modules, packages, commands, or API surfaces being split.
- [Risk] Recommendations could be treated as behavior proof. -> Mitigation:
  recommendations are structure evidence only; behavior proof still comes from
  model checks, parity tests, replay, or conformance evidence.
- [Risk] Agents may over-split by mapping every block to a file. -> Mitigation:
  tests and protocol wording require rationale and permit grouping related
  blocks under one module owner.
