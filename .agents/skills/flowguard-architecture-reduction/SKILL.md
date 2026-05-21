---
name: flowguard-architecture-reduction
description: Use when a FlowGuard model should drive behavior-preserving code architecture simplification, including shrinking overgrown flows, merging duplicate handlers/modules, collapsing pass-through adapters, removing dead branches or irrelevant state, and producing a StructureMesh-ready contraction plan before editing production code.
---

# FlowGuard Architecture Reduction

This is a standalone FlowGuard satellite skill for model-backed code
contraction. Use it when the goal is not merely to simplify a model, but to ask
whether a complex implementation can be made smaller while preserving declared
observable behavior.

Plain rule: reduce code only after the model proves or bounds what behavior is
unchanged, then hand the target structure to Code Structure Recommendation and
StructureMesh. This skill reviews and recommends; it does not directly rewrite
production code.

Return to `model-first-function-flow` when the model itself is unclear. Use
`flowguard-code-structure-recommendation` when the task only needs a target
module plan before code exists. Use `flowguard-structure-mesh` when production
code refactoring is already underway and parity evidence is the main risk.

## Hard Gates

- Verify the real package before claiming FlowGuard use:
  `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- Do not create a fake mini-framework or prose-only substitute.
- Declare the observable architecture contract first: public entrypoints,
  observable outputs, observable state, observable side effects, validation
  boundaries, and rationale.
- Ground the review in existing model ownership before recommending a new
  contraction. Use `flowguard-existing-model-preflight` when ownership may
  matter.
- Every contraction candidate must have a proof status. Do not treat
  `property_only_safe`, `needs_conformance_replay`, `risky_keep`, or
  `blocked_by_missing_evidence` as safe code deletion.
- Any candidate touching public entrypoints must route through StructureMesh or
  equivalent public-entrypoint parity evidence.
- This skill must not edit production code directly. Actual refactors need
  StructureMesh, DevelopmentProcessFlow, tests, and conformance evidence as
  appropriate.

## When To Use

Use this route when a codebase or model shows complexity-growth signals:

- repeated handlers, adapters, modules, phases, or validation layers around the
  same behavior;
- proposed new module/model boundaries overlap existing responsibility;
- a refactor goal is to shrink code rather than split it further;
- model/test/code evidence shows duplicate obligations or duplicate coverage;
- a UI flow repeats screens, controls, state paths, or information displays
  and the desired result is a smaller implemented UI structure;
- a done/release claim follows a long staged task where the implementation may
  have accumulated workaround branches.

Skip it for greenfield module planning with no existing code, tiny edits,
formatting-only work, and model-only cleanup that will not affect code.

## Workflow

1. Run existing-model grounding when relevant:
   - current model ids;
   - FunctionBlock owners;
   - state owners;
   - side-effect owners;
   - public-entrypoint owners;
   - duplicate-boundary risks.
2. Define the observable architecture contract:
   - what public behavior must stay unchanged;
   - which state and side effects are externally meaningful;
   - which tests, replay, conformance, or manual evidence boundaries matter.
3. Map model elements to code nodes:
   - FunctionBlock -> function, class, handler, command, component, or module;
   - state field -> dataclass field, storage key, UI state, config, or record;
   - side effect -> file write, API call, DB write, subprocess, UI effect;
   - public entrypoint -> CLI, API, exported function, UI route, or command.
4. Identify contraction candidates:
   - `merge_handlers`;
   - `merge_modules`;
   - `collapse_adapter`;
   - `remove_branch`;
   - `remove_state_field`;
   - `merge_state_phase`;
   - `remove_duplicate_validation`;
   - `keep_public_facade`;
   - `manual_review`.
5. Classify proof status for each candidate:
   - `safe_by_equivalence`: same observable behavior is proven or bounded;
   - `safe_by_public_facade`: internals can shrink while facade stays;
   - `property_only_safe`: only selected invariants are preserved;
   - `needs_conformance_replay`: real-code replay is still required;
   - `risky_keep`: looks duplicate but should remain;
   - `blocked_by_missing_evidence`: do not contract yet.
6. Use `review_architecture_reduction(...)` when available.
7. Produce a target architecture summary for Code Structure Recommendation or
   StructureMesh: merge, collapse, remove, keep facade, or manual review.
8. Before code edits, hand off:
   - to Code Structure Recommendation for target module ownership;
   - to StructureMesh for existing code refactors and public entrypoint parity;
   - to DevelopmentProcessFlow for staged edit/revalidation ordering;
   - to Model-Test Alignment or conformance replay when proof status requires
     stronger evidence.

## User-Facing Snapshot

For non-trivial use, show a compact Mermaid architecture-reduction diagram. It
should show:

- current code boundary;
- model boundary;
- observable contract;
- contraction candidates;
- proof status;
- target code structure;
- required next route.

Edges mean maps-to, preserves, contracts, requires-parity, or blocks. The
diagram explains the review; it is not validation evidence.

## Owned Helpers

- `ObservableArchitectureContract`
- `ArchitectureReductionCandidate`
- `ArchitectureReductionTrigger`
- `TargetArchitectureAction`
- `ArchitectureReductionPlan`
- `ArchitectureReductionFinding`
- `ArchitectureReductionReport`
- `review_architecture_reduction(...)`

## Non-Goals

- Do not perform broad source-code semantic proof.
- Do not replace StructureMesh, Code Structure Recommendation,
  DevelopmentProcessFlow, Model-Test Alignment, or conformance replay.
- Do not delete compatibility facades just because internals can shrink.
- Do not hide risky candidates or skipped checks.
