# Post-Runtime Model-Miss Protocol

Use this protocol when runtime, tests, replay, logs, or manual validation expose
an issue after FlowGuard previously passed.

FlowGuard passing is provisional until the modeled change or process is checked
against production-facing evidence. A later green runtime check by itself does
not close a known model miss unless the miss has been reviewed.

## Required Steps

1. Reopen the model-first work instead of treating the prior pass as final.
2. Classify the miss with one of five practical types:
   `boundary_missing`, `state_too_coarse`, `input_branch_missing`,
   `invariant_too_weak`, or `evidence_overclaimed`.
3. If the issue belongs in scope, represent the observed issue in executable
   evidence: scenario, invariant, replay adapter, representative trace, or
   model boundary note.
4. Add one same-class generalized bad case when practical.
5. Add current test evidence for the observed regression and for the
   same-class generalized case. A point regression is necessary but does not
   close an in-scope miss by itself.
6. Run Model-Test Alignment on the repaired model obligation, optional code
   contracts when in scope, and the observed/same-class test evidence. If the
   same-class validation is too large, slow, layered, stale-prone,
   background, or release-only, route that hierarchy to TestMesh and report
   scoped confidence until current child evidence exists.
7. If the same-class miss recurs, or if a high-risk first miss would make a
   local point fix overclaim full confidence, promote it to a defect-family gate
   with a model obligation, authority boundary, observed failure, same-class
   generalized case, historical holdout, and current proof evidence. The gate
   is FlowGuard evidence for the existing Model-Miss/Risk Evidence Ledger
   chain, not a new downstream app skill.
8. Rerun the relevant model checks and confirm the old weakness is now visible,
   or deliberately mark the generalized case out of scope.
9. Validate the repair with the refined model plus the strongest practical
   production-facing evidence.
10. If the repair changed a child model under a parent ModelMesh, rerun the
   affected parent child-reattachment gate. The parent must consume the current
   child evidence id and confirm the child's inputs, outputs, state ownership,
   side-effect ownership, and outgoing guarantees still fit the parent flow.
11. If the miss shows that real code accepted an unmodeled input, emitted an
   extra output/error/state write/side effect, or failed a declared leaf cell,
   update the leaf boundary matrix and rerun layered proof. Do not close the
   miss with only a new ordinary test when the model boundary itself overflowed.
12. Record `Miss type`, `Generalized case`, observed-regression test evidence,
   same-class test evidence, Model-Test Alignment result, and any parent
   reattachment or defect-family gate decision in adoption evidence and the Risk
   Evidence Ledger when a prior final claim had one, or explain
   why no generalized case was added.

## What Not To Add By Default

Do not add a hazard registry, upgrade reviewer, default model mesh, full
coverage matrix, or evidence-level field as the default response to ordinary
model misses. Use those only when the task already has framework-upgrade or
broad-capability risk. This does not waive the parent reattachment gate when the
miss repair changed a child model that an existing parent ModelMesh depends on.

## Completion Standard

The model miss is closed only when it is classified, represented in executable
evidence or explicitly out of scope, rerun, validated with production-facing
evidence, and, for in-scope misses, backed by current observed-regression and
same-class test evidence in Model-Test Alignment. When the miss was repaired in
a child model under a parent mesh, the affected parent reattachment gate must
also pass or remain an explicit blocker. A patch plus a later green runtime
check, or a patch plus one observed-bug regression test, is not enough by
itself. A recurring or high-risk same-class miss also requires a current
defect-family gate or an explicit scoped-confidence boundary.
If the prior green claim had a Risk Evidence Ledger row, mark the old proof as
stale or overclaimed and attach the new same-class evidence plus defect-family
gate status before restoring full confidence.

Layered proof misses should be mapped to the broken table before closure:
parent coverage gap, illegal child overlap, stale child reattachment, missing
leaf boundary cell, or real-code boundary overflow.
