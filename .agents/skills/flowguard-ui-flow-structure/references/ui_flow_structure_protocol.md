# UI Flow Structure Protocol

Use this route when UI design needs a model-first interaction structure before
visual design or frontend implementation. The route has four model/design
stages for complete app-level UI claims: build or review a UI interaction
model, review launch-to-terminal journey coverage, derive UI structure from
that model, then derive a UI text hierarchy blueprint from the reviewed
structure. It has a fifth implementation-evidence stage only when the agent
claims the running UI is implemented, runnable, or complete. Local
component-only UI work may skip journey coverage with an explicit scope reason.

## Trigger

Use UI Flow Structure when:

- the user asks how a UI's buttons, menus, controls, panels, screens, dialogs,
  inspectors, or navigation should work together;
- a UI has meaningful state transitions such as empty, loaded, running,
  failed, result-ready, review, publish, or archived;
- controls appear, disappear, enable, disable, block, recover, retry, cancel,
  or depend on other workflow stages;
- the agent needs to decide which functions are global, parent-level,
  child-level, contextual, local, destructive, terminal, or recovery actions;
- the UI needs parent/child topology, menu levels, stable toolbar placement,
  overlay hierarchy, or stage-dependent controls derived from behavior;
- the UI may show the same information or expose the same function in multiple
  places, and the agent needs to distinguish useful redundancy from clutter,
  conflict, or same-level duplication;
- the UI needs heading levels, labels, button text slots, status text,
  helper text, empty/error/recovery copy slots, or text priority derived from
  the modeled interaction and structure instead of invented late in visual
  design.
- the agent wants to claim the whole app UI is covered from launch through
  entry branches such as new project, load existing project, cancel, recover,
  export, and exit.
- the agent wants to claim the implemented/runnable UI has been opened and
  verified through browser, desktop, or manual click-through evidence.

Skip with a reason when the request is a tiny visual-only edit with no
behavior, state, navigation, or control-availability impact.

## Inputs

Collect the lightest fit-for-risk UI evidence:

- product goal and user workflow;
- existing FlowGuard product/workflow model when available;
- initial UI state;
- controls, buttons, inputs, menus, panels, dialogs, drawers, inspectors, and
  overlays;
- user events and system events;
- visible output for each event;
- information displays, charts, summary cards, labels, status text, tables, and
  other semantic content shown per state;
- UI states and parent/child state groups;
- failure, recovery, cancel, retry, rollback, terminal, and export paths;
- app-level launch state, top-level entry points, feature journeys, success
  terminals, terminal action purposes, and residual blindspots when complete UI
  coverage is claimed;
- state availability: visible, enabled, disabled, hidden controls per state;
- existing or proposed heading, label, button, status, helper, empty-state,
  error, recovery, validation, and success text when available;
- user-visible feature contracts from the product or functional model when an
  implemented/runnable UI claim is made;
- browser, desktop automation, or manual click-through evidence, including
  model revision/fingerprint and step-level event/state observations, when
  implementation completion is claimed;
- downstream validation boundaries such as scenario review, browser checks,
  implementation tests, Figma review, or design implementation review.

## Stage 1: UI Interaction Model

Represent the UI as:

```text
UI event x UI state -> Set(UI output x UI state)
```

The model should include:

- source product/workflow model id when one exists;
- `UIControl` rows for buttons, menus, inputs, status controls, and commands;
- `UIDisplayElement` rows for text, charts, tables, status cards, images, or
  other semantic information;
- `UIStateNode` rows for abstract UI states;
- `UITransition` rows for every modeled event;
- initial state and terminal states;
- failure states and recovery controls;
- destructive controls and their prominence;
- state availability matrix;
- explicit redundancy rationale when the same state repeats one semantic
  information item or exposes same-level controls for one function.

Known-bad hazards:

- a visible control has no modeled event;
- initial state is missing or unregistered;
- a transition references an unknown state or control;
- a recoverable failure state has no recovery action;
- a destructive action is promoted as global or primary;
- state availability is only implied in prose;
- chart A and text B show the same semantic information in the same state
  without a reason;
- two same-level buttons trigger the same modeled function without explaining
  why both must exist.

## Stage 2: UI Journey Coverage

For complete app-level UI claims, review launch-to-terminal coverage after the
interaction model passes and before structure derivation. Use
`UIJourneyCoverage`, `UIJourneyEntryPoint`, `UIFeatureJourney`,
`UITerminalActionAllowance`, `UIResidualBlindspot`, and
`review_ui_journey_coverage(...)` when the package API is available.

The coverage should include:

- source UI interaction model id and reviewed status;
- launch state id;
- launch-available entry points such as new project, load existing project,
  settings, cancel, export, and exit when in scope;
- feature journeys with required states, required events, success terminal
  states, failure states, recovery/cancel/exit events, validation, and
  rationale;
- every reachable visible or enabled actionable control and every reachable
  event, either owned by a journey/terminal allowance or explicitly scoped to a
  residual blindspot;
- allowed terminal actions and purposes such as restart, export, close,
  recovery, cancel, or exit;
- residual blindspots with feature/control/event scope, reason, owner,
  validation boundary, and rationale.

Known-bad hazards:

- complete app UI claim has no journey coverage;
- an entry point references an unknown control, unknown event, or non-launch
  source state;
- a visible or enabled button/control in a reachable state has no modeled event
  and no scoped residual blindspot;
- a reachable modeled event is not consumed by any feature journey, terminal
  allowance, entry point, or residual blindspot;
- a declared feature path references an unknown or unreachable state/event;
- a feature journey has no reachable success terminal;
- a recoverable failure has no named recovery, cancel, exit, or terminal
  handling;
- a terminal state exposes an outgoing action with no allowed terminal purpose;
- a residual blindspot lacks reason, owner, rationale, or validation boundary.

## Stage 3: Structure Derivation

After the UI interaction model is reviewed, and after journey coverage passes
when required, derive the interface structure:

- parent surface boundary;
- target regions, screens, menus, panels, overlays, and child components;
- state-to-region map;
- control-to-region map;
- display-to-region map;
- event-to-region map;
- parent/child hierarchy edges;
- persistent controls and stable global placement;
- contextual controls and their owning stage or child node;
- information display ownership and redundancy rationale;
- overlay placement such as modal, drawer, popover, or inspector;
- stable regions that should not move between states;
- validation boundaries and rationale.

Hierarchy recommendations should be explicit:

- first-level persistent controls belong in stable global areas such as a top
  toolbar, app shell, menu bar, or primary navigation;
- second-level contextual controls belong in the owning parent workflow area,
  inspector, side panel, or phase region;
- third-level local controls belong near the local data, row, item, or child
  state they affect;
- blocking or parent-scoped interactions belong in modal, drawer, popover,
  inspector, or inline child regions based on how they constrain the parent
  flow;
- destructive controls should be visually and structurally separated from
  ordinary primary progression.

Known-bad hazards:

- structure is derived before the UI model is reviewed;
- persistent controls are not assigned to stable global regions;
- contextual controls are assigned to global regions;
- parent/child region references are missing or unregistered;
- menu levels are chosen by visual habit rather than modeled dependency;
- repeated information is assigned to the same region without an explicit
  redundancy rationale;
- duplicate controls for the same function appear at the same hierarchy level
  without a modeled difference;
- overlay controls are not represented as blocking or scoped child regions;
- validation boundaries are missing.

## Stage 4: UI Text Hierarchy Blueprint

After the UI structure derivation is reviewed, derive the text hierarchy
blueprint with `UITextHierarchyBlueprint`, `UITextElement`,
`UITypographyToken`, and `review_ui_text_hierarchy(...)` when the package API is
available. This is not final copywriting, brand voice, final font choice, or
visual polish. It is the model-derived ownership, priority, and semantic
typography-token map for UI text slots:

- root page or surface title and its owning parent surface;
- region headings and section labels for each derived region;
- control labels for primary, secondary, contextual, local, destructive,
  recovery, cancel, retry, export, and terminal actions;
- status, progress, success, warning, failure, and terminal-state messages;
- helper, validation, empty-state, recovery, confirmation, and diagnostic text
  slots;
- semantic information labels for displays, charts, cards, tables, and
  summaries;
- text priority by hierarchy level: global, parent workflow, contextual region,
  local child item, overlay, or inline validation;
- state-to-text map that names which text appears, changes, or disappears per
  UI state;
- control-to-label map that keeps action text aligned with modeled events and
  control ownership;
- display-to-label map that keeps semantic display labels aligned with the
  display ownership map;
- redundancy rationale when the same text intent appears in multiple places.

Text hierarchy recommendations should be explicit:

- top-level headings name the current parent surface or workflow stage, not a
  local child action;
- region headings describe owned state groups, displays, or child workflows;
- primary action labels map to modeled progression events;
- destructive, terminal, and recovery action labels must expose their modeled
  consequence or recovery role;
- status text belongs to the state or region that owns the state transition;
- helper and validation text stay near the input, control, or child state they
  constrain;
- overlay text names the blocked or scoped parent interaction it interrupts.

Known-bad hazards:

- final UI copy is written before the interaction model and structure are
  reviewed;
- headings are chosen by visual size rather than parent/child structure;
- a button label does not match its modeled event or consequence;
- error or recovery text exists without a modeled failure or recovery path;
- repeated labels or messages create competing sources of truth without
  rationale;
- text ownership is ambiguous across parent, child, overlay, and local regions;
- downstream copy/design work receives only prose, not state/control/display
  maps for the text slots.

## Stage 5: UI Implementation Validation

Use this stage only when the route claims a running UI has been implemented,
is runnable, or is complete. Model, journey coverage, structure derivation, and
text hierarchy evidence are still design/model evidence; they do not prove that
the real UI was opened and clicked through.

Use `UIFeatureContract`, `UIImplementationValidation`,
`UIImplementationJourneyRun`, `UIImplementationStepEvidence`,
`UIImplementationBlindspot`, and
`review_ui_implementation_validation(...)` when the package API is available.

The validation should include:

- source feature/product model id, source UI interaction model id, source
  journey coverage id, implementation target, current model or implementation
  revision, validation boundaries, and rationale;
- feature contracts for every user-visible feature that should have a UI path;
- mappings from feature contracts to UI journeys, entry points, controls, and
  events;
- browser, desktop automation, or manual journey runs with step-level event,
  control, source-state, target-state, result, evidence reference, and observed
  state data;
- pure UI control/event classifications for actions such as close, cancel,
  expand, collapse, or export side effects when they are not product features;
- implementation blindspots with feature/control/event scope, reason, owner,
  validation boundary, and rationale.

Known-bad hazards:

- an implemented/runnable UI claim has no implementation validation;
- a user-visible feature has no UI journey, entry point, event, or blindspot;
- a reachable actionable control or modeled event has no feature owner, pure UI
  classification, run evidence, or blindspot;
- a modeled feature journey has no passed browser, desktop, or manual run;
- success evidence omits modeled failure, recovery, cancel, or exit events;
- evidence is failed, skipped, not run, stale, or lacks a model revision;
- a step references unknown controls, events, source states, or target states;
- an implementation blindspot lacks scope, reason, owner, validation boundary,
  or rationale.

## Recommendation Shape

Produce a UI structure contract with:

- UI interaction model id and evidence status;
- app-level journey coverage id and evidence status when complete app coverage
  is claimed;
- implementation validation id and evidence status when implemented/runnable UI
  completion is claimed;
- launch state, entry points, feature journeys, terminal actions, failure
  handling, and residual blindspots when journey coverage is in scope;
- parent UI surface id;
- UI states, controls, transitions, and availability matrix;
- visible information elements and semantic keys for each state;
- target regions and placements;
- hierarchy level for each region or control;
- stable placement rules;
- parent/child topology;
- recovery and terminal behavior;
- downstream validation boundaries;
- rationale for grouping and placement decisions;
- rationale for intentional repetition, such as accessibility, persistent
  navigation, summary plus details, or cross-page continuity;
- UI text hierarchy blueprint: page/surface title, region headings, labels,
  action text slots, state/status messages, helper/validation text, recovery
  and error copy slots, semantic display labels, text ownership maps, priority
  levels, and rationale for repeated text.
- implementation evidence boundary: feature contracts, journey runs, step
  evidence, model revision, pure UI actions, residual implementation
  blindspots, and remaining manual/browser validation boundaries.

## Relationship To Other Routes

Use `flowguard-code-structure-recommendation` when the next question is how to
split implementation modules or files from a functional model.

Use `flowguard-structure-mesh` when an existing large code surface is being
refactored and needs facade, dependency, parity, public-entrypoint, or release
evidence.

Use frontend, Figma, Browser, and design review workflows after the UI flow,
required journey coverage, structure, and UI text hierarchy contracts exist.
When those workflows produce browser, desktop, or human click-through evidence,
feed that evidence back into UI implementation validation before claiming the
running UI is complete.

## Completion Standard

The route is complete when:

- the UI interaction model has initial state, states, controls, transitions,
  displayed information, failure/recovery behavior, terminal behavior,
  availability, duplicate/redundancy review, validation, and rationale;
- complete app-level UI claims have journey coverage with launch state, entry
  points, feature journeys, reachable success terminals, failure recovery/cancel
  handling, terminal action allowances, residual blindspots, validation, and
  rationale;
- the UI structure derivation names parent/child UI regions, menu levels,
  persistent/global controls, contextual controls, overlay hierarchy, stable
  layout positions, display ownership, validation boundaries, and rationale;
- the UI text hierarchy blueprint names page/surface titles, region headings,
  control labels, action text slots, status/state messages, helper/validation
  text, error/recovery copy slots, semantic display labels, state/control/text
  ownership, priority levels, and rationale for repeated text;
- implemented/runnable UI claims have implementation validation that aligns
  user-visible feature contracts, reviewed UI journeys, real click-through
  evidence, model revision/freshness, pure UI actions, and residual
  implementation blindspots;
- known-bad layout-only, missing-journey-coverage, missing-entry,
  unreachable-feature-path, missing-success-terminal, unhandled-failure,
  terminal-forward-action, visible-control-without-event,
  uncovered-reachable-event, unmodeled-control, missing-recovery,
  unstable-global, repeated-information, duplicate-control, wrong-level,
  unowned-text, missing-implementation-run, stale-implementation-evidence, and
  implementation-control-without-feature-owner hazards are rejected or
  explicitly out of scope.
