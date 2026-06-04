## Context

FlowGuard already has the pieces needed for disciplined bug repair:
Existing Model Preflight finds current model ownership, Model-Miss Review
separates an observed bug from the bug class, Plan Intake can backpropagate
false negatives, Model-Test Alignment locks model obligations to code
contracts and tests, DevelopmentProcessFlow tracks stale evidence, and the Risk
Evidence Ledger / Closure Contract controls final confidence.

The current weakness is discoverability and ordering. A user can say "fix this
bug" and the agent may treat it as normal implementation unless a prior
FlowGuard pass has already been contradicted. The repair should remain inside
the existing route family; adding a separate bug-fix route would duplicate
responsibility and increase route drift.

## Goals / Non-Goals

**Goals:**
- Make non-trivial bug repairs a first-class trigger for the existing
  Model-Miss Review route.
- Add root-cause backpropagation wording that reuses existing Plan Intake
  false-negative fields.
- Require bug repair closure to show the model obligation, owner code contract,
  observed-regression test, same-class test, and current alignment evidence.
- Carry fallback, old-path, alias, and compatibility decisions through existing
  Architecture Reduction and LegacyPathDisposition evidence.
- Keep final confidence scoped or blocked when any route evidence is missing,
  stale, internal-only, progress-only, or explicitly deferred.

**Non-Goals:**
- No new FlowGuard satellite skill.
- No new standalone bug-fix closure API unless tests expose an existing API
  gap.
- No compatibility switch that allows model-test-only bug repair closure.
- No remote GitHub publish unless requested separately after local sync.

## Decisions

1. **Upgrade Model-Miss Review instead of creating a new route.**
   Model-Miss Review already owns observed failure, same-class generalized bad
   case, recurring defect-family gates, and repair validation. The change will
   broaden its trigger and protocol while keeping existing ownership.

2. **Use Plan Intake false-negative backpropagation for root cause.**
   Root-cause proof will be expressed through the existing shape:
   previous passing claim, observed failure, supported cause,
   would-have-failed-if condition, and new plan/model/repair evidence. This
   avoids a parallel root-cause vocabulary.

3. **Use Model-Test Alignment for the model-code-test lock.**
   Bug repair closure must reuse existing `ModelObligation`, `CodeContract`,
   and `TestEvidence` closure roles. The Model-Miss route will explain the
   handoff; MTA keeps the executable check.

4. **Use existing compatibility and legacy-path evidence.**
   Architecture Reduction classifies fallback/compatibility surfaces before
   contraction. LegacyPathDisposition closes reachable old paths during
   repair. Model-Miss Review should call out those handoffs rather than
   replacing them.

5. **Use DevelopmentProcessFlow and Closure Contract as coordinators.**
   DevelopmentProcessFlow tracks whether later edits stale evidence. Closure
   Contract and Risk Evidence Ledger decide whether the final claim can be
   full, scoped, or blocked. They remain coordinators, not owners of the
   underlying proof.

## Risks / Trade-offs

- **Risk:** The new wording becomes too heavy for tiny bug fixes.
  **Mitigation:** Scope the trigger to non-trivial bug repairs and allow
  explicit scoped/out-of-scope reasons for tiny or unavailable evidence.

- **Risk:** Agents treat the upgraded wording as a new route.
  **Mitigation:** Repeatedly state that this is the existing Model-Miss Review
  route and that downstream checks stay with existing route owners.

- **Risk:** Tests only verify words, not behavior.
  **Mitigation:** Protect both wording and executable behavior with existing
  public template tests, Model-Test Alignment tests, Plan Intake tests, Risk
  Ledger tests, and OpenSpec validation.

- **Risk:** Local shadow and git source copies drift.
  **Mitigation:** Validate in the active shadow workspace, then sync package,
  tests, docs, skills, OpenSpec artifacts, installed Codex skills, editable
  install, project records, and git source together.
