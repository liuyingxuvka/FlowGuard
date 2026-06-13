# Bug Repair And Post-Runtime Model-Miss Protocol

Use this protocol for non-trivial bug repairs where a real failure exposes a
missed behavior class, and when runtime, tests, replay, logs, or manual
validation expose an issue after FlowGuard previously passed.

FlowGuard passing is provisional until the modeled change or process is checked
against production-facing evidence. A later green runtime check by itself does
not close a known model miss unless the miss has been reviewed.

If a user opens a UI after a green FlowGuard claim and the visible behavior is
wrong, treat the episode as a model miss. Typical UI miss types are
`evidence_overclaimed` when the prior proof only showed a label or API route,
and `boundary_missing` when the prior model did not account for the visible
control, field, source-interaction branch, task flow, human-operability rule, or UI state
update.

For bug repair work inside an existing modeled system, run Existing Model
Preflight first so the fix extends the current model boundary instead of
creating a parallel one.

## Required Steps

1. Reopen the model-first work instead of treating the prior pass, bug report,
   or failing test as a local patch target.
2. Classify the miss with one of the practical types:
   `boundary_missing`, `code_boundary_mismatch`, `state_too_coarse`,
   `input_branch_missing`, `invariant_too_weak`, or `evidence_overclaimed`.
3. Preserve the observed failure evidence and backpropagate the root cause into
   a structured false-negative record when there was any previous green claim:
   previous claim, observed failure, supported cause, `would_have_failed_if`,
   new plan/model/test item, and closure evidence. If there was no previous
   claim, record that explicitly instead of inventing one.
4. If the issue belongs in scope, represent the observed issue in executable
   evidence: scenario, invariant, replay adapter, representative trace, or
   model boundary note.
5. If the root cause involves a behavior-bearing field, schema key, config
   flag, prompt/config field, payload column, or persisted attribute, add
   `root_cause_field_ids`, `same_class_field_ids`, and `old_field_ids` as
   needed, then update FieldLifecycleMesh so projection and disposition gaps are
   explicit.
6. Add one same-class generalized bad case when practical.
7. For UI misses, run `review_ui_model_misses(...)` with a record of the prior
   green claim, why it looked green, the user-observed failure, affected
   controls/fields, same-class controls/fields, same-class tests or click
   evidence, task-flow/human-operability gaps, root-cause backpropagation, and
   code owner. Select/Open txt/Load table/Load File style failures should be
   reviewed as a same-class UI family before closure.
8. Add current test evidence for the observed regression and for the
   same-class generalized case. A point regression is necessary but does not
   close an in-scope miss by itself.
9. Bind the repaired obligation to the owner code contract that actually
   implements the behavior. Helper-only, adapter-only, or internal-path tests
   cannot close a public bug class by themselves.
10. Run Model-Test Alignment on the repaired model obligation, owner code
   contracts, and the observed/same-class test evidence. If the
   same-class validation is too large, slow, layered, stale-prone,
   background, or release-only, route that hierarchy to TestMesh and report
   scoped confidence until current child evidence exists.
11. If the repair adds, replaces, bypasses, or preserves an old/fallback/legacy
   path or old/replaced/deprecated field, route the compatibility surface
   through Architecture Reduction when appropriate and record a
   LegacyPathDisposition or field disposition: deleted, blocked, migrated,
   delegated to a repaired contract or replacement field, same-contract
   repaired, or explicitly out of scope with a reason. `unknown` blocks broad
   closure.
12. If sibling obligations share the same family-level claim, run
   obligation-family parity so every sibling has required mechanism evidence
   from allowed provenance.
13. Run an analogous defect scan for same-family siblings and caller-supplied
   related surfaces. Open must-scan candidates block broad closure; should-scan
   candidates must be covered, assigned to a separate change, or excluded with
   a concrete reason.
14. If the same-class miss recurs, or if a high-risk first miss would make a
   local point fix overclaim full confidence, promote it to a defect-family gate
   with a model obligation, authority boundary, observed failure, same-class
   generalized case, historical holdout, and current proof evidence. The gate
   is FlowGuard evidence for the existing Model-Miss/Risk Evidence Ledger
   chain, not a new downstream app skill.
15. Rerun the relevant model checks and confirm the old weakness is now visible,
   or deliberately mark the generalized case out of scope.
16. Validate the repair with the refined model plus the strongest practical
   production-facing evidence.
17. If the repair changed a child model under a parent ModelMesh, rerun the
   affected parent child-reattachment gate. The parent must consume the current
   child evidence id and confirm the child's inputs, outputs, state ownership,
   side-effect ownership, and outgoing guarantees still fit the parent flow.
18. If the miss shows that real code accepted an unmodeled input, emitted an
    extra output/error/state write/side effect, or failed a declared leaf cell,
    update the leaf boundary matrix and rerun layered proof. Do not close the
    miss with only a new ordinary test when the model boundary itself overflowed.
19. Run `review_model_maturation_loop(...)` over the miss classification,
    alignment result, mesh/layered proof result, code-boundary observations, and
    freshness rows. Resolve or explicitly scope any state, branch, invariant,
    same-class, obligation, child reattachment, or evidence-refresh action.
20. Run DevelopmentProcessFlow over the changed plan/model/code/test/docs
    artifacts so later edits do not stale the repair evidence.
21. Record `Miss type`, `Root cause backpropagation`, `Generalized case`, field
    lifecycle/projection/disposition evidence when fields are involved, owner
    code contract, observed-regression test evidence, same-class test evidence,
    family parity result, analogous scan result, legacy path disposition,
    Model-Test Alignment result, process freshness, and any parent reattachment
    or defect-family gate decision in adoption evidence and the Risk Evidence
    Ledger when a prior final claim had one, or explain why no generalized case
    was added.

## What Not To Add By Default

Do not add a hazard registry, upgrade reviewer, default model mesh, full
coverage matrix, or evidence-level field as the default response to ordinary
model misses. Use those only when the task already has framework-upgrade or
broad-capability risk. This does not waive the parent reattachment gate when the
miss repair changed a child model that an existing parent ModelMesh depends on.

## Completion Standard

The bug repair or model miss is closed only when it is classified, represented
in executable evidence or explicitly out of scope, rerun, validated with
production-facing evidence, and, for in-scope misses, backed by current
observed-regression and same-class test evidence in Model-Test Alignment. Root
cause must be backpropagated into the previous plan/model/test gap when a prior
claim existed, behavior-bearing fields must be represented in FieldLifecycleMesh
and projected when relevant, the repaired model obligation must bind to the
owner code contract, and reachable old/fallback/legacy paths or old fields must
have a disposition.
When the miss was repaired in a child model under a parent mesh, the affected
parent reattachment gate must also pass or remain an explicit blocker. The model
maturation loop must show no open in-scope upgrade action for a broad claim. A
patch plus a later green runtime check, or a patch plus one observed-bug
regression test, is not enough by itself. A recurring or high-risk same-class
miss also requires a current defect-family gate or an explicit
scoped-confidence boundary. A same-shape risk radius scan with open must-scan
candidates also keeps closure blocked.
If the prior green claim had a Risk Evidence Ledger row, mark the old proof as
stale or overclaimed and attach the new same-class evidence, family parity,
analogous scan status, and defect-family gate status before restoring full
confidence.

Layered proof misses should be mapped to the broken table before closure:
parent coverage gap, illegal child overlap, stale child reattachment, missing
leaf boundary cell, or real-code boundary overflow.
