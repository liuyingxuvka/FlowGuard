## Context

FlowGuard already has the right model families for this problem:
Hierarchical ModelMesh owns parent/child structure and reattachment,
MeshClosure owns model-to-model handoff closure, TransitionCoverageMatrix
projects finite state transitions into Model-Test Alignment/TestMesh, TestMesh
owns child validation evidence, and Model-Miss Review owns false-negative
backpropagation.

The weakness is the default green boundary. A parent mesh can still look green
when children are locally green but the parent has not forced all child
handoffs into closure transitions, retry/rejection loops have only prose
progress rules, and the generated test obligations are not automatically tied
to transition cells. The repair must strengthen those existing paths rather
than introduce a new route, scanner, or compatibility layer.

## Goals / Non-Goals

**Goals:**

- Make parent/child ModelMesh green confidence depend on closed handoffs when
  child outputs or reattachment contracts make a whole-flow claim meaningful.
- Represent retry/rejection liveness inside `MeshClosureTransition` using
  structured tokens, not keyword scans.
- Generate transition coverage cells directly from closure transitions so
  Model-Test Alignment and TestMesh receive required obligations by default.
- Require rejection/retry-like handoffs to carry failure, negative, and replay
  coverage in addition to ordinary happy-path coverage.
- Backpropagate post-green stuck/retry/rejection misses into the same ModelMesh,
  TransitionCoverageMatrix, Model-Test Alignment, and TestMesh evidence chain.

**Non-Goals:**

- No new FlowGuard route, no log keyword scanner, and no parallel agentic
  workflow framework.
- No compatibility shim that lets old or partial model shapes claim full green.
- No attempt to prove semantic LLM correctness. Synthetic/fake-agent packets
  prove control-flow and contract coverage only unless real semantic evidence
  is supplied through the existing evidence routes.

## Decisions

1. **Harden the existing closure transition type instead of adding a new route.**

   `MeshClosureTransition` will gain optional structured fields:
   `repeat_input_tokens`, `progress_tokens`, `repair_feedback_tokens`, and
   `blocker_tokens`. The existing `loop`, `progress_rule`, and
   `max_iterations` fields remain valid, but repeated-input loops must also
   prove repair feedback and a blocking/progress disposition.

   Alternative considered: add an `AgenticLiveness` route. Rejected because the
   user explicitly wants ModelMesh itself to be strong enough by default.

2. **Require closure for meaningful parent/child handoffs, not for empty toy
   maps.**

   `review_hierarchical_mesh(...)` will block parent confidence when the parent
   has child outputs or reattachment contracts but no closure model. This keeps
   simple inventory-only maps usable while preventing child-local green from
   supporting a broad parent flow claim.

   Alternative considered: require a closure model for every `HierarchyPartitionMap`.
   Rejected because some existing reviews are intentionally partition-only and
   do not claim whole-flow handoff closure.

3. **Project closure transitions into TransitionCoverageMatrix cells.**

   A new helper in `transition_coverage.py` will create one
   `TransitionCoverageCell` per closure transition. Normal transitions require
   the existing happy-path default. Loop/retry/rejection transitions require
   happy, failure, negative, and replay test kinds by default.

   Alternative considered: teach TestMesh to read ModelMesh directly. Rejected
   because Model-Test Alignment already owns semantic obligation binding, while
   TestMesh only owns evidence hierarchy and freshness.

4. **Keep code/test binding in Model-Test Alignment.**

   The generated transition matrix will preserve code contract id and runtime
   node id when provided by the closure transition. Model-Test Alignment still
   decides whether tests bind the same model obligation and owner code contract.

5. **Treat post-green no-delta loops as model misses.**

   Model-Miss Review documentation and templates will require repeated rejected
   packets, same-input retries, missing repair feedback, and stuck child
   reattachment to be represented as same-class model/test obligations when
   they appear after a previous FlowGuard pass.

## Risks / Trade-offs

- **Risk: existing examples become stricter.** → Update tests and docs so
  examples claiming parent confidence include closure models, while pure
  partition-only examples stay scoped.
- **Risk: string progress rules remain too vague.** → Keep `progress_rule` for
  compatibility but add structured token checks for repeated-input loops.
- **Risk: generated transition cells overclaim fake-agent semantic evidence.**
  → Required test kinds and docs will label these as contract/control-flow
  obligations; semantic proof still needs existing real evidence rows.
- **Risk: full regression is slow.** → Run focused tests first and use
  documented background log artifacts for heavyweight checks, then inspect final
  exit/result files before claiming completion.
