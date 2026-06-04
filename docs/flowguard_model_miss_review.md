# FlowGuard Model-Miss Review Notes

Use this scaffold for non-trivial bug repairs and when real validation finds an
issue after a FlowGuard pass.

## Review Questions

- Why did the earlier model miss this bug class?
- Was there a previous green or broad-confidence claim? If yes, what was the
  previous claim id, observed failure, supported root cause, and
  `would_have_failed_if` condition?
- Which new plan, model, code-contract, or test item would have caught this
  bug class before the fix?
- Was the boundary too narrow, the state too coarse, an input branch missing, an
  invariant weak, a replay skipped, or the issue outside the modeled scope?
- How is the issue now represented: scenario, invariant, replay adapter,
  representative trace, or explicit out-of-scope boundary?
- What same-class generalized bad case prevents a point-fix-only repair, and is
  that class represented or explicitly out of scope?
- How is the known bug used as validation or holdout evidence instead of the
  whole model target?
- Which observed-regression test and same-class generalized test evidence now
  prove the repaired obligation?
- Which owner code contract implements the repaired behavior, and which
  Model-Test Alignment rows prove the model obligation, owner code contract,
  observed-regression test, and same-class test cover the same behavior?
- Are old, fallback, compatibility, or alternate paths still reachable? If yes,
  are they deleted, blocked, delegated to the repaired contract,
  same-contract repaired, or explicitly out of scope with a reason?
- Has this same-class family appeared before, or is it high risk enough to
  require a defect-family gate rather than another ordinary bug fix?
- Which defect-family gate records the family id, authority boundary, observed
  failure, same-class generalized case, historical holdout, and current proof?
- Which refined model checks, runtime checks, and same-class tests must pass
  before completion?
- If the repair changed a child model under a parent ModelMesh, which parent
  reattachment gate consumed the new child evidence id?
- If same-class validation is large, slow, layered, background, or release-only,
  which TestMesh parent/child suite owns it and where is final result evidence?
- Which DevelopmentProcessFlow and Risk Evidence Ledger rows consume the final
  model/code/test/legacy-path evidence, and which later edits would stale them?

Do not let a later green runtime check, one observed-bug regression test, or a
second local point fix close a known model miss by itself. Full closure needs
root-cause backpropagation when there was a prior claim, owner code contract
binding, same-class test evidence, legacy path disposition for reachable old
paths, and recurring families need a defect-family gate or an explicit
scoped-confidence boundary.
Child-local green is not enough when parent mesh confidence depends on the
child's input/output/state/side-effect handoff.
