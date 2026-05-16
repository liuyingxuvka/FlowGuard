## Context

FlowGuard's core model remains `State + FunctionBlock + Invariant + Explorer`.
The current model mesh protocol already treats child models as evidence
contracts instead of inlining every child state graph. Large real workflows now
need that mesh layer to also review hierarchical partition quality: whether
parent coverage is complete, whether sibling models are sufficiently
independent, and whether a single oversized model should be split before it
becomes too expensive to inspect.

## Goals / Non-Goals

**Goals:**

- Support multi-level parent/child model hierarchies, not just a root with one
  child layer.
- Let each parent boundary declare a partition map that assigns coverage items
  to children or the parent itself.
- Let a mesh review each sibling set for coverage gaps, excessive overlap,
  ownership conflicts, stale evidence, hidden skipped checks, and large-model
  split decisions.
- Apply the same review to new models and legacy models discovered in existing
  projects.
- Keep the first implementation in helper/reporting APIs and documentation,
  without changing core `FunctionBlock`, `Workflow`, or `Explorer` behavior.

**Non-Goals:**

- Do not automatically rewrite or split existing model files.
- Do not merge child state graphs into one parent graph.
- Do not replace budgeted graph execution; large models can still use the
  budgeted runner when a split is not yet justified.
- Do not add third-party dependencies.

## Decisions

1. Add hierarchy governance as a helper/reporting layer.
   - Rationale: existing users depend on stable core model semantics.
   - Alternative considered: make `Explorer` understand nested workflows. That
     would mix state-space exploration with architecture governance and risk
     breaking existing models.

2. Represent hierarchy as partition metadata plus evidence contracts.
   - Rationale: a parent should see a child's risk boundary, owned coverage,
     exposed outputs, freshness rule, skipped checks, and evidence tier, not the
     child's full state graph.
   - Alternative considered: use child reachable states directly. That defeats
     the state-space reduction goal.

3. Run mesh review at every parent boundary.
   - Rationale: any child can become a parent when its internal model gets too
     large. A single global mesh cannot reason cleanly about every nested
     sibling set without becoming a giant graph.
   - Alternative considered: only run one top-level mesh. That misses overlap
     and coverage gaps inside large child domains.

4. Trigger mesh review from both quantity and scale.
   - Rationale: three or more models create coordination risk, while one large
     model creates split risk even before sibling models exist.
   - Suggested defaults: model count >= 3, estimated or observed state count
     above 10,000, a budgeted run that remains incomplete, or a model that
     contains several unrelated functional areas.

5. Treat legacy models as compatibility contracts first.
   - Rationale: existing model scripts are assets. The safe first step is to
     register and classify them before deciding whether to split, merge, or
     wrap them as child evidence.

## Risks / Trade-offs

- [Risk] Partition metadata can drift from real model code. -> Mitigation:
  include freshness rules, fingerprint inputs where practical, and keep skipped
  or stale evidence visible in the mesh report.
- [Risk] Overlap scoring can be too rigid. -> Mitigation: distinguish
  `read_only`, `shared_kernel`, parent-owned, and child-owned coverage instead
  of treating all overlap as a failure.
- [Risk] A size threshold can become cargo-culted. -> Mitigation: make the
  default threshold configurable and allow the mesh decision to keep a large
  model when it is structurally cohesive.
- [Risk] Legacy migration can become too invasive. -> Mitigation: first
  provide classification and compatibility-contract review; do not auto-edit
  legacy model code.

## Migration Plan

1. Add helper dataclasses and review functions for partition maps, child model
   evidence, legacy classification, and mesh review decisions.
2. Add examples for a nested hierarchy and a legacy large-model review.
3. Add tests for coverage gaps, sibling overlap, ownership conflicts, stale
   evidence, large-model triggers, and legacy compatibility decisions.
4. Update docs, README, changelog, and API surface notes.
5. Bump the package version, run validation, sync editable install and shadow
   workspace, tag, push, and publish a GitHub release.
