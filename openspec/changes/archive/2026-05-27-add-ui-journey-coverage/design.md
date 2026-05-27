## Context

`UIInteractionModel` records states, controls, displays, and transitions, and
`review_ui_interaction_model(...)` catches missing initial state, missing
availability, unmapped controls, failure recovery gaps, destructive prominence,
and duplicate information/control hazards. That is necessary but not sufficient
for app-level UI completeness. A model can still pass while omitting a top-level
entry branch, leaving a declared state unreachable from launch, exposing a
forward-only action from a terminal state, or failing to name the validation
surface for a deliberately out-of-scope feature.

This change adds a separate app-level journey coverage surface. It is explicit
enough for software startup flows such as new project, load existing project,
open recent project, settings, cancel, recovery, export, and exit, while keeping
component-level UI modeling lightweight.

## Goals / Non-Goals

**Goals:**

- Distinguish local UI model coherence from complete app-level UI coverage.
- Represent launch state, entry points, feature journeys, path obligations,
  terminal states, recovery/cancel paths, and residual blindspots.
- Reject missing entry paths, unreachable path states/events, features without
  success terminals, recoverable failures without recovery/cancel/terminal
  handling, terminal states with unexplained forward actions, and blindspots
  without validation boundaries.
- Make the template demonstrate launch-to-terminal coverage with new-project
  and load-existing-project branches.
- Update skills and docs so agents cannot claim complete UI design from
  structure/text artifacts alone.

**Non-Goals:**

- Do not require journey coverage for tiny visual-only or component-local UI
  changes that do not claim app completeness.
- Do not replace browser QA, frontend implementation tests, Figma review,
  accessibility testing, or production conformance.
- Do not infer every possible product feature automatically; the model author
  must declare the app boundary and residual blindspots.
- Do not introduce external dependencies.

## Decisions

### Add a separate coverage object

Create `UIJourneyCoverage` instead of overloading `UIInteractionModel`.
`UIInteractionModel` remains the source of declared controls, states, displays,
and transitions. `UIJourneyCoverage` names the app-level obligations that must
be reachable from launch.

Alternative considered: add many optional fields to `UIInteractionModel`. That
would blur local/component modeling with app completeness and make existing
users provide app-level inventory even when they only need a local state model.

### Coverage checks use declared paths and graph reachability

The reviewer should build a transition graph from the interaction model, then
check both coverage references and graph reachability:

- launch state exists and is registered;
- every entry point references a registered control/event and starts from
  launch or a declared launch-available state;
- every feature has at least one entry point and success terminal;
- every required state and terminal is reachable from launch;
- every required event is registered;
- every recoverable failure named by a journey has recovery, cancel, or terminal
  handling;
- terminal states do not have outgoing transitions unless the transition is
  explicitly allowed as restart, export, close, recovery, cancel, or exit;
- every reachable visible/enabled actionable control has a modeled event or a
  scoped residual blindspot;
- every reachable modeled event is consumed by an entry point, feature journey,
  terminal allowance, or residual blindspot;
- every residual blindspot has feature/control/event scope, owner, validation
  boundaries, and rationale.

Alternative considered: rely only on named feature path lists. That catches
missing inventory but misses impossible or unreachable paths.

### Keep complete-UI claims opt-in and explicit

The docs and skill guidance should require journey coverage only when an agent
claims complete app-level UI modeling. Local UI structure and text hierarchy
work can still use the existing three-stage workflow, but app-level UI work
uses an expanded sequence:

```text
product intent
-> UI interaction model
-> UI journey coverage review
-> UI structure derivation
-> UI text hierarchy blueprint
-> frontend/Figma/browser handoff
```

Alternative considered: make journey coverage mandatory for every
`UIInteractionModel`. That would over-model small UI edits and make the helper
less useful for component-level workflows.

## Risks / Trade-offs

- **Risk: Users think FlowGuard discovered all product features automatically**
  -> Require a declared feature/entry inventory and residual blindspots.
- **Risk: Existing local UI tests become noisy** -> Keep the new reviewer
  separate and do not change `review_ui_interaction_model(...)` success
  semantics except where direct interaction-model findings already exist.
- **Risk: Journey coverage becomes prose-only** -> Model entry points and
  journeys as dataclasses, add known-bad tests, and include a template run that
  executes the reviewer.
- **Risk: Release claims overstate production confidence** -> Docs must say
  journey coverage is model evidence, not browser, frontend, or production
  conformance evidence.

## Migration Plan

1. Add OpenSpec and FlowGuard self-model evidence for the route gap.
2. Add journey coverage dataclasses and reviewer in `flowguard/ui_structure.py`.
3. Export the new APIs from `flowguard/__init__.py`.
4. Extend focused tests with passing app coverage and known-bad omissions.
5. Update the UI template to demonstrate launch/new/load/recovery/terminal
   coverage before structure and text hierarchy handoff.
6. Update skill/docs/README/changelog/version and sync installed skills.
7. Run focused tests, model checks, OpenSpec validation, public template tests,
   full regression, privacy scan, editable install verification, and shadow
   workspace verification before release.

Rollback before release is straightforward: remove the new helper classes,
reviewer, tests, template additions, docs, and exports. After release, remove
only through a deprecation-aware follow-up.
