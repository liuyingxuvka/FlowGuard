# FlowGuard shared execution rules

Short consumer-facing rules shared by the three public FlowGuard operations.
Ordinary work loads this file plus the selected domain protocol only.

## Selection and context

- Read `route_index.md` first and select exactly one subject from its positive
  and forbidden conditions. Zero matches are `no_match`; multiple matches are
  `conflict`. Keywords, declaration order, or a caller assertion do not select
  a subject.
- Pass one immutable `RouteContext` containing the task facts and coverage
  demand, project root, accepted model/revision identity, exact owner
  denominator and bindings, affected ids, claim boundary, toolchain/environment,
  private evidence root, and the current source/contract/check fingerprints.
- Lazy references are inputs, not evidence shortcuts. A skipped conditional
  reference is `not_triggered`; a required unavailable reference is `blocked`.
  Do not preload peer routes, whole model shards, or all receipt trees.

## Execution and evidence

- Classify each selected owner as exactly one of
  `execute | reuse_current | blocked | not_run` before a producer starts.
- Read-only or plan-only work has zero producer invocations and creates no
  lease, run directory, receipt, pointer, or installation projection.
- `reuse_current` requires one exact current terminal receipt in the same
  maintenance unit and route boundary with identical subject, owner, request,
  inputs, dependencies, producer, toolchain, environment, policy, obligations,
  and child receipts. It verifies and composes; it does not rerun.
- Freeze source, model, contract, check, toolchain, environment, scope, owner
  inputs, dependencies, claim boundary, and evidence root before `execute`.
  Unknown or ambiguous ownership stops before any producer; it never widens
  to run-all.
- A parent receipt cannot be relabeled as a leaf receipt. Native owner
  semantics and evidence remain separate from aggregate summaries.

## Stop and claim rules

Stop at the current owner on drift, missing/stale/foreign/malformed/duplicate
evidence, unknown owner/component, unresolved reverse binding, scope overflow,
required blocked or skipped members, missing `--reuse-only` currentness,
unconfirmed descendant cleanup, symlink-capability failure, OpenSpec drift, or
an unavailable external owner. Do not retry by changing paths, creating a new
epoch, loading another subject, or widening the operation.

`read` is read-only, `change` executes the exact affected owner closure, and
`release` verifies the declared release scope. Report evidence, failures,
blockers, skipped/not-run checks, residual risk, claim boundary, and typed next
actions. `out_of_scope` and `not_run` are never silently counted as closed
obligations.
