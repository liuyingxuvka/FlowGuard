---
name: flowguard-code-structure-recommendation
description: Use when a FlowGuard model should drive pre-code architecture, module split planning, function/block ownership, facade design, implementation boundaries, or code structure recommendations before editing production code.
---

# FlowGuard Code Structure Recommendation

Standalone FlowGuard satellite skill for deriving target implementation
structure from a model before code edits. Use it for FunctionBlock-to-module
ownership, facade planning, adapter boundaries, and validation boundaries.
When fields matter, include FieldLifecycleMesh reader/writer/owner maps so code
structure has a single field owner and explicit field readers/writers.
When modules look like similar A/B/C workflows, consume Model Similarity
Consolidation maintenance groups and code obligations instead of inventing a
second shared-kernel rationale.

Return to `model-first-function-flow` when the behavior model is missing. Use
StructureMesh when refactoring existing large code or public APIs.

## First Read

- Route id: `code_structure_recommendation`.
- Core helper: `review_code_structure_recommendation()`.
- Required shape: FunctionBlock-to-module ownership, state owner map,
  field owner/reader/writer map when fields are in scope, public-entrypoint
  map, and validation boundaries.
- Similarity handoff: cite maintenance group ids, code obligation ids, shared
  kernel owner, and adapter owners when model similarity drives the split.
- Reference: `references/code_structure_recommendation_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- Do not invent modules before model responsibilities are named.
- Public facades and validation boundaries must stay explicit.

## Minimum Workflow

1. Name the source model and relevant FunctionBlocks.
2. Map state, fields, side effects, public entrypoints, and validation boundaries.
3. Recommend target modules and facades.
4. Mark refactor parity or StructureMesh needs before implementation.

## Snapshot

Show a code structure diagram with FunctionBlock-to-module ownership, state
owners, facade boundary, and validation boundaries.
When drawing the snapshot, edges mean owns, calls, adapts, exposes, or validates.

## Non-Goals

- Do not perform existing-code refactors; route those to StructureMesh.
- Do not replace Model-Test Alignment or runtime conformance evidence.
