## Context

`UIInteractionModel` and `UIJourneyCoverage` protect the model layer: visible
controls must have modeled events, modeled events must be owned by a journey or
blindspot, and complete app UI claims must start from launch. They do not prove
that a feature from the functional model is exposed by the UI, that every UI
journey has functional ownership, or that the running interface was actually
opened and clicked through.

The new layer should not replace browser tools or human QA. It should record the
evidence those tools produce and check that the evidence matches the same model
that created the UI journey inventory.

## Goals / Non-Goals

**Goals:**

- Connect user-visible functional features to UI journey coverage and real UI
  validation evidence.
- Reject functional features with no UI journey, UI journeys with no functional
  owner, and actionable UI controls that are neither function-owned nor
  explicitly pure UI behavior.
- Require implemented-UI completion claims to include browser, desktop, or
  manual click-through evidence for each modeled feature journey, including
  failure/recovery/cancel/exit paths when they are part of the model.
- Keep design-only UI modeling lightweight: implementation evidence is not
  required unless an implemented/runnable UI claim is made.
- Keep residual blindspots visible with reason, owner, validation boundary, and
  follow-up evidence target.

**Non-Goals:**

- Do not automate browser or desktop UI interaction inside this helper.
- Do not require only manual validation; browser automation, desktop automation,
  and human click-through records are all valid evidence methods.
- Do not infer the full product feature inventory automatically; the feature
  contract must be declared or handed in from an external functional model.
- Do not replace accessibility, visual design, Figma review, or production
  telemetry.
- Do not introduce external dependencies.

## Decisions

### Add a separate implementation validation object

Create `UIImplementationValidation` rather than overloading
`UIJourneyCoverage`. Journey coverage remains model evidence. Implementation
validation records real UI evidence, freshness, feature ownership, and residual
implementation blindspots.

Alternative considered: add `validated` flags to each feature journey. That
would blur model coverage with runtime evidence and make it easier to claim a
feature is implemented without recording how it was verified.

### Represent functional ownership as feature contracts

Add `UIFeatureContract` to represent the functional model slice relevant to the
UI: feature id, exposure mode, required controls, required events, journey ids,
and whether the feature is user-visible. This makes alignment explicit even
when the source functional model is outside this repository.

Alternative considered: rely only on `UIControl.function_key` and
`UITransition.function_block`. Those fields are useful cross-checks but are too
low-level to express whether a user-visible feature is intentionally not exposed
through the UI.

### Evidence runs consume journey coverage

Add `UIImplementationJourneyRun` and `UIImplementationStepEvidence`. Each run
names a feature and, optionally, the journey or entry point it verifies. Each
step names the model event/control/source/target state plus method, result,
evidence reference, and observed result. The reviewer checks that feature,
event, control, and state references match the supplied interaction model and
journey coverage.

Alternative considered: accept one free-form "manual QA passed" note. That
would not catch a missing load-existing-project branch, a skipped failure
recovery path, or an outdated validation after the model changed.

### Freshness and blindspots stay visible

Implementation evidence has a source model fingerprint or revision field. If it
is absent or mismatched, the reviewer blocks completion. Blindspots can defer
hard-to-automate branches, but only with feature/control/event scope, reason,
owner, validation boundary, and rationale.

## Risks / Trade-offs

- **Risk: The new layer feels heavy for design-only UI work** -> Gate it only
  behind implemented/runnable UI claims; model-only UI work can stop after
  journey, structure, and text hierarchy evidence.
- **Risk: Users treat a recorded manual run as permanent truth** -> Require a
  model revision/evidence freshness field and report stale or missing freshness.
- **Risk: Functional model terms differ from UI terms** -> Allow explicit
  feature contracts and pure UI action classification instead of assuming every
  control is a product feature.
- **Risk: Browser automation is unavailable for some UI surfaces** -> Accept
  manual or desktop automation evidence while requiring structured steps and
  residual blindspots for skipped branches.

## Migration Plan

1. Add OpenSpec specs and a FlowGuard self-model for the implementation
   validation gate.
2. Add implementation validation dataclasses, report, and reviewer to
   `flowguard/ui_structure.py`.
3. Export the new APIs and include them in the modeling helper surface.
4. Add focused tests for passing validation and known-bad feature, UI, evidence,
   freshness, branch, and blindspot gaps.
5. Extend the UI flow structure template to demonstrate feature contracts and
   browser/manual click-through evidence after journey coverage.
6. Update skill/docs/release checklist and sync installed skill copies.
7. Run focused tests, OpenSpec validation, FlowGuard model checks, public
   template tests, full regression, editable install checks, and shadow
   workspace import checks.
