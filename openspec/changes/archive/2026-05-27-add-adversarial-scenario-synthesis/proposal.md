## Why

FlowGuard can already review deterministic scenarios, generated matrices, helper
packs, conformance replay, model-test alignment, and risk evidence. The missing
step is a first-class way to use that existing chain proactively: generate
high-risk challenge routes before a runtime bug is observed.

## What Changes

- Extend the existing scenario-matrix path with adversarial challenge patterns
  for retries, duplicate delivery, stale state, terminal replay, and partial
  failure style workflows.
- Add model-derived challenge synthesis from actual FlowGuard Explorer reports,
  including invariant violations, dead branches, exceptions, repeated labels,
  repeated blocks, state revisits, and trace risk signals.
- Keep generated challenge scenarios as ordinary `Scenario` objects so they
  continue through Scenario Sandbox, conformance replay, Model-Test Alignment,
  and Risk Evidence Ledger without a parallel workflow.
- Preserve the current safety rule that generated scenarios default to
  `needs_human_review` until a domain oracle or explicit expectation is
  supplied.
- Add risk-focused notes and tags so reports can explain why a generated route
  is dangerous instead of merely listing an input sequence.
- Update the retry, deduplication, cache, and side-effect packs to opt into the
  richer challenge matrix while keeping their public shape small.
- Document the proactive bug-discovery workflow as an extension of existing
  FlowGuard mechanisms, not a replacement for replay, tests, or evidence
  alignment.

## Capabilities

### New Capabilities

- `adversarial-scenario-synthesis`: FlowGuard can derive bounded high-risk
  challenge scenarios from existing scenario-matrix inputs and helper packs,
  while preserving existing Scenario Sandbox status and evidence semantics.

### Modified Capabilities

- None.

## Impact

- Affected code: `flowguard/scenario_matrix.py`, `flowguard/packs/*.py`,
  `flowguard/runner.py`, and `flowguard/plan.py`.
- Affected tests: scenario-matrix and pack tests focused on generated route
  shape, tags, notes, sequence limits, and default review status.
- Affected docs: productized helper and scenario sandbox guidance.
- No new runtime dependencies.
- No new standalone testing workflow.
