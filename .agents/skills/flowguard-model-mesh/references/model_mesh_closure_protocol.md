# ModelMesh Closure And Authority Protocol

Load this file only for parent whole-flow confidence, loop/retry closure,
portable-system handoff, or a multi-model authority revision.

## Closure model

Build a finite model-of-models, not an expansion of child state graphs. Record
root entry tokens, model-to-model transitions, child outputs and consumers,
required joins, normal/failure exits, terminal side-effect closures, and
out-of-scope dispositions with rationale. For retry/rejection/wait handoffs,
record repeated inputs/outputs, repair feedback, and a progress token, blocker,
ranking rule, or finite bound.

The closure model is required for a whole-flow claim: represent repeat-input tokens,
blocker tokens, repair feedback, and whether the same packet can return
without a changed token or bounded termination.

`review_mesh_closure_model(...)` blocks unknown tokens, unreachable required
outputs, unconsumed child outputs, incomplete joins, terminal states with
pending obligations, unexplained exclusions, and loops without repair/progress
or bounds. When a hierarchy declares child outputs, reattachments, or runtime
paths, broad parent confidence requires the closure report.

## Required bad cases

At minimum prove rejection of these families:

- abstract/local green used as live or parent permission;
- stale, foreign, skipped, not-run, parse-error, or progress-only evidence;
- unregistered models or ambiguous input owners;
- incompatible sibling ownership or hidden blockers/model misses;
- missing conformance or same-class regression evidence;
- oversized/thick direct evidence accepted without a split decision;
- parent items without owner and child changes without ancestor/sibling review;
- repaired children whose new receipt or interface is not consumed;
- current bug instance confused with bug-class closure;
- whole-flow terminals with unconsumed outputs, incomplete joins, or unknown tokens;
- loop-like handoffs that can repeat the same rejected packet without repair;
- partial multi-model activation, stale base head, or undeclared affected change.

## Layered proof

Parent confidence joins four explicit tables: parent coverage, child
disjointness, current child reattachment, and finite leaf boundary cells. A
leaf with a real finite code boundary proves each declared
`Input x State -> Set(Output x State)` cell, splits again, or remains
scoped/blocked. Model-Test Alignment and TestMesh own code/test evidence;
RiskLedger decides the resulting confidence.

## Authority boundary

ModelMesh supplies hierarchy and affected-sibling relations to the sole model
system authority; it creates no second registry. A multi-model change freezes
the observed base head, candidate snapshot, member and relation diff, affected
closure, fields/effects/contracts/tests, predictions, and current owner
receipts. Recompute the fixed-point diff; undeclared change, stale head,
missing evidence, or partial member activation blocks.

Build a candidate/revision pair only from one terminal current full model
parent receipt. Persist immutable snapshot, revision, decision, and activation
records before the sole pointer changes. Model identities contain model,
runner, purpose, and exact local/shared inputs; snapshot owns global revision,
while Git identity remains separate release provenance.

Completion requires a green finite closure model, current child and layered
evidence, legal joins/loops/exclusions, reviewed affected siblings, and one
atomic authority transition or an explicit scoped/blocked result.
