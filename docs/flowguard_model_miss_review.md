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
- Was a behavior-bearing field omitted, under-modeled, wrongly scoped out, or
  left without reader/writer/owner visibility?
- Was the failure found by a user opening or clicking the UI after a green
  claim? If yes, record it as a UI model miss rather than a local button fix.
- Which prior UI model or evidence row went green, and was it green only
  because a label matched, an API route existed, or a planned click was
  overclaimed?
- Which affected controls/fields and same-class controls/fields now need
  same-class click or implementation evidence?
- Did the user fail because the UI was confusing rather than technically
  unwired? If yes, preserve task-flow, affordance, action grammar, dialog
  return, keyboard/focus, walkthrough, and same-class task evidence.
- How is the issue now represented: scenario, invariant, replay adapter,
  representative trace, or explicit out-of-scope boundary?
- What same-class generalized bad case prevents a point-fix-only repair, and is
  that class represented or explicitly out of scope?
- How is the known bug used as validation or holdout evidence instead of the
  whole model target?
- Which observed-regression test and same-class generalized test evidence now
  prove the repaired obligation?
- Which root-cause field ids and same-class field case ids prove the repair is
  not only an observed-field point fix?
- Which owner code contract implements the repaired behavior, and which
  Model-Test Alignment rows prove the model obligation, owner code contract,
  observed-regression test, and same-class test cover the same behavior?
- Are old, fallback, compatibility, or alternate paths still reachable? If yes,
  are they deleted, blocked, delegated to the repaired contract,
  same-contract repaired, or explicitly out of scope with a reason?
- Are old, replaced, deprecated, or compatibility-like fields still reachable?
  If yes, has FieldLifecycleMesh produced a closing disposition and can that
  row be reviewed as legacy path disposition evidence?
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
For UI misses, full closure also needs `review_ui_model_misses(...)` evidence:
previous claim, previous green reason, observed failure, affected
controls/fields, same-class controls/fields, same-class tests or click
evidence, task-flow and human-operability gaps, root-cause backpropagation, and
code owner.
When the root cause is a field, full closure also needs same-class field cases,
field lifecycle projection into Model-Test Alignment, and old-field
disposition for any legacy field left in or near the repaired path.
Child-local green is not enough when parent mesh confidence depends on the
child's input/output/state/side-effect handoff.
