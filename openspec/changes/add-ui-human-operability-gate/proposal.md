## Why

FlowGuard now blocks many UI last-mile false claims: visible controls must be
inventoried, enabled controls must have real functional chains, and MATLAB
callback semantics must be modeled. A remaining gap is that a UI can still be
technically modeled and wired while being hard for a person to understand. The
same feature may appear through competing buttons, path fields and native
pickers may not explain their relationship, static status can look clickable,
keyboard/focus behavior may be undefined, and dialog returns may leave users
without a clear next step.

This change adds a human-operability layer. It treats user tasks as the bridge
between functional capability and UI structure: every in-scope user-visible
feature must map to a user task, every task must map to a UI journey/control
path, and every UI path must expose understandable affordance, action grammar,
region ownership, dialog return, keyboard/focus, and walkthrough evidence.

## What Changes

- Add a `UIUserTaskCoverageLedger` and `UIUserTaskFrame` family so FlowGuard
  tracks the full set of in-scope user tasks, not just one example task.
- Add traceability from functional model/features to user tasks, UI journeys,
  controls, functional chains, and evidence.
- Add human-operability contracts for visible affordance, action grammar,
  semantic regions, dialog/window returns, keyboard/focus behavior, and
  walkthrough scenarios.
- Add review helpers that reject confusing UI cases even when controls are
  present and technically wired.
- Extend Model Miss Review so user-observed confusion is a model miss class,
  not a local visual cleanup.
- Extend PlanDetailing, DevelopmentProcessFlow, RiskEvidenceLedger,
  ClosureContract, and AgentWorkflowRehearsal so done/release claims cannot
  bypass human-operability evidence.
- Update UI Flow skills, templates, docs, public API surface, and tests.

## Scope

In scope:

- FlowGuard Python model/helper APIs.
- UI Flow Structure skill prompt and protocol.
- Public templates and docs.
- OpenSpec and FlowGuard self-model evidence.
- Local installed-skill, editable-install, formal-repo, shadow-workspace, and
  local-git synchronization.

Out of scope:

- Reworking a concrete application UI.
- Remote push, remote tag push, or GitHub Release.
- Destructive cleanup of peer-agent work.

## Claim Boundary

After this change, FlowGuard can claim that the local route, APIs, skills,
templates, and validation gates support human-operability modeling. It cannot
claim that any target application's UI is human-operable until that application
has current task coverage, affordance, dialog, keyboard, walkthrough, and
implementation evidence.
