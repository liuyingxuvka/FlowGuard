## 1. FlowGuard Preflight

- [x] 1.1 Add or update a FlowGuard self-model for model boundary diff propagation before production code changes.
- [x] 1.2 Represent child boundary diffs, parent reconciliation, sibling intersection, bug-class holdout handling, and large-check routing in the self-model.
- [x] 1.3 Run scenario review for the self-model and keep non-applicable conformance, loop/stuck, progress/fairness, and contract/refinement checks visible as skipped in adoption evidence.
- [x] 1.4 Record adoption evidence, skipped checks, counterexamples, and next actions in the local FlowGuard adoption log.

## 2. Boundary Diff Propagation

- [x] 2.1 Add boundary diff structures for old/new ownership of functions, state fields, side effects, invariants, contracts, risk classes, and validation evidence.
- [x] 2.2 Implement parent propagation review that marks affected partition, freshness, coverage, and release-readiness claims stale until reconciled.
- [x] 2.3 Implement sibling intersection review for shared reads, duplicate ownership, handoff drift, shared-kernel ownership, and non-intersecting sibling freshness.
- [x] 2.4 Add structured findings and reports for coverage gaps, responsibility moves, stale evidence, ownership conflicts, and accepted reconciliations.
- [x] 2.5 Export any new helper APIs and keep existing `FunctionBlock`, `Workflow`, and `Explorer` behavior compatible.

## 3. Bug-Class Responsibility And Holdout Evidence

- [x] 3.1 Update model-miss guidance or helpers so known bug instances are recorded as holdout or validation evidence only.
- [x] 3.2 Add explicit bug-class responsibility boundary fields for parent, child, sibling, shared-kernel, and escalated ownership decisions.
- [x] 3.3 Make point-fix-only modeling fail when the observed bug is represented without a same-class generalized responsibility boundary.
- [x] 3.4 Add precision review for bug classes assigned to the wrong model boundary or crossing sibling boundaries without handoff, escalation, or shared-kernel ownership.

## 4. Large And Slow Propagation Checks

- [x] 4.1 Route propagated parent or sibling checks that exceed model count, state count, or runtime thresholds through ModelMesh split review.
- [x] 4.2 Use Budgeted model-group execution when propagated checks are too large for one complete reachable-graph run.
- [x] 4.3 Use LongCheck evidence conventions for background or slow propagated checks, including log paths, exit codes, update times, and proof-reuse status.
- [x] 4.4 Ensure incomplete budgeted shards, missing required labels, stale proof reuse, or missing LongCheck exit evidence cannot support green release-readiness claims.

## 5. Tests, Documentation, And Release

- [x] 5.1 Add focused tests for boundary diff capture, parent reconciliation, sibling intersections, shared reads, duplicate ownership, stale evidence, and non-intersecting siblings.
- [x] 5.2 Add focused tests for known-bug holdout separation, point-fix-only rejection, bug-class responsibility mismatch, and cross-sibling escalation.
- [x] 5.3 Add focused tests for ModelMesh, Budgeted model-group, and LongCheck handling of large or slow propagated checks.
- [x] 5.4 Update examples and documentation for boundary diff propagation, bug-class responsibility boundaries, holdout evidence, and heavy-check routing.
- [x] 5.5 Update changelog and version metadata, sync installed skill and shadow workspace when implementation work is ready for release, and run final validation.
