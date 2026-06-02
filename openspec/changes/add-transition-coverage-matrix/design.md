## Overview

Add a small bridge layer named transition coverage matrix. The bridge does not replace Explorer, Model-Test Alignment, UI Flow Structure, or TestMesh. It converts modeled transitions into explicit coverage cells, then projects those cells into the evidence systems that already enforce freshness and pass/fail status.

## Data Shape

`TransitionCoverageCell` records one behavior obligation:

- `cell_id`
- `source_state`
- `trigger`
- `target_state`
- `expected_output`
- optional `function_block`
- optional `risk_class`
- `required_test_kinds`
- optional `evidence_target_id`

`TransitionCoverageMatrix` groups cells for one model boundary and records the source route, such as ordinary model, UI model, workflow, or leaf boundary.

## Projection Rules

The primary projection is:

```text
TransitionCoverageCell -> ModelObligation
```

The generated `ModelObligation` uses:

- obligation id: `transition:<cell_id>`
- obligation type: `transition_coverage`
- external input: the trigger
- external output: expected output when present
- state reads: source state
- state writes: target state
- required test kinds: copied from the cell

Large or slow matrices can also project into TestMesh required leaf-cell ids:

```text
TransitionCoverageMatrix -> required_leaf_cell_ids
```

This keeps semantic coverage in Model-Test Alignment and evidence hierarchy in TestMesh.

## UI Integration

`UIInteractionModel.transitions` already records event, source state, target state, function block, and output. The new helper projects those rows into transition coverage cells. UI implementation validation remains responsible for real click-through or browser/manual evidence; the transition matrix gives that evidence a stable target.

## Compatibility

Existing Model-Test Alignment plans remain valid because they can still pass explicit `ModelObligation` rows. Existing TestMesh and UI models remain valid because the new projections are additive helper APIs.

## Non-Goals

- Do not make Model-Test Alignment a full TestMesh hierarchy.
- Do not infer domain-specific expected outputs when the model did not declare them.
- Do not treat generated matrix cells as passing evidence by themselves.
- Do not weaken existing leaf matrix or workflow step contract checks.

## Validation

Validation must cover:

- transition cells project to model obligations;
- missing test evidence for generated obligations blocks Model-Test Alignment;
- leaf matrix-cell evidence with matching target ids covers transition obligations without duplicate-primary false positives;
- UI transitions project into transition coverage cells;
- TestMesh can consume projected required leaf-cell ids;
- public API and template surfaces expose the new helper.
