# DevelopmentProcessFlow Protocol

Use `development_process_flow` when the risky question is not whether a product
workflow, test hierarchy, model mesh, or code structure is correct, but whether
a staged development lifecycle can still trust its process order and validation
evidence after later work.

This is a sibling sub-protocol. It supports planning and execution evidence
without supervising other routes. It can reference evidence produced by
ModelMesh, TestMesh, StructureMesh, Model-Test Alignment, LongCheck, or
Conformance Adoption through ids and freshness metadata, and it should consume
a Risk Evidence Ledger decision before final done/release/archive/publish
claims. It does not inspect, replace, or repair those route internals.

When the upstream plan is vague or only a short AI outline, use
`flowguard-plan-detailing-compiler` first. Its `PlanDetail` rows can be
projected with `plan_detail_to_development_process(...)` to create lifecycle
artifacts, actions, evidence, validation requirements, and freshness rules.
DevelopmentProcessFlow then owns evidence freshness; plan detailing only proves
the lifecycle rows are explicit enough to review.

## Trigger

Create or update a DevelopmentProcessFlow review when:

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
- a done, release, archive, or publish claim depends on validation evidence;
- peer-agent or unknown-writer changes could make earlier evidence stale;
- V-style requirement/design/model/code-to-validation pairs need explicit
  freshness checks;
- routine confidence may proceed while release-required evidence remains
  visible as deferred.

Do not trigger this route merely because tests are large or source structure is
being split. Use TestMesh for validation hierarchy and StructureMesh for code
structure decomposition. Use Model-Test Alignment for direct model/code/test
obligation coverage. Use core modeling for the product workflow itself.

Skip only for truly single-step work with no meaningful validation or artifact
freshness risk, such as a tiny typo fix, pure explanation, or formatting-only
change.

## Input Checklist

List process artifacts:

- artifact id and type, such as requirement, design, model, code, test, adapter,
  doc, release asset, or sibling route report;
- current version or fingerprint;
- path, owner, and upstream artifact ids when relevant.

List process actions:

- action id, type, actor, status, and decision scope;
- read artifacts, written artifacts, direct invalidations, produced evidence,
  required evidence, and required validation ids;
- ordering dependencies such as `order_after`.

List process evidence:

- evidence id, kind, producer route, status, command, and result path;
- covered artifact ids and covered versions;
- verifier artifacts such as test files, model files, adapters, or checklists;
- background completion artifacts, skipped visibility, and release-required
  flags;
- validation requirement ids the evidence is intended to satisfy.

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
- `model_test_mismatch`: model obligations, optional code contracts, and
  ordinary test evidence do not line up. Hand off to Model-Test Alignment.
- `stale_evidence`: the artifact or verifier version changed after evidence
  was produced. Rerun or replace the owning evidence before it can support the
  lifecycle claim.
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

List validation requirements:

- requirement id;
- required artifact ids and evidence kinds;
- explicit evidence ids when only selected evidence may satisfy the requirement;
- routine or release scope;
- V-style pair flag and rerun command.

List freshness rules:

- upstream artifact id;
- downstream artifact ids or evidence kinds invalidated by that upstream
  change;
- rationale for why the propagation is intentional.

## Required Findings

Keep these findings visible:

- `unknown_artifact_reference`;
- `out_of_order_process_step`;
- `stale_evidence_after_artifact_change`;
- `test_changed_after_test_pass`;
- `model_changed_after_alignment_pass`;
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
- `final_claim_uses_blocked_risk_evidence`.

## Prompt Template

```text
Build a FlowGuard DevelopmentProcessFlow review for this repository.

Treat the development lifecycle itself as the modeled process. Do not supervise
or inspect sibling routes. If evidence came from TestMesh, StructureMesh,
ModelMesh, Model-Test Alignment, LongCheck, or Conformance Adoption, reference
only its evidence id, producer route, status, covered artifact versions, and
freshness metadata.

Process artifacts:
- artifact id/type/current version:
- upstream artifacts:

Process actions:
- action id/type/actor/scope/status:
- reads/writes/invalidates:
- produced evidence:
- required evidence or validation ids:

Evidence records:
- evidence id/kind/producer route/status:
- covered artifacts and versions:
- verifier artifacts:
- background completion artifacts:
- skipped visibility:
- release required:

Validation requirements:
- requirement id:
- required artifacts:
- required evidence kinds:
- explicit evidence ids:
- routine or release scope:
- V-style pair:
- rerun command:

Freshness rules:
- upstream artifact:
- invalidated downstream artifacts or evidence kinds:
- rationale:

Known hazards that must fail:
- stale evidence after code, test, model, or requirement changes;
- done/release/archive/publish claim using stale evidence;
- failed validation pushed through without failure triage;
- oversized model evidence treated as an ordinary failure instead of ModelMesh
  handoff;
- oversized, skipped, stale, or release-only validation treated as an ordinary
  failure instead of TestMesh handoff;
- model/test obligation mismatch treated as an ordinary failure instead of
  Model-Test Alignment handoff;
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
- done, release, archive, and publish claims have current passing evidence for
  the requested scope;
- broad done, release, archive, publish, framework-sync, or final-confidence
  claims use proof-artifact-bound evidence: each consumed validation row has a
  current `ProofArtifactRef` with result path, fingerprint, passing status,
  covered validation obligation, and no route gaps;
- release-required evidence is current for release scope, or visibly deferred
  only for routine scope;
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
- test command, source, tested artifact, dependency, environment, result
  fingerprint, or coverage-scope edits stale any `TestResultReuseTicket` that
  reused old test output.

Progress-only background regressions can show liveness, but they do not satisfy
layered proof freshness until final artifacts and exit status exist.
