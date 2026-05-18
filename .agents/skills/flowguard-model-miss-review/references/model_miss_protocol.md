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
5. Rerun the relevant model checks and confirm the old weakness is now visible,
   or deliberately mark the generalized case out of scope.
6. Validate the repair with the refined model plus the strongest practical
   production-facing evidence.
7. Record `Miss type` and `Generalized case` in adoption evidence, or explain
   why no generalized case was added.

## What Not To Add By Default

Do not add a hazard registry, upgrade reviewer, default model mesh, full
coverage matrix, or evidence-level field as the default response to ordinary
model misses. Use those only when the task already has framework-upgrade or
broad-capability risk.

## Completion Standard

The model miss is closed only when it is classified, represented in executable
evidence or explicitly out of scope, rerun, and validated with production-facing
evidence. A patch plus a later green runtime check is not enough by itself.
