# DevelopmentProcessFlow Protocol

Use `development_process_flow` as the FlowGuard development-process simulator
front door. It decides whether the current request needs `plan_detailing`,
`agent_workflow`, `execution_freshness`, or an ordered combination of those
internal modes before an agent implements, validates, installs, syncs, releases,
archives, publishes, or claims done.

This is the single hot-path process entry for non-trivial rough-plan
discussion, multi-skill workflow planning, and lifecycle evidence freshness.
The `flowguard-plan-detailing-compiler` and
`flowguard-agent-workflow-rehearsal` skills remain available as explicit or
delegated mode owners, not as competing generic first stops.

It can reference evidence produced by ModelMesh, TestMesh, StructureMesh,
ContractExhaustionMesh, Model-Test Alignment, Model Topology Hazard Review, LongCheck, Conformance
Adoption, PlanDetailing, or AgentWorkflowRehearsal through ids and freshness
metadata, and it should consume a Risk Evidence Ledger decision before final
done/release/archive/publish claims. It does not inspect, replace, or repair
those route internals.

## Simulator Modes

- `plan_detailing`: rough idea, vague request, short plan, or AI-generated
  outline must become explicit rows with scope, artifacts, steps, receipts,
  validation, failures, human questions, and claim boundaries. Delegate to
  PlanDetailing when detailed row construction is needed.
- `agent_workflow`: selected/skipped skills, tools, plugins, external actions,
  side effects, inventory freshness, continue/rework gates, or cross-route
  evidence claims must be rehearsed. Delegate to AgentWorkflowRehearsal when
  a full skill/tool workflow plan is needed.
- `execution_freshness`: staged edits, validation, install/sync, shadow sync,
  git/version work, release/archive/publish, peer writes, or final claims need
  artifact-version and evidence-freshness review. This protocol owns that mode.

For a full plan-to-release path, record all applicable modes in order:
`plan_detailing` -> `agent_workflow` -> `execution_freshness`.

## Trigger

Create or update a DevelopmentProcessFlow review when:

- a user asks to discuss, refine, detail, or accept a non-trivial plan;
- a task may require several Codex skills, tools, plugins, external actions,
  install/sync, release/publish, or cross-route evidence claims;
- non-trivial development, modification, refactor, prompt, skill, documentation,
  repository, install, or release work has multiple meaningful stages and
  requires validation;
- the work naturally follows staged actions such as plan, edit, test, fix, and
  verify before the agent can claim done;
- development step ordering matters, such as requirements, design, model, code,
  test, docs, release package, and archive actions;
- a later step might overwrite or invalidate an earlier step's evidence;
- tests, model files, validation adapters, review checklists, or other verifier
  artifacts changed after evidence was produced;
- a model or UI transition changed after transition coverage matrices, MTA
  obligations, or TestMesh required cell evidence were produced;
- a visible UI action map, click-through run, pure-UI classification, or manual
  UI boundary changed after implementation evidence was produced;
- a payload schema, fixture, real import/export/save/load/generate behavior,
  generated artifact, or AI work-package format changed after synthetic payload
  evidence was produced;
- a field lifecycle mesh, field projection, replacement disposition, or
  bug-repair closure artifact changed after alignment, process, or closure
  evidence was produced;
- a non-trivial bug repair changed root-cause evidence, model obligations,
  owner code contracts, observed/contract-exhaustion case tests, compatibility disposition,
  or ledger rows after earlier validation;
- a real-code alignment claim changed source-audit reports, binding-row gap
  codes, counterexample/known-bad target ids, or writer-inventory evidence after
  earlier validation;
- a done, release, archive, or publish claim depends on validation evidence;
- peer-agent or unknown-writer changes could make earlier evidence stale;
- a changed artifact touches a remembered open maintenance obligation and the
  owner route must be rerun or the final claim kept scoped;
- V-style requirement/design/model/code-to-validation pairs need explicit
  freshness checks;
- routine confidence may proceed while release-required evidence remains
  visible as deferred.

Do not trigger this route merely because tests are large or source structure is
being split. Use TestMesh for validation hierarchy and StructureMesh for code
structure decomposition. Use Model-Test Alignment for direct model/code/test
obligation coverage. Use core modeling for the product workflow itself.

Do not trigger PlanDetailing or AgentWorkflowRehearsal directly for generic
rough-plan or multi-skill setup unless the user explicitly names that skill or
DevelopmentProcessFlow has selected and delegated the corresponding simulator
mode.

Skip only for truly single-step work with no meaningful validation or artifact
freshness risk, such as a tiny typo fix, pure explanation, or formatting-only
change.

## Input Checklist

Use grouped process rows instead of separate blanks for every lifecycle field.

- changed artifacts: id/type, current version or fingerprint, path/owner, and
  upstream artifact ids when they affect freshness;
- process steps: action id/type, actor, status, decision scope, read/write
  artifacts, invalidations, and ordering dependencies;
- simulator mode decisions: selected modes, reason, delegated skill if any,
  required mode evidence, and scoped gaps;
- validation evidence: evidence id, kind, producer route, status, command or
  result path, covered artifact versions, verifier artifacts, and validation
  requirement ids;
- UI/payload evidence when relevant: action-map revision, clicked control ids,
  real payload surface ids, payload contract ids, synthetic case ids,
  execution proof refs, work-package fixture ids, and manual/native-dialog
  boundaries;
- UI task completion evidence type when relevant: `ui_model_coverage`,
  `ui_static_test`, `ui_runtime_click`, `ui_browser_dom_geometry`,
  `ui_desktop_manual_observation`, `ui_native_dialog_blindspot`,
  `ui_work_mode`, `ui_source_baseline`, `ui_source_target_mapping`,
  `ui_source_interaction`, `ui_observed_source_alignment`,
  `ui_observed_inventory`, `ui_functional_chain`,
  `ui_human_operability`, `ui_implementation_validation`, or `ui_done_claim_review`;
- UI lifecycle artifacts when relevant: observed real-surface inventory,
  enabled-control functional chain, human-operability, source-baseline
  interaction gate, and UI done-claim review;
- evidence caveats: skipped visibility, background final artifacts,
  release-required flags, stale reasons, and proof artifact when a final claim
  depends on the row;
- final claim boundary: routine vs release/archive/publish scope and the Risk
  Evidence Ledger row that consumes the lifecycle evidence.

## Validation Failure Triage

After any failed, stale, skipped, timeout, running, progress-only, oversized, or
ambiguous validation result, DevelopmentProcessFlow must classify the failure
before the agent continues implementation, reruns toward green, or claims done.
The classification is part of the development evidence.

Use these triage classes:

- `ordinary_implementation_defect`: the failure points to a normal code,
  prompt, doc, or adapter defect. Continue through the ordinary fix path, then
  rerun the affected validation.
- `model_too_thick`: a FlowGuard model is oversized, mixes unrelated
  responsibilities, or is being used as direct parent evidence when a
  parent/child split is needed. Hand off to ModelMesh.
- `test_too_thick`: a test/check command is slow, broad, layered, skipped,
  stale, release-only, or hides child evidence status. Hand off to TestMesh.
- `auto_split_required`: `review_auto_mesh_splits(...)` found direct model or
  validation evidence that is oversized, incomplete, slow, broad,
  progress-only, or release-only. Hand off to the reported ModelMesh or
  TestMesh split gate and keep lifecycle confidence blocked or scoped until
  current mesh evidence is consumed.
- `model_test_mismatch`: model obligations, owner code contracts, and ordinary
  test evidence do not bind the same behavior. Hand off to Model-Test
  Alignment.
- `transition_coverage_stale`: modeled transitions changed after the transition
  coverage matrix, Model-Test Alignment obligations, or TestMesh required cell
  ids were generated. Regenerate the matrix and rerun the owning evidence
  route.
- `contract_exhaustion_matrix_stale`: a field/schema boundary, same-class
  family seed, payload contract, transition matrix, parent/child closure,
  interaction group, coverage shard, coverage receipt, or no-delta loop changed
  after canonical bad-case ids were generated. Regenerate ContractExhaustionMesh
  cases and rerun affected MTA/TestMesh/ModelMesh/Risk Ledger evidence.
- `ui_action_evidence_stale`: reachable controls, modeled UI events,
  pure-UI classifications, or native/manual boundaries changed after UI
  implementation validation. Rerun UI Flow Structure implementation evidence.
- `ui_real_surface_evidence_stale`: observed visible items, enabled controls,
  status text, tables, displayed fields, human-operability, source-baseline
  mapping, or native dialog boundaries changed after observed-inventory,
  functional-chain, source-interaction, or done-claim evidence. Rerun the UI
  Flow Structure hard gates before completion.
- `artifact_payload_evidence_stale`: a payload schema, fixture, real payload
  surface, generated artifact, or AI work-package shape changed after payload
  validation. Rebuild synthetic payload cases, rerun the real surface, and
  rerun Model-Test Alignment or TestMesh.
- `topology_hazard_gap`: a locally green model topology still has anchored
  future-use hazards. Hand off to Model Topology Hazard Review and keep the
  lifecycle claim scoped or blocked until current route evidence is consumed.
- `stale_evidence`: the artifact or verifier version changed after evidence
  was produced. Rerun or replace the owning evidence before it can support the
  lifecycle claim.
- `three_way_binding_stale`: a model obligation, owner code contract, code
  source, source-audit report, test row, transition cell, bad-case closure
  target, or proof artifact changed after a model-code-test binding row was
  produced. Regenerate the affected row and rerun Model-Test Alignment before
  claiming done or release confidence.
- `bug_repair_closure_stale`: a root-cause backpropagation record,
  contract-exhaustion case, generated combination case, coverage receipt, owner
  code contract, legacy path disposition, or Risk Evidence Ledger row changed
  after the repair was validated. Rerun the owning route evidence before
  claiming done or release confidence.
- `field_lifecycle_changed_after_field_evidence`: FieldLifecycleMesh rows
  changed after field lifecycle evidence was produced. Rerun FieldLifecycleMesh
  and consume the new report before broad claims.
- `field_projection_changed_after_alignment_pass`: a behavior-bearing field
  projection changed after Model-Test Alignment passed. Regenerate field
  obligations/contracts and rerun alignment.
- `runtime_writer_inventory_stale`: a runtime-gateway claim changed critical
  state surfaces, gateway contracts, discovered writers, scoped-out writer
  reasons, or inventory proof artifacts after adoption evidence passed. Rerun
  Runtime Gateway Adoption before claiming runtime protection.
- `replacement_disposition_changed_after_closure_pass`: old-path or old-field
  disposition changed after closure evidence. Rerun the owning disposition and
  closure routes.
- `bug_repair_closure_changed_after_review_pass`: observed/same-class/root
  cause closure rows changed after review. Rerun Model-Miss Review and consume
  the new evidence.
- `parent_child_evidence_not_reattached`: a child model, child validation
  suite, or sibling route is locally green, but the parent has not consumed the
  current evidence id and contract. Return to the owning parent evidence gate.

Do not treat a later green command as closing a triage finding by itself. If
the classification was `model_too_thick`, `test_too_thick`, or
`model_test_mismatch`, the owning satellite route must produce current
evidence and the parent lifecycle review must consume that evidence id before a
done, release, archive, or publish claim is supported.

When sibling evidence says the model is too coarse, stale, disconnected, or
missing an obligation, include a `review_model_maturation_loop(...)` row in the
minimum revalidation plan. A broad lifecycle claim must either consume the
current model-upgrade evidence or explicitly report scoped confidence.

Capture validation requirements as one grouped row per requirement: id,
required artifacts, evidence kinds or explicit evidence ids, routine/release
scope, V-style pair when relevant, and rerun command.

Capture freshness as one grouped rule: upstream artifact, invalidated
downstream artifacts or evidence kinds, and rationale for the propagation.

## Required Findings

Keep these findings visible:

- `unknown_artifact_reference`;
- `out_of_order_process_step`;
- `stale_evidence_after_artifact_change`;
- `test_changed_after_test_pass`;
- `model_changed_after_alignment_pass`;
- `transition_matrix_changed_after_test_pass`;
- `requirement_change_without_downstream_revalidation`;
- `unknown_writer_invalidates_evidence`;
- `ambiguous_freshness_policy`;
- `progress_only_validation_claimed_complete`;
- `hidden_skipped_validation_claimed_pass`;
- `failed_validation_claimed_current`;
- `validation_evidence_not_current`;
- `missing_v_model_validation_pair`;
- `missing_required_revalidation`;
- `release_claim_with_stale_evidence`;
- `release_evidence_not_current`;
- `model_maturation_required_before_final_claim`;
- `final_claim_missing_risk_evidence_ledger`;
- `final_claim_uses_blocked_risk_evidence`;
- `open_maintenance_obligation_claimed_done`.

## Prompt Template

```text
Build a FlowGuard DevelopmentProcessFlow review for this repository.

Treat the development lifecycle itself as the modeled process. Do not supervise
or inspect sibling routes. If evidence came from TestMesh, StructureMesh,
ModelMesh, Model-Test Alignment, Model Topology Hazard Review, LongCheck, or
Conformance Adoption, reference only its evidence id, producer route, status,
covered artifact versions, and freshness metadata.

Use these groups:

- Changed artifacts: identity, version, and upstream links.
- Process steps: action/status/scope, reads/writes/invalidates, and produced or
  required evidence.
- Validation evidence: identity/status/freshness, covered and verifier
  artifacts, plus skipped/background/release caveats.
- Validation requirements: requirement/scope, required artifacts or evidence,
  and V-style pair or rerun command.
- Freshness rules: upstream, downstream, and rationale.

Known hazards that must fail:
- stale evidence after code, test, model, or requirement changes;
- stale transition coverage after model/UI transition changes;
- done/release/archive/publish claim using stale evidence;
- failed validation pushed through without failure triage;
- oversized model evidence treated as an ordinary failure instead of ModelMesh
  handoff;
- oversized, skipped, stale, or release-only validation treated as an ordinary
  failure instead of TestMesh handoff;
- model/test obligation mismatch treated as an ordinary failure instead of
  Model-Test Alignment handoff;
- topology-anchored future-use hazard treated as generic prose instead of
  Model Topology Hazard Review evidence;
- child-local green evidence counted as parent confidence before parent
  reattachment;
- progress-only background evidence counted as complete;
- hidden skipped validation counted as passed;
- failed, timeout, skipped, not-run, or running evidence counted as current;
- missing V-style validation pair;
- peer or unknown writer changing covered artifacts after evidence;
- ambiguous freshness policy for declared upstream/downstream artifacts.
```

## Completion Standard

A DevelopmentProcessFlow review can support a lifecycle claim only when:

- every referenced artifact, evidence id, validation id, and ordering
  dependency is registered;
- evidence is current for the artifact versions and verifier versions it
  claims to cover;
- upstream changes have explicit freshness rules or are reported as ambiguous;
- skipped, failed, timeout, not-run, running, stale, and progress-only evidence
  remain visible and do not satisfy current validation;
- OpenSpec or task-list checkboxes for UI work carry a current evidence type;
  artifact completion, planned evidence, background liveness, or a checked box
  is not release completion by itself;
- done, release, archive, and publish claims have current passing evidence for
  the requested scope;
- UI done/release claims consume current observed-inventory, functional-chain,
  source-baseline interaction semantics when applicable,
  `UIImplementationValidation`, and UI done-claim review evidence;
- broad done, release, archive, publish, framework-sync, or final-confidence
  claims use proof-artifact-bound evidence: each consumed validation row has a
  current `ProofArtifactRef` with result path, fingerprint, passing status,
  covered validation obligation, and no route gaps;
- release-required evidence is current for release scope, or visibly deferred
  only for routine scope;
- remembered maintenance obligations touched by changed artifacts have current
  owner-route evidence or are carried as scoped confidence;
- bug-repair claims consume current root-cause backpropagation,
  model-code-test alignment, compatibility or legacy path disposition, and
  Risk Evidence Ledger evidence instead of only a later green test command;
- any validation failure has a visible triage class, and non-ordinary triage
  classes have current evidence from the owning satellite or parent evidence
  gate;
- the report includes minimum revalidation recommendations for unsupported
  requirements.

## Layered Boundary Proof Freshness

When a done, release, archive, or publish claim depends on layered model
confidence, treat `review_layered_boundary_proof(...)` output as a sibling
evidence id. DevelopmentProcessFlow does not inspect the four proof tables, but
it must keep their freshness rules visible:

- parent coverage edits stale the parent proof decision;
- child ownership, state, side-effect, invariant, or contract edits stale
  disjointness and reattachment;
- child evidence id changes stale parent reattachment until the parent consumes
  the new id;
- code, test, adapter, or observation edits under a leaf stale the affected
  leaf boundary-matrix cells.
- model/UI transition edits stale generated transition coverage cells, MTA
  transition obligations, and TestMesh required cell ids derived from them.
- ModelMesh closure edits stale generated transition coverage cells, MTA
  transition obligations, and TestMesh required cell ids derived from closure
  transitions, especially retry/rejection repeat-input cells.
- test command, source, tested artifact, dependency, environment, result
  fingerprint, or coverage-scope edits stale any `TestResultReuseTicket` that
  reused old test output.

Progress-only background regressions can show liveness, but they do not satisfy
layered proof freshness until final artifacts and exit status exist.
