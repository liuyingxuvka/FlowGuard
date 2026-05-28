# Post-Runtime Model-Miss Protocol

Use this protocol when runtime, tests, replay, logs, or manual validation expose
an issue after FlowGuard previously passed.

FlowGuard passing is provisional until the modeled change or process is checked
against production-facing evidence. A later green runtime check by itself does
not close a known model miss unless the miss has been reviewed.

Keep responsibility split cleanly. Model-Miss Review owns the current bug
instance, its practical miss type, and the same-class bug responsibility and
generalized bad case. ModelMesh owns parent/child reattachment, upward boundary
propagation, and affected sibling review when the repair changes a child model
boundary. A fix that only proves the current instance no longer reproduces is
not bug-class closure.
When sibling obligations share the same family-level claim, Model-Miss Review
also consumes obligation-family parity and an analogous defect scan before
broad closure can be restored.

## Required Steps

1. Reopen the model-first work instead of treating the prior pass as final.
2. Classify the miss with one of five practical types:
   `boundary_missing`, `state_too_coarse`, `input_branch_missing`,
   `invariant_too_weak`, or `evidence_overclaimed`.
3. If the issue belongs in scope, represent the observed issue in executable
   evidence: scenario, invariant, replay adapter, representative trace, or
   model boundary note.
4. Add one same-class generalized bad case when practical.
5. Run obligation-family parity when related obligations share the same claim,
   then run an analogous defect scan for same-shape sibling or related-surface
   risks.
6. Rerun the relevant model checks and confirm the old weakness is now visible,
   or deliberately mark the generalized case out of scope.
7. Validate the repair with the refined model plus the strongest practical
   production-facing evidence.
8. If the repair changed a child model under a parent ModelMesh, rerun the
   affected parent child-reattachment gate. The parent must consume the current
   child evidence id and confirm the child's inputs, outputs, state ownership,
   side-effect ownership, and outgoing guarantees still fit the parent flow.
9. If the child boundary changed, keep the miss open until the affected parent
   ModelMesh has reviewed upward propagation and any affected sibling model
   assumptions.
10. If the miss shows that real code accepted an unmodeled input, emitted an
   extra output/error/state write/side effect, or failed a declared leaf cell,
   update the leaf boundary matrix and rerun layered proof. Do not close the
   miss with only a new ordinary test when the model boundary itself overflowed.
11. Treat background long-running checks as liveness until final output, error,
   combined log, exit, and metadata artifacts exist. Progress is not
   production-facing pass evidence.
12. Record `Miss type`, `Generalized case`, family parity result, analogous
    scan result, and any parent reattachment decision in adoption evidence and
    the Risk Evidence Ledger when a prior final claim had one, or explain why
    no generalized case was added.

## What Not To Add By Default

Do not add a hazard registry, upgrade reviewer, default model mesh, full
coverage matrix, or evidence-level field as the default response to ordinary
model misses. Use those only when the task already has framework-upgrade or
broad-capability risk. This does not waive the parent reattachment gate when the
miss repair changed a child model that an existing parent ModelMesh depends on.

## Completion Standard

The model miss is closed only when it is classified, represented in executable
evidence or explicitly out of scope, rerun, and validated with production-facing
evidence. When the miss was repaired in a child model under a parent mesh, the
affected parent reattachment gate, upward boundary propagation review, and
affected sibling review must also pass or remain explicit blockers. A patch
plus a later green runtime check or in-progress background run is not enough by
itself. Open same-shape must-scan candidates from an analogous defect scan also
block full closure.
If the prior green claim had a Risk Evidence Ledger row, mark the old proof as
stale or overclaimed and attach the new same-class evidence, family parity, and
analogous scan status before restoring full confidence.

Layered proof misses should be mapped to the broken table before closure:
parent coverage gap, illegal child overlap, stale child reattachment, missing
leaf boundary cell, or real-code boundary overflow.
