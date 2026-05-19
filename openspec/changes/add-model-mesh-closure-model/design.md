## Context

ModelMesh currently reviews the shape and evidence quality of parent/child model
hierarchies. It can block missing target split derivation, stale child evidence,
child reattachment drift, ownership conflicts, and affected sibling assumptions.
Those checks answer "is the model map partitioned and reattached?" They do not
answer "does the model network close from parent entry to normal, failure, or
explicitly out-of-scope exits?"

The closure gap is itself a FlowGuard-shaped problem: child model outputs are
inputs to the mesh, pending handoffs are state, consumers and terminal
dispositions are transitions, and final confidence depends on invariants over
remaining obligations. The design therefore adds a small executable
mesh-closure meta-model rather than a prose-only checklist.

## Goals / Non-Goals

**Goals:**

- Represent model-to-model handoffs as finite, inspectable FlowGuard-style
  closure obligations.
- Prove that declared root entries can close through child output consumption,
  join completion, terminal disposition, or explicit out-of-scope disposition.
- Keep parent confidence blocked when any child output or required join remains
  unconsumed.
- Integrate closure review into ModelMesh green decisions without expanding
  child state graphs.
- Add known-bad hazard tests so a happy-path closure pass is not enough.

**Non-Goals:**

- Do not inline every child route into the parent mesh.
- Do not replace existing child model checks, loop checks, conformance replay,
  or Model-Miss Review.
- Do not introduce automatic source parsing, graph visualization dependencies,
  or non-standard-library runtime dependencies.
- Do not require ordinary single-model FlowGuard usage to create a mesh closure
  model.

## Decisions

1. **Model closure as obligations and transitions.**
   Add dataclasses for closure inputs, transitions, obligations, terminal
   dispositions, and join requirements. A closure run starts from root entries
   and processes child outputs or terminal events into a state containing
   pending obligations and completed joins.

   Alternative considered: add only imperative checks to
   `review_hierarchical_mesh(...)`. That would catch some missing consumers but
   would make counterexample traces and known-bad hazards weaker than the rest
   of FlowGuard.

2. **Keep child models as contract nodes.**
   The closure model consumes child contract summaries: model id, accepted
   inputs, emitted outputs, evidence id, and ownership metadata already carried
   by `ChildModelEvidence` and `ChildReattachmentContract`. It does not inspect
   child internal states.

   Alternative considered: require the parent mesh to traverse child reachable
   states directly. That defeats ModelMesh's state-space reduction goal and
   duplicates child model responsibility.

3. **Require closure only when a parent boundary declares it.**
   `HierarchyPartitionMap` gains an optional closure model field. Existing
   callers remain constructible. When a closure model is present, green parent
   confidence requires the closure review to pass. When a change claims whole
   parent workflow confidence, docs and skills instruct agents to declare the
   closure model instead of treating it as optional.

   Alternative considered: require closure for every ModelMesh review
   immediately. That risks breaking existing partition-only examples and makes
   migration harder.

4. **Use explicit closure decisions.**
   Closure findings map to decisions such as `mesh_closure_required`,
   `unconsumed_child_output`, `open_branch_without_exit`,
   `missing_join_point`, `unreachable_normal_exit`, `terminal_leak`, and
   `loop_progress_required`. `review_hierarchical_mesh(...)` surfaces closure
   failures before returning `mesh_green_can_continue`.

   Alternative considered: collapse closure failures into the existing generic
   `mesh_review_blocked`. That would hide the exact path gap the feature is
   meant to expose.

5. **Treat out-of-scope as a terminal disposition with a reason.**
   A child output can close as out-of-scope only when the closure model records
   an explicit rationale. Empty or missing rationales are blockers.

   Alternative considered: allow any unconsumed output to be marked skipped.
   That would recreate the current overclaim risk in a different field.

6. **Model progress-sensitive loops as visible gaps.**
   The closure model can mark a transition as a loop or retry. A loop that is
   not bounded, ranked, or backed by a progress rule is not green closure. This
   aligns with existing loop/stuck guidance without making closure review a full
   liveness prover.

   Alternative considered: ignore loops at the mesh layer and rely entirely on
   child loop checks. That misses parent/child handoff loops such as "parent
   waits for child output that is never consumed."

## Risks / Trade-offs

- [Risk] The closure model adds ceremony for small meshes. -> Mitigation: make
  the field optional at construction and require it by docs/skills when a parent
  claims whole-flow confidence.
- [Risk] Closure review becomes a second giant graph. -> Mitigation: only model
  child boundary inputs/outputs, consumers, joins, and terminal dispositions.
- [Risk] Agents use out-of-scope to hide gaps. -> Mitigation: require explicit
  rationale and test missing-rationale hazards.
- [Risk] Closure passes while child evidence is stale. -> Mitigation: keep
  existing evidence freshness and reattachment checks; closure is an additional
  gate, not a replacement.
- [Risk] Sync across shadow and git workspaces drifts. -> Mitigation: after
  implementation, mirror the complete touched source/docs/tests/OpenSpec files
  into the git checkout, reinstall editable package from the git checkout, and
  verify imports from both workspaces.

## Migration Plan

1. Add closure model dataclasses, report formatting, and review helper in the
   existing ModelMesh module.
2. Add focused tests for green closure and known-bad closure hazards.
3. Wire optional closure review into `review_hierarchical_mesh(...)`.
4. Update examples, public exports, docs, skills, and release notes.
5. Run focused and broader regression suites.
6. Mirror touched files into the git checkout without overwriting unrelated
   dirty files, refresh the editable install, and verify both local workspaces
   import the same package version and API.

## Open Questions

- None for the initial implementation. Future work can add visualization or
  automatic closure model derivation from real model files.
