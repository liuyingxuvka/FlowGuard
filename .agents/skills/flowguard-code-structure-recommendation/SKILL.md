---
name: flowguard-code-structure-recommendation
description: Use when a FlowGuard model should drive pre-code architecture, module split planning, function/block ownership, facade design, implementation boundaries, or code structure recommendations before editing production code.
---

# FlowGuard Code Structure Recommendation

This is a standalone FlowGuard satellite skill for turning a model into an
implementation structure plan. Use it directly when the user asks how code
should be structured from the model before making or reviewing code changes.

Return to `model-first-function-flow` when the model itself is not established,
when the route is ambiguous, or when multiple FlowGuard routes need
coordination.

## Hard Gates

- Verify the real package before claiming FlowGuard use:
  `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- Do not create a fake mini-framework or prose-only substitute.
- Derive structure from modeled FunctionBlocks, state ownership, side effects,
  and contracts.
- Do not turn structure advice into a broad refactor without validation.
- Keep proposed ownership boundaries reviewable and scoped.

## Workflow

1. Read or build the smallest fit-for-risk FlowGuard model.
2. Extract FunctionBlock ownership, state reads/writes, side effects,
   external contracts, and public entrypoints.
3. Recommend modules, facades, adapters, and test seams from that evidence.
4. Identify risky dependency directions, shared state, and compatibility
   boundaries.
5. Use `review_code_structure_recommendation(...)` where available, then use
   StructureMesh only if the actual refactor is large enough to need it.

## Owned Helpers

- `review_code_structure_recommendation(...)`
- `docs/code_structure_recommendation.md`
- `references/code_structure_recommendation_protocol.md`

## Non-Goals

- Do not govern a large existing-module refactor end to end; use
  `flowguard-structure-mesh`.
- Do not split tests or models.
- Do not replace implementation tests or conformance replay.

For detailed route rules, read
`references/code_structure_recommendation_protocol.md`.
