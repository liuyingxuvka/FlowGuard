# UI Flow Structure Protocol

Use this route when UI design needs a model-first interaction structure before
visual design or frontend implementation. The route has two stages: build or
review a UI interaction model, then derive UI structure from that model.

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
  overlay hierarchy, or stage-dependent controls derived from behavior.
- the UI may show the same information or expose the same function in multiple
  places, and the agent needs to distinguish useful redundancy from clutter,
  conflict, or same-level duplication.

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
- state availability: visible, enabled, disabled, hidden controls per state;
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

## Stage 2: Structure Derivation

After the UI interaction model is reviewed, derive the interface structure:

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

## Recommendation Shape

Produce a UI structure contract with:

- UI interaction model id and evidence status;
- parent UI surface id;
- UI states, controls, transitions, and availability matrix;
- visible information elements and semantic keys for each state;
- target regions and placements;
- hierarchy level for each region or control;
- stable placement rules;
- parent/child topology;
- recovery and terminal behavior;
- downstream validation boundaries;
- rationale for grouping and placement decisions.
- rationale for intentional repetition, such as accessibility, persistent
  navigation, summary plus details, or cross-page continuity.

## Relationship To Other Routes

Use `flowguard-code-structure-recommendation` when the next question is how to
split implementation modules or files from a functional model.

Use `flowguard-structure-mesh` when an existing large code surface is being
refactored and needs facade, dependency, parity, public-entrypoint, or release
evidence.

Use frontend, Figma, Browser, and design review workflows after the UI flow
structure contract exists.

## Completion Standard

The route is complete when:

- the UI interaction model has initial state, states, controls, transitions,
  displayed information, failure/recovery behavior, terminal behavior,
  availability, duplicate/redundancy review, validation, and rationale;
- the UI structure derivation names parent/child UI regions, menu levels,
  persistent/global controls, contextual controls, overlay hierarchy, stable
  layout positions, display ownership, validation boundaries, and rationale;
- known-bad layout-only, unmodeled-control, missing-recovery, unstable-global,
  repeated-information, duplicate-control, and wrong-level hazards are rejected
  or explicitly out of scope.
