## Context

The existing FlowGuard routes already split model scale, test scale, structure
boundaries, code-boundary observations, and final risk evidence. They still
depend on an upstream plan/adoption layer to supply the right surfaces. If the
input plan omits the repeated failure class, if an adapter maps a stale log into
generic passing evidence, or if a report label is later overclaimed, downstream
FlowGuard helpers may pass honestly while the real workflow remains unsafe.

The new layer treats plan construction and claim promotion as explicit
FlowGuard-reviewable artifacts. It lives in the Python package as helper APIs,
not as another installed Codex subskill.

## Goals / Non-Goals

**Goals:**

- Fail or scope plans that do not declare current source evidence and in-scope
  risk surfaces.
- Require recurring or high-risk cases to carry observed failure, same-class,
  and historical holdout references when those branches are part of the claim.
- Make evidence adapters prove that raw artifact freshness, failure, stale,
  progress-only, and internal-path classifications survive mapping.
- Backpropagate post-green misses into a cause and a new failing condition.
- Prevent broad confidence claims from being built from narrower reports.
- Keep the helpers small, serializable, and standard-library only.

**Non-Goals:**

- Do not run tests, parse project logs, or inspect source files inside these
  helpers.
- Do not replace ModelMesh, TestMesh, Model-Test Alignment, Risk Evidence
  Ledger, or DevelopmentProcessFlow.
- Do not make OpenSpec a FlowGuard runtime dependency.
- Do not declare production confidence from helper success alone; claim-chain
  review still needs current lower-level evidence.

## Decisions

1. **Single helper module, multiple narrow reports.**
   Put the new checks in one `plan_intake.py` module because their shared job is
   to harden the plan/evidence/claim seam before existing FlowGuard routes are
   trusted. Keep report types separate so callers can adopt them incrementally.

2. **Evidence ids over raw parsing.**
   Project adapters own raw parsing. FlowGuard only checks structured rows:
   raw artifact ids, mapped evidence ids, expected/observed classifications,
   freshness, and known-bad rejection status.

3. **Warnings can scope confidence but blockers stop claims.**
   Explicitly scoped surfaces or lower-scope claim dependencies may keep a
   helper `ok` while reducing confidence to `scoped`. Unknown, omitted,
   stale-as-current, or known-bad-passed cases block.

4. **False-negative review is cause-specific.**
   Each post-green miss must name the previous passing claim/evidence, observed
   failure, cause, and at least one would-have-failed-if condition. Adapter
   mapping causes must also name an adapter gap.

5. **Claim scopes are typed.**
   Higher scopes cannot be inferred from string summaries. `production_confidence`
   requires current runtime replay, risk evidence, plan intake, adapter
   conformance, false-negative closure when applicable, and mutation evidence
   when mutation probes are declared.

## Risks / Trade-offs

- **Risk:** The public API grows again.
  **Mitigation:** expose one module of focused helper dataclasses and keep them
  out of the core API group.

- **Risk:** Callers may treat plan intake success as proof of runtime behavior.
  **Mitigation:** claim-chain review names `plan_valid_only` separately from
  runtime and production scopes.

- **Risk:** Adapters may not have all metadata initially.
  **Mitigation:** allow explicitly scoped findings, but block silent omission or
  stale/failing evidence mapped as current pass.

- **Risk:** The change may conflict with parallel work.
  **Mitigation:** keep edits scoped to new helper module, public exports, docs,
  tests, changelog, and version sync.
