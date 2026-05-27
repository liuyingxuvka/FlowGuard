## Why

FlowGuard now has ModelMesh, TestMesh, StructureMesh, Model-Test Alignment,
Risk Evidence Ledger, recurring miss gates, and automatic split review. Those
helpers are hard validators over structured inputs. The recurring failure mode
is earlier: an agent can under-declare the plan, omit historical misses, drop
runtime/log/test evidence during adapter mapping, or upgrade a narrow passing
report into a broad confidence claim.

This change hardens FlowGuard at the plan-intake and claim-boundary layer. It
does not add another broad satellite skill. It adds small public helpers that
make missing input surfaces, evidence-adapter loss, known false negatives, weak
mutation evidence, and unsupported claim escalation visible before completion
or release confidence is claimed.

## What Changes

- Add a plan-intake completeness review for source evidence, user-visible risk
  surfaces, omitted in-scope branches, happy-path-only plans, and recurring or
  high-risk historical cases.
- Add evidence-adapter conformance review so raw runtime, log, test, code, and
  history artifacts cannot silently become current passing evidence after status
  or classification loss.
- Add false-negative backpropagation review so real misses after a green model
  create a structured cause, previous-pass link, observed failure link, and
  would-have-failed-if condition before closure.
- Add plan mutation review so known-bad missing branches or weakened invariants
  must fail the plan/model/check path before confidence is raised.
- Add typed FlowGuard claim-chain review so `plan_valid_only`, `model_valid`,
  `test_alignment_valid`, `runtime_replay_valid`, and `production_confidence`
  cannot be conflated.
- Update docs, public exports, tests, version notes, and installed local package
  sync for the new helper APIs.

## Capabilities

### New Capabilities

- `plan-intake-completeness`: Reviews whether a FlowGuard-backed plan declares
  the source/evidence universe and all in-scope risk surfaces before modeling
  or completion claims.
- `evidence-adapter-conformance`: Reviews whether project-specific evidence
  adapters preserve raw artifact identity, freshness, failure/progress/stale
  classifications, and known-bad fixture rejection.
- `false-negative-backpropagation`: Reviews whether a post-green miss has been
  traced back into model input, invariant, oracle, adapter, stale evidence, or
  claim-scope causes.
- `plan-mutation-review`: Reviews whether known-bad plan mutations fail instead
  of being accepted by a too-wide plan/model/check path.
- `flowguard-claim-chain`: Reviews whether broader FlowGuard confidence claims
  are supported by current lower-scope reports and evidence.

### Modified Capabilities

- Model-first kernel guidance should route repeated issues and completion
  claims through these helpers before treating existing satellite reports as
  sufficient.
- Risk Evidence Ledger and Model-Test Alignment guidance should consume these
  helpers as claim-boundary evidence when adapters or historical misses matter.

## Impact

- Affected package APIs: new dataclasses, report types, constants, and review
  functions exported through `flowguard.__init__`.
- Affected docs and skills: API surface docs, model-first skill guidance, risk
  evidence guidance, and release/change notes.
- Affected tests: API-surface tests plus focused helper tests for green and
  known-bad cases.
- Non-goal: no dependency on OpenSpec, FlowPilot, Codex, or a project-specific
  adapter at runtime; helpers stay standard-library only.
