# UI Flow Structure Protocol

Use this route when UI design needs a model-first interaction structure before
visual design or frontend implementation. The route has five model/design
stages for complete app-level UI claims: build or review a UI interaction
model, review visible UI surface, review launch-to-terminal journey coverage,
derive UI structure from that model, then derive a UI text hierarchy blueprint
from the reviewed structure. It has a later implementation-evidence stage only
when the agent claims the running UI is implemented, runnable, or complete. Local
component-only UI work may skip journey coverage with an explicit scope reason.
When a UI transition-test coverage claim is made, project the reviewed
`UIInteractionModel.transitions` into a transition coverage matrix before
claiming test coverage.

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
- visible controls, status text, helper copy, placeholders, metadata, or
  disabled-state reasons need to stay user-facing and owned by state/control
  purpose before visual design;
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
- the UI already exists or can run, and the agent needs to account the real
  visible buttons, inputs, dropdowns, tables, displayed fields, status text,
  dialogs, and regions before claiming the model covers it.
- the UI may technically be wired but still confusing to a human, so supported
  user-visible features must be covered by task frames, primary controls,
  action grammar, region semantics, dialog/window return semantics,
  keyboard/focus rules, and walkthrough evidence.

Skip with a reason when the request is a tiny visual-only edit with no
behavior, state, navigation, or control-availability impact.

## Inputs

Collect the lightest fit-for-risk UI evidence:

- product goal and user workflow;
- existing FlowGuard product/workflow model when available;
- initial UI state;
- controls, buttons, inputs, menus, panels, dialogs, drawers, inspectors, and
  overlays;
- an observed real-surface inventory from the running page/window when
  available, including each visible item id, kind, label/text, enabled state,
  region, and evidence reference;
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
- user task inventory: every supported feature, every task a user can perform,
  task-to-feature links, UI path links, primary controls, required feedback,
  cancel/error behavior, keyboard/focus expectations, and scoped-out tasks;
- affordance, action grammar, region semantic, dialog/window return,
  keyboard/focus, and human walkthrough observations when human-operable UI
  confidence is claimed;
- browser, desktop automation, or manual click-through evidence, including
  model revision/fingerprint and step-level event/state observations, when
  implementation completion is claimed;
- render or implementation evidence kinds such as screenshot, browser
  click-through, DOM text, computed style, geometry, accessibility/ARIA,
  runtime trace/log, test result, or manual observation;
- geometry/layout observations for overflow, overlap, bounds, focus,
  keyboard reachability, and scroll ownership when layout confidence is in
  scope;
- hot-path feedback, cold-path work, stale-result guards,
  cancellation/coalescing, and stable-region rules when responsiveness is in
  scope;
- transition coverage matrix ids or scoped-out reasons when claiming tests
  cover the modeled UI transitions;
- downstream validation boundaries such as scenario review, browser checks,
  implementation tests, Figma review, or design implementation review.

## Stage 0: Observed Real-Surface Inventory

For existing, migrated, or runnable UI, the observed real surface is the first
hard gate. Before declaring UI modeling complete, automatically list the actual
visible UI items: buttons, inputs, dropdowns, tables, displayed fields, status
text, helper copy, dialogs, menus, toolbars, panels, and visible regions.

Use `UIObservedSurfaceInventory`, `UIObservedSurfaceItem`, and
`review_ui_observed_surface_inventory(...)` when the package API is available.

The inventory must map every observed visible item to a modeled `UIControl`,
`UIDisplayElement`, or `UIVisibleSurfaceItem`, or record a blindspot with an
owner, reason, and validation boundary. Enabled actionable items without a
model mapping block UI model completion.

Known-bad hazards:

- the model lists intended controls but never counts the real page/window;
- a visible button, picker, input, table, field, or status text is not mapped;
- an enabled visible control is treated as covered because its label matches;
- a blindspot has no owner, reason, or follow-up validation boundary.

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

## Stage 2: Visible Surface Review

Review what the user actually sees before treating the structure or visual
design as ready. Use `UIVisibleSurface`, `UIVisibleSurfaceItem`, and
`review_ui_visible_surface(...)` when the package API is available.

The visible surface should include:

- controls, helper copy, status text, placeholders, metadata, and
  disabled-state reasons that are visible in each modeled state;
- the state, region, control, or display owner for each visible item;
- user-facing purpose and rationale for helper/status/metadata text;
- user-understandable disabled reasons for disabled controls;
- a rationale when implementation-facing terms are intentionally visible to
  users.

Known-bad hazards:

- visible implementation terms such as mock, backend, hydration, debug route,
  dataset id, or render strategy leak to users without a user-facing reason;
- a disabled control is visible without a reason the user can understand;
- placeholder text is presented as completed product functionality;
- helper copy repeats a nearby label or button without adding user value;
- one state exposes multiple primary empty/loading/pending/error/success/status
  messages that compete with each other.

## Stage 3: UI Journey Coverage

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

## Stage 4: Structure Derivation

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

## Stage 5: UI Text Hierarchy Blueprint

After the UI structure derivation is reviewed, derive the text hierarchy
blueprint with `UITextHierarchyBlueprint`, `UITextElement`,
`UITypographyToken`, and `review_ui_text_hierarchy(...)` when the package API is
available. This is not final copywriting, brand voice, final font choice, or
visual polish. It is the model-derived ownership, priority, and semantic
typography-token map for UI text slots:

The blueprint should keep helper copy, placeholder text, status text,
empty/loading/error messages, metadata labels, and disabled reasons tied to an
owning state, region, control, or display purpose. It should keep helper copy
below the main task unless escalation is justified, avoid treating placeholder
text as completed feature proof, and require user value when helper copy
repeats a nearby label.

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

Visual handoff hygiene should stay soft but explicit:

- semantic hierarchy levels are not a command to create one visual font size per
  level;
- labels, helper text, status text, metadata, and panel text with similar jobs
  should usually reuse visual treatments;
- when text looks different through size, weight, color role, spacing, or
  placement, name the job it performs: primary focus, region scan, local
  control, warning, helper text, quiet metadata, or brand expression;
- prefer grouping, spacing, weight, color role, or placement before inventing a
  one-off visual text style;
- preserve expressive hero, editorial, brand-heavy, warning, or state-critical
  exceptions when their attention or meaning role is clear.

Known-bad hazards:

- final UI copy is written before the interaction model and structure are
  reviewed;
- headings are chosen by visual size rather than parent/child structure;
- a button label does not match its modeled event or consequence;
- error or recovery text exists without a modeled failure or recovery path;
- repeated labels or messages create competing sources of truth without
  rationale;
- text ownership is ambiguous across parent, child, overlay, and local regions;
- every semantic text role becomes a separate visual text style without a clear
  job;
- nearby text with the same local function uses unrelated sizes, weights, or
  color roles only to create artificial design variation;
- downstream copy/design work receives only prose, not state/control/display
  maps for the text slots.

## Stage 6: Human-Operability Validation

Before implementation validation, require a human-operability review when the
claim says the UI is usable, human-operable, release-ready, or understandable.
Use `UIUserTaskFrame`, `UIUserTaskCoverageLedger`,
`UIRegionSemanticMap`, `UIAffordanceContract`, `UIActionGrammar`,
`UIDialogWindowContract`, `UIKeyboardFocusContract`,
`UIHumanWalkthroughScenario`, `UIHumanWalkthroughStep`,
`UIHumanOperabilityAssessment`, and `review_ui_human_operability(...)` when the
package API is available.

The human-operability package should include:

- all supported user-visible features from the functional/product model, not a
  single convenient task sample;
- user task frames for every task the UI promises to support, with user goal,
  source feature, entry state, main/alternate/cancel/error paths, success
  state, visible feedback, required controls/displays/dialogs, keyboard
  contract, evidence refs, and rationale;
- links from feature -> task -> UI journey/control/functional chain, plus
  scoped-out feature/task rows with owner and validation boundary;
- primary control ownership for each task, so a prominent button cannot float
  outside the task model;
- region semantic maps for input, action, result, status, recovery,
  navigation, and dialog areas;
- affordance contracts for visible items that look clickable, editable,
  selectable, read-only, status-only, or decorative;
- action grammar for each semantic intent, including primary action,
  alternate actions, conflicts, preconditions, next state, feedback, and
  duplicate policy;
- dialog/window contracts for native file pickers, directory pickers, save
  dialogs, OS shell opens, custom modals, popovers, and drawers, including
  success, cancel, error, focus return, feedback, native/manual boundary, and
  evidence;
- keyboard/focus contracts for Tab order, Enter, Escape, disabled-control skip,
  focus return, and error focus;
- human walkthroughs that record visible prompt, user action, expected
  feedback, actual feedback, evidence ref, confusion, and mitigation.

Known-bad hazards:

- task coverage only models one happy path while other supported features still
  have buttons, fields, or journeys;
- a primary button has no owning user task;
- a visible item looks selectable/clickable but is actually read-only, status,
  display, or decorative without a disposition;
- two controls are both primary for the same user intent in the same state;
- native dialog success is modeled but cancel, error, selected path, focus
  return, or feedback is missing;
- keyboard users cannot reach the same task, return focus after dialog, or
  recover from errors;
- walkthrough evidence records confusion but no mitigation.

## Stage 7: UI Implementation Validation

Use this stage only when the route claims a running UI has been implemented,
is runnable, or is complete. Model, journey coverage, structure derivation, and
text hierarchy evidence are still design/model evidence; they do not prove that
the real UI was opened and clicked through.

Use `UIFeatureContract`, `UIImplementationValidation`,
`UIImplementationJourneyRun`, `UIImplementationStepEvidence`,
`UIImplementationBlindspot`, and
`review_ui_implementation_validation(...)` when the package API is available.
Use `UIRenderEvidenceSet`, `UIRenderEvidence`, and
`review_ui_render_evidence(...)` when the route needs evidence-kind review.
Use `UIControlFunctionalChainSet`,
`review_ui_control_functional_chains(...)`, `MATLABBaselineCallbackGate`, and
`review_matlab_baseline_callback_gate(...)` when enabled controls or MATLAB
migration semantics are in scope.

The validation should include:

- source feature/product model id, source UI interaction model id, source
  journey coverage id, implementation target, current model or implementation
  revision, validation boundaries, and rationale;
- feature contracts for every user-visible feature that should have a UI path;
- mappings from feature contracts to UI journeys, entry points, controls, and
  events;
- every reachable enabled actionable control from the visible surface map:
  buttons, menus, tabs, icon buttons, toggles, inputs, file pickers, dialogs,
  context menus, and destructive/recovery controls must have run evidence,
  pure-UI classification, or an implementation blindspot;
- every enabled control that is not pure UI must have this functional chain:
  visible control -> UI event -> code owner -> backend/local function -> UI
  state update -> click/test evidence;
- API existence, route existence, and label matching are insufficient unless
  the click evidence shows the functional chain updates the UI state;
- MATLAB migrations must preserve callback semantics for `uigetfile`,
  `uigetdir`, `winopen`, and buttons with no callback, including select,
  cancel, chosen path, load result, open/shell effect, and error path branches;
- browser, desktop automation, or manual journey runs with step-level event,
  control, source-state, target-state, result, evidence reference, and observed
  state data;
- native file pickers, save dialogs, permission prompts, and manual-only UI
  branches need structured event/result/evidence-reference rows and a scoped
  boundary; a prose note such as "checked manually" is not pass evidence;
- render evidence with declared evidence kinds such as screenshot, browser
  click-through, DOM text, computed style, geometry, accessibility/ARIA,
  runtime trace/log, test result, or manual observation;
- pure UI control/event classifications for actions such as close, cancel,
  expand, collapse, or export side effects when they are not product features;
- implementation blindspots with feature/control/event scope, reason, owner,
  validation boundary, and rationale.

Known-bad hazards:

- an implemented/runnable UI claim has no implementation validation;
- a user-visible feature has no UI journey, entry point, event, or blindspot;
- a reachable enabled button, menu item, icon button, input, tab, toggle,
  picker, or dialog action is never clicked and is not scoped as pure UI or a
  blindspot;
- an enabled control has only an API or label proof and no functional chain;
- MATLAB picker/open/no-callback behavior models success but omits cancel,
  error, selected-path, or no-op disposition;
- a reachable actionable control or modeled event has no feature owner, pure UI
  classification, run evidence, or blindspot;
- a modeled feature journey has no passed browser, desktop, or manual run;
- manual/native-dialog evidence has no structured step row, observed result,
  evidence reference, or boundary;
- success evidence omits modeled failure, recovery, cancel, or exit events;
- evidence is failed, skipped, not run, stale, or lacks a model revision;
- render evidence lacks an evidence kind, uses an unknown kind, lacks an
  evidence reference, or is stale for the current model revision;
- a step references unknown controls, events, source states, or target states;
- an implementation blindspot lacks scope, reason, owner, validation boundary,
  or rationale.

## Stage 8: Geometry And Responsiveness Evidence

Use this stage when layout or responsiveness confidence is in scope. Use
`UIGeometryLayoutEvidenceSet`, `UIGeometryLayoutEvidence`, and
`review_ui_geometry_layout_evidence(...)` for geometry/layout evidence. Use
`UIResponsivenessContract`, `UIHotPathAction`, `UIColdPathWork`,
`UIStableRegionRule`, and `review_ui_responsiveness_contract(...)` for
hot/cold path evidence.

Geometry evidence should cover text overflow, control overlap, viewport or
container bounds, focus reachability, keyboard reachability, and scroll owner.
Responsiveness contracts should name immediate hot-path feedback, deferred
cold-path work, stale-result guards or cancellation/coalescing rules, and
stable regions that must not drift across unrelated input changes.

Known-bad hazards:

- text overflows its container or controls overlap;
- dialogs, popovers, menus, or panels exceed the declared viewport/container;
- focus or keyboard paths are unreachable;
- scroll ownership is unclear;
- a hot-path click has no immediate feedback target;
- cold-path work can overwrite a newer state because no stale guard,
  cancellation rule, or coalescing rule exists;
- a stable region has no preservation rule.

## Stage 9: Transition Coverage Projection

Use this stage when the claim says tests cover modeled UI transitions. Project
the reviewed interaction model with `ui_interaction_model_to_transition_coverage(...)`.
Small matrices can feed Model-Test Alignment directly through
`transition_coverage_to_model_obligations(...)` and
`transition_coverage_to_code_contracts(...)`; large browser-heavy matrices can
feed TestMesh through `transition_coverage_to_required_leaf_cell_ids(...)`.
Each transition should carry the visible event/control, source state, target
state, handler/function block, and code contract or runtime node id that owns
the transition. The projection is not implementation evidence by itself. It
creates stable model obligation, code contract, and cell targets for browser,
desktop, or manual evidence.

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
- visible-surface inventory with helper copy, status text, placeholders,
  metadata, disabled reasons, owners, and user-facing purpose;
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
- human-operability boundary: supported feature inventory, user task coverage
  ledger, primary control ownership, region semantic map, affordance contracts,
  action grammar, dialog/window return semantics, keyboard/focus contracts,
  walkthrough results, confusion mitigations, and scoped-out tasks/features.
- implementation evidence boundary: feature contracts, journey runs, step
  evidence, render evidence kinds, model revision, pure UI actions, residual
  implementation blindspots, and remaining manual/browser validation
  boundaries.
- geometry and responsiveness evidence when claimed: overflow/overlap/bounds,
  focus and keyboard reachability, scroll owner, hot-path feedback, cold-path
  stale guards, and stable-region preservation.
- transition coverage boundary when model-code-test coverage is claimed:
  projected cell ids, owner code contract ids, runtime node ids, required test
  kinds, evidence targets, and scoped-out cells with reasons.

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
- visible surface has user-facing owners and purposes for controls, helper
  copy, status text, placeholders, metadata, and disabled reasons, with
  internal implementation terms kept out of the UI unless explicitly justified;
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
- human-operability validation covers every supported user-visible task and
  links function model features to task frames, UI journeys, primary controls,
  functional chains, feedback, cancel/error behavior, region semantics,
  affordance, action grammar, dialog/window returns, keyboard/focus, and
  walkthrough evidence;
- implemented/runnable UI claims have implementation validation that aligns
  user-visible feature contracts, reviewed UI journeys, real click-through
  evidence, screenshot/DOM/geometry/accessibility/runtime/test/manual evidence
  kinds when used, model revision/freshness, pure UI actions, and residual
  implementation blindspots;
- layout or responsiveness claims have geometry evidence and hot/cold path
  contracts for the declared boundary;
- known-bad layout-only, missing-journey-coverage, missing-entry,
  unreachable-feature-path, missing-success-terminal, unhandled-failure,
  terminal-forward-action, visible-control-without-event,
  uncovered-reachable-event, unmodeled-control, missing-recovery,
  unstable-global, repeated-information, duplicate-control, wrong-level,
  unowned-text, visible-internal-terminology, missing-disabled-reason,
  missing-render-evidence-kind, geometry-overflow/overlap, missing-hot-feedback,
  missing-cold-path-stale-guard, missing-implementation-run,
  stale-implementation-evidence, and implementation-control-without-feature-owner
  hazards are rejected or explicitly out of scope.
