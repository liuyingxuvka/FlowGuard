# flowguard-ui-flow-structure Specification

## Purpose
This capability defines FlowGuard's Flowguard Ui Flow Structure behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: UI interaction model is created before UI structure derivation
The system SHALL provide a UI interaction model surface that represents the UI
as `UI event x UI state -> Set(UI output x UI state)` before deriving a UI
structure blueprint. For complete app-level UI claims, the system SHALL also
review UI journey coverage between the interaction model and structure
derivation. For implemented or runnable UI completion claims, the system SHALL
review implementation validation after the model, journey coverage, structure,
and text hierarchy evidence exists.

#### Scenario: UI flow model records initial state and transitions
- **WHEN** a UI flow structure route models an interface
- **THEN** the model includes an initial UI state, state nodes, control events,
  transitions, and terminal or recoverable states before structure derivation

#### Scenario: Complete app UI requires journey coverage
- **WHEN** an agent claims that an app-level UI has been modeled completely
- **THEN** the route reviews launch-to-terminal journey coverage before deriving
  UI structure or handing the contract to visual design or implementation

#### Scenario: Implemented UI requires real execution evidence
- **WHEN** an agent claims that the running UI has been implemented completely
- **THEN** the route reviews implementation validation evidence that aligns the
  feature contracts, UI journey coverage, and browser/manual click-through
  records before accepting the completion claim

### Requirement: UI controls and events are mapped to model behavior
The system SHALL map controls, events, and button effects to UI state
transitions and FlowGuard FunctionBlocks or equivalent modeled UI actions.

#### Scenario: Control has modeled effect
- **WHEN** a button, menu item, or input action is included in the UI model
- **THEN** the model identifies the event, owning control, source state,
  resulting state, visible output, and modeled action or FunctionBlock

#### Scenario: Unmapped control is rejected
- **WHEN** a visible control has no modeled event or transition
- **THEN** the UI interaction model review reports the control as unmodeled

### Requirement: UI information and control redundancy is reviewed
The system SHALL represent semantic information displays and control function
keys so redundant UI content or overlapping same-level controls can be checked
instead of accepted as arbitrary layout.

#### Scenario: Duplicate same-state information requires rationale
- **WHEN** one UI state shows two display elements with the same semantic
  information key
- **THEN** the UI interaction model review reports duplicate information unless
  the repetition has an explicit redundancy rationale or duplicate group

#### Scenario: Duplicate same-level control function requires rationale
- **WHEN** one UI state exposes multiple controls at the same hierarchy level
  for the same modeled function
- **THEN** the UI interaction model review reports overlapping controls unless
  the repetition has an explicit redundancy rationale or duplicate group

#### Scenario: Region repeats information without reason
- **WHEN** a structure derivation places multiple displays with the same
  semantic information key in one region
- **THEN** the structure review reports duplicate regional information unless
  the repetition is explicitly justified

### Requirement: State availability is explicit
The system SHALL represent which controls are visible, enabled, disabled, or
hidden, and which semantic information displays are visible, in each relevant
UI state.

#### Scenario: Stage-dependent action is represented
- **WHEN** an action is available only after another flow phase completes
- **THEN** the state availability matrix records the dependency and the states
  where the action is enabled or unavailable

#### Scenario: Terminal state does not expose forward-only action
- **WHEN** a UI state is terminal
- **THEN** the review reports a finding if a forward-only action remains
  enabled without an explicit restart, export, close, or recovery purpose

### Requirement: Failure and recovery paths are modeled
The system SHALL identify failure states and provide modeled recovery,
rollback, retry, cancel, or diagnostic actions when recovery is possible.

#### Scenario: Failure state has recovery action
- **WHEN** a transition can enter a recoverable failure state
- **THEN** the UI model includes at least one recovery action or explains why
  the state is terminal

#### Scenario: Missing recovery is rejected
- **WHEN** a recoverable failure state has no recovery, diagnostic, or terminal
  explanation
- **THEN** the UI interaction model review reports missing failure recovery

### Requirement: UI structure is derived from the UI interaction model
The system SHALL derive UI parent/child nodes, persistent controls, contextual
controls, navigation, regions, panels, and control tiers from the reviewed UI
interaction model.

#### Scenario: Parent and child nodes are derived
- **WHEN** the UI flow contains state groups or dependency chains
- **THEN** the structure derivation identifies parent nodes, child nodes,
  covered states, covered controls, and rationale

#### Scenario: Global control remains stable
- **WHEN** a control is marked persistent or global in the model
- **THEN** the structure derivation places it in a stable global region rather
  than a phase-only child area

#### Scenario: Contextual control is scoped to its phase
- **WHEN** a control depends on a particular state or parent flow
- **THEN** the structure derivation assigns it to the matching contextual
  region, panel, or child node

### Requirement: UI hierarchy recommendations are explicit
The system SHALL convert modeled parent/child UI topology into explicit
hierarchy and placement recommendations such as first-level persistent menus,
second-level contextual regions, third-level local controls, modal or drawer
overlays, stable toolbar positions, and layout areas that must not drift across
states.

#### Scenario: Menu levels are derived from function topology
- **WHEN** a modeled function is global, parent-level, child-level, or local to
  a sub-state
- **THEN** the structure derivation recommends the matching menu or control
  level and records the reason

#### Scenario: Layout positions remain stable across states
- **WHEN** a control or region is persistent across multiple UI states
- **THEN** the structure derivation marks its placement as stable so later
  visual design does not move it arbitrarily between screens

#### Scenario: Overlay hierarchy is derived from blocking flow
- **WHEN** a modeled action temporarily blocks or scopes the parent flow
- **THEN** the structure derivation identifies whether the interaction belongs
  in a modal, drawer, inspector, popover, or inline child region

### Requirement: UI flow structure is a standalone Codex satellite skill
The repository SHALL provide a directly invokable
`flowguard-ui-flow-structure` Codex skill while preserving
`model-first-function-flow` as the kernel for applicability, hard gates, and
ambiguous routing.

#### Scenario: Direct UI model request invokes satellite
- **WHEN** a user asks Codex to model UI button flows, UI state transitions, or
  model-derived UI structure from a workflow
- **THEN** Codex can invoke `flowguard-ui-flow-structure` directly

#### Scenario: Ambiguous UI work returns to kernel
- **WHEN** a UI request is visual-only, trivial, or unclear about behavior and
  state impact
- **THEN** the satellite routes the task back to `model-first-function-flow` or
  skips with a reason according to the kernel guidance

### Requirement: Visual design and frontend implementation remain separate
The UI flow structure route SHALL NOT replace visual design, Figma execution,
frontend implementation, browser QA, design implementation review, accessibility
testing, or production conformance. Complete app-level UI model claims SHALL
remain bounded to declared journey coverage and residual blindspots. Complete
implemented UI claims SHALL additionally remain bounded to declared
implementation validation evidence and residual implementation blindspots.

#### Scenario: Route hands off after structure contract
- **WHEN** the UI interaction model, app-level journey coverage when required,
  and structure derivation are complete
- **THEN** the resulting UI structure contract can be handed to frontend,
  Figma, or design review workflows without claiming visual or implementation
  completeness

#### Scenario: Journey coverage does not imply production conformance
- **WHEN** UI journey coverage passes for the declared model boundary
- **THEN** the route still reports browser, frontend, accessibility, and
  production conformance as separate downstream validation surfaces

#### Scenario: Implementation validation consumes downstream evidence
- **WHEN** browser automation, desktop automation, or human click-through
  evidence is available for the implemented UI
- **THEN** the route records that evidence in implementation validation instead
  of treating downstream QA prose as proof of model completeness

### Requirement: UI text hierarchy handoff guides visual review
The FlowGuard UI Flow Structure route SHALL hand off text hierarchy evidence to
frontend, Figma, design-review, and design-iteration workflows with soft
typography hygiene guidance instead of treating the semantic hierarchy as final
visual styling.

#### Scenario: Handoff names downstream typography hygiene
- **WHEN** the route produces or references a UI text hierarchy blueprint before
  frontend implementation or visual design
- **THEN** the route guidance tells downstream workflows to preserve calm
  hierarchy, reuse visual text treatments for similar text jobs, and explain
  intentional visual differences

#### Scenario: Implementation review checks hierarchy calm without hard caps
- **WHEN** a running UI or screenshot is reviewed after a UI text hierarchy
  blueprint exists
- **THEN** the review may flag chaotic one-off text treatments as actionable
  design findings while avoiding a fixed maximum font-size rule

### Requirement: UI transitions bind visible events, code, and tests

UI Flow Structure SHALL route broad UI transition confidence through model,
code, and test bindings by default.

#### Scenario: UI transition is claimed covered
- **WHEN** a UI transition cell is used in a full confidence claim
- **THEN** the claim identifies the visible event/control, code contract or
  handler boundary, and runnable evidence for that transition.

### Requirement: UI transitions project to transition coverage cells
UI Flow Structure SHALL allow modeled UI transitions to be projected into transition coverage cells before runnable UI completion claims.

#### Scenario: UI transition becomes coverage cell
- **WHEN** a UI transition declares event id, source state, target state, output, and function block
- **THEN** FlowGuard can project it to a transition coverage cell with a stable target id

#### Scenario: Runnable UI evidence targets transition cells
- **WHEN** implemented UI completion is claimed
- **THEN** browser, desktop, or manual click-through evidence can be linked to projected transition cell ids
- **AND** missing failure, recovery, cancel, or terminal transition evidence remains visible

### Requirement: UI transition projection does not replace UI journey review
Transition coverage projection SHALL support UI implementation evidence but SHALL NOT replace UI journey coverage, structure derivation, text hierarchy, or residual blindspot reporting.

#### Scenario: Journey gap remains visible
- **WHEN** transition cells are generated but the UI journey coverage still misses a reachable event
- **THEN** the UI route reports the journey gap instead of accepting transition projection as complete UI coverage

### Requirement: User task coverage ledger precedes human-operable UI claims
FlowGuard UI Flow Structure SHALL require a user task coverage ledger before a
UI can be called human-operable, release-ready, or fully covered for user-facing
functionality. The ledger MUST account every in-scope user-visible functional
capability, user task, task flow, UI journey/control path, functional chain, and
evidence boundary.

#### Scenario: Feature maps to task
- **WHEN** a user-visible feature or functional capability is in scope
- **THEN** the ledger requires at least one mapped user task or an explicit
  out-of-scope reason

#### Scenario: Task maps to UI path
- **WHEN** a user task is in scope
- **THEN** it requires a task frame with entry, main, alternate, cancel, error,
  success, feedback, and UI journey/control links

#### Scenario: UI primary control has no task owner
- **WHEN** a visible primary control is in scope
- **AND** it maps to no user task
- **THEN** UI Flow Structure blocks human-operable and release-ready claims

### Requirement: Human-operability contracts align perceived UI with actual UI
FlowGuard UI Flow Structure SHALL model perceived role, actual role, visual
cue, expected action, expected result, region ownership, action grammar,
dialog/window return, keyboard/focus behavior, and walkthrough evidence before
human-operable UI claims.

#### Scenario: Static item looks actionable
- **WHEN** a visible item is perceived as a button, input, or link
- **AND** its actual role is readonly, status, display, or container
- **THEN** the operability review requires a safe mismatch disposition or
  blocks broad UI confidence

#### Scenario: Action grammar has duplicate primary controls
- **WHEN** two same-state same-level controls express the same semantic action
- **THEN** the review requires one primary action and a rationale for alternates
  or duplicate groups

#### Scenario: Dialog return semantics are incomplete
- **WHEN** a task enters a native dialog, file picker, save dialog, OS shell, or
  modal window
- **THEN** the review requires success, cancel, error, focus-return, feedback,
  and manual/native boundary semantics

#### Scenario: Keyboard path is undefined
- **WHEN** a task is claimed human-operable
- **THEN** Tab order, default Enter behavior, Escape behavior, disabled-skip
  policy, and focus return must be defined or explicitly out of scope

#### Scenario: Walkthrough reports confusion
- **WHEN** a walkthrough step marks user confusion
- **THEN** the review blocks human-operable confidence unless mitigation,
  rationale, or a scoped blindspot is recorded

### Requirement: UI Flow Structure routes by UI work mode
FlowGuard UI Flow Structure SHALL classify each non-trivial UI task as greenfield, source-based, or mixed before requiring source-baseline evidence.

#### Scenario: Greenfield UI uses target task evidence
- **WHEN** a UI task has no existing source authority and is declared greenfield
- **THEN** UI Flow Structure requires product/user goals, supported task frames, target UI rationale, visible-surface coverage, functional chains, human-operability evidence, and implementation validation when claimed
- **AND** it does not require source-baseline mapping evidence

#### Scenario: Source-based UI uses source-baseline evidence first
- **WHEN** a UI task replaces, migrates, reproduces, or intentionally changes an existing source authority
- **THEN** UI Flow Structure requires a reviewed source-baseline model and target mapping before target UI completeness can be claimed

#### Scenario: Mixed UI separates source and new scope
- **WHEN** a UI task includes both source-based and greenfield areas
- **THEN** source-based areas require source-baseline mapping and greenfield areas require product/user-task rationale

### Requirement: UI Flow Structure compares source, target, and observed UI
FlowGuard UI Flow Structure SHALL compare Source Baseline, Target UI, and Observed UI for source-based scopes instead of accepting target-model self-consistency alone.

#### Scenario: Observed matches wrong target
- **WHEN** observed UI evidence matches the target model
- **AND** the target model has unapproved drift from the source baseline
- **THEN** UI Flow Structure blocks broad source-based UI confidence

#### Scenario: Source item has approved replacement
- **WHEN** a source item is replaced, hidden, moved, deleted, or deferred
- **AND** the target mapping includes a current disposition, rationale, and evidence boundary
- **THEN** UI Flow Structure may treat that source difference as accounted for

### Requirement: Generic source interactions replace source-specific callback gates
FlowGuard UI Flow Structure SHALL model file pickers, directory pickers, save dialogs, external opens, custom dialogs, commands, navigation, and no-handler controls with generic source interaction semantics.

#### Scenario: Source interaction branch is missing
- **WHEN** a source-based UI interaction requires confirm, cancel, result, error, focus return, or feedback behavior
- **AND** the source interaction gate lacks branch evidence or an explicit scoped boundary
- **THEN** UI Flow Structure blocks full source-based UI confidence

#### Scenario: Generic skill names no source-specific technology
- **WHEN** the installed generic UI Flow Structure skill is read
- **THEN** it describes source-baseline authority, work mode, generic interactions, source-target mapping, and observed alignment without naming a specific source technology as a hard gate

### Requirement: UI Flow Structure includes functional capability coverage in the existing route
FlowGuard UI Flow Structure SHALL account functional capability coverage inside the existing UI route before broad model, human-operability, implementation, or completion claims.

#### Scenario: Capability coverage precedes task and implementation claims
- **WHEN** a UI task claims that user-visible functionality is complete, runnable, release-ready, or human-operable
- **THEN** UI Flow Structure requires a current capability inventory and coverage review that feeds existing feature contracts, task coverage, journeys, controls/events, functional chains, output contracts, and implementation evidence

#### Scenario: Existing UI stages are reused
- **WHEN** capability coverage is required
- **THEN** it augments work mode, observed surface, UI interaction model, human-operability, implementation validation, and closure evidence
- **AND** it does not create a separate parallel UI workflow

#### Scenario: Observed controls alone are insufficient
- **WHEN** observed surface inventory and enabled-control functional chains pass
- **AND** a required capability is absent from the capability inventory or has no existing-flow binding
- **THEN** UI Flow Structure blocks full UI completion confidence

### Requirement: Observed UI inventory is the first hard gate
FlowGuard UI Flow Structure SHALL require a rendered or observed UI inventory
before an existing, migrated, runnable, or complete UI can be called modeled.
The inventory MUST list real visible controls, inputs, selects, tables,
display fields, status text, native-dialog triggers, and visible commands for
the observed target and revision.

#### Scenario: Observed item maps to model owner
- **WHEN** an observed inventory item is visible in an in-scope UI state
- **THEN** the UI review requires it to map to a `UIControl`,
  `UIDisplayElement`, or `UIVisibleSurfaceItem`
- **AND** the mapped owner must be registered in the reviewed UI model or
  visible surface

#### Scenario: Observed item is missing from model
- **WHEN** an observed inventory includes an in-scope visible button, input,
  select, table, display field, status text, native-dialog trigger, or command
  with no mapped model owner and no scoped blindspot
- **THEN** UI Flow Structure blocks model-complete and runnable-UI claims

#### Scenario: Model-only surface cannot prove real UI coverage
- **WHEN** a UI model declares controls and visible items but no observed
  inventory evidence exists for an existing or runnable UI claim
- **THEN** the claim remains design-only or scoped

### Requirement: Source-baseline interaction semantics are modeled for source-based parity
FlowGuard UI Flow Structure SHALL require source-based parity claims to model
source-baseline interaction semantics, not only visible control names. The
baseline gate MUST cover relevant native pickers, external opens, save/custom
dialogs, no-handler controls, trigger/confirm/cancel/value/result/error
branches, and native/manual boundaries.

#### Scenario: File picker baseline covers choose and cancel
- **WHEN** a source-based UI claims parity with a source file picker
- **THEN** the source interaction gate requires trigger, confirm, cancel,
  selected value, result feedback, and error-path semantics unless a branch is
  explicitly out of scope

#### Scenario: No-handler button remains visible
- **WHEN** a source baseline has a visible enabled button with no handler
- **THEN** the target UI must either model it as non-functional/disabled with
  a user-facing reason or provide a replacement functional chain

#### Scenario: Native opener has scoped evidence
- **WHEN** a source-based UI uses or replaces an external opener
- **THEN** the source-baseline interaction gate requires structured evidence for the
  visible trigger, native/local action, observable result or manual boundary,
  and any scoped blindspot

### Requirement: Implemented UI action evidence covers reachable controls
UI Flow Structure SHALL require each reachable enabled actionable control and
modeled event in an implemented/runnable UI claim to have real run evidence,
pure-UI classification, or a scoped implementation blindspot.

#### Scenario: Reachable button is unverified
- **WHEN** a running UI exposes an enabled actionable control or modeled event
- **AND** the implementation validation has no browser, desktop, or manual step
  evidence for it
- **AND** it has no pure-UI classification or scoped blindspot
- **THEN** the implementation validation MUST report a blocker

#### Scenario: Native dialog needs manual fallback
- **WHEN** a reachable UI action depends on a native file picker, download,
  clipboard, desktop shell, system permission, or third-party surface that the
  automation cannot inspect
- **THEN** the action MUST have manual step evidence or a scoped blindspot with
  owner, reason, and validation boundary

### Requirement: UI run evidence records step-level freshness
UI implementation validation SHALL keep run method, step event, control,
source state, target state, result, evidence reference, and model or
implementation revision visible.

#### Scenario: Stale UI click-through evidence
- **WHEN** UI run evidence references an older model or implementation revision
- **THEN** the implemented UI claim MUST remain blocked or scoped until the run
  is refreshed

### Requirement: Visible UI surface is reviewed
The UI Flow Structure route SHALL provide a visible-surface review that accounts
for user-facing controls, status text, helper copy, placeholders, metadata, and
disabled-state reasons when those items are in scope for a modeled UI.

#### Scenario: Visible surface has user-facing purpose
- **WHEN** a UI route records visible controls, status text, helper copy,
  placeholders, metadata, or disabled controls
- **THEN** the review verifies that each item has a state or owner, a
  user-facing purpose, and a rationale before accepting the visible surface

#### Scenario: Internal terminology is rejected
- **WHEN** a visible UI item exposes internal implementation terminology such as
  mock, backend, hydration, debug route, dataset id, or render strategy without
  an explicit user-facing reason
- **THEN** the visible-surface review reports an internal-terminology finding

#### Scenario: Disabled control explains availability
- **WHEN** a visible disabled control is part of the UI surface
- **THEN** the review requires a user-understandable disabled reason or reports
  the disabled control as incomplete

### Requirement: UI route can review universal layout evidence
The UI Flow Structure route SHALL provide a universal geometry/layout evidence
surface for text overflow, control overlap, viewport bounds, dialog or popover
bounds, focus reachability, keyboard reachability, and scroll ownership.

#### Scenario: Layout issue blocks clean geometry evidence
- **WHEN** geometry evidence records text overflow, overlapping controls,
  out-of-bounds UI, missing focus reachability, missing keyboard reachability,
  or unclear scroll ownership
- **THEN** the geometry review reports the affected item as a layout evidence
  finding

#### Scenario: Passing geometry evidence supports handoff
- **WHEN** geometry evidence records checked bounds, no overflow, no overlap,
  focus reachability, keyboard reachability, and scroll ownership
- **THEN** the geometry review can pass for the declared UI surface boundary

### Requirement: UI route can model hot and cold interaction paths
The UI Flow Structure route SHALL provide a responsiveness contract that names
hot-path user feedback, cold-path work, stale-result guards,
cancellation/coalescing behavior, and stable regions when responsiveness claims
are in scope.

#### Scenario: Hot path has immediate feedback
- **WHEN** a UI interaction is modeled as a hot-path action
- **THEN** the responsiveness review requires a feedback target or reports the
  hot path as missing immediate feedback

#### Scenario: Cold result cannot overwrite newer state
- **WHEN** a UI interaction starts cold-path work that may finish after later
  user input
- **THEN** the responsiveness review requires a stale-result guard,
  cancellation, or coalescing rule before accepting the contract

#### Scenario: Stable region is preserved
- **WHEN** a UI region is marked stable across unrelated input changes
- **THEN** the responsiveness review requires a preservation rule or reports the
  stable region as unprotected

### Requirement: UI candidate content is admitted before display modeling
FlowGuard UI Flow Structure SHALL require every in-scope candidate displayed value, status/helper/metadata item, non-action label, optional detail, or other state-exposing content item to have exactly one `user_visible`, `user_on_demand`, or `internal` classification before it can support display, text, visible-surface, or observed-surface modeling. Only a label that matches a registered control, is owned by an in-scope user task, and exposes no additional state, disabled reason, or metadata qualifies for the ordinary-control exemption; qualifying controls and labels SHALL NOT require duplicate content-admission rows.

#### Scenario: Candidate content has no classification
- **WHEN** in-scope candidate content has no visibility item or has an unknown visibility class
- **THEN** the UI review blocks rendering of that content and blocks a complete UI claim

#### Scenario: Ordinary task control label remains lightweight
- **WHEN** a normal control and label are already owned by an in-scope user task and do not expose additional system state or metadata
- **THEN** the UI route does not require a duplicate content-admission row

### Requirement: Ordinary UI admits only user-facing content
FlowGuard UI Flow Structure SHALL treat `user_visible` and `user_on_demand` as ordinary user-facing content and `internal` as non-user content. `user_visible` and `user_on_demand` content MUST identify at least one typed `task:`, `state:`, `recovery:`, or `safety:` need with a non-empty target; task and state targets MUST resolve when their owning models are supplied. `internal` content MUST NOT map to ordinary UI displays, text elements, visible-surface items, or observed visible content.

#### Scenario: Internal audit content maps directly to a display
- **WHEN** an internal trace, audit, model, test, routing, evidence, schema, or diagnostic item maps to a display, text, visible-surface, or observed-surface owner
- **THEN** the UI review reports a blocking internal-content mapping finding even when the item has a free-text purpose or rationale

#### Scenario: User-visible status has a user need
- **WHEN** current progress, success, failure, recovery, next-action, or safety content is classified `user_visible`
- **THEN** the review accepts it only when it references the user need that makes default visibility necessary

### Requirement: On-demand user content is default hidden
Content classified `user_on_demand` SHALL be hidden in the default or closed UI state across display, text, visible-surface, and observed-surface mappings, SHALL become visible only after an explicit reveal event whose control is visible, enabled, and labeled in the source state, and SHALL have an operable close, collapse, blur, Escape, or equivalent return path. Hover reveal MUST have a distinct keyboard/focus event rather than reusing the same untyped pointer event.

#### Scenario: On-demand detail is visible before reveal
- **WHEN** `user_on_demand` content is visible in a default or closed state without its reveal event
- **THEN** the UI state and content-visibility reviews block the model

#### Scenario: Optional explanation has an accessible reveal path
- **WHEN** optional explanation content is hidden in the closed state and a click, expand, hover, or focus event reveals it
- **THEN** the review accepts the path only when keyboard/focus equivalence and a return path are also modeled

### Requirement: Content admission does not create an audience-role taxonomy
Content admission SHALL keep exactly the three visibility classes `user_visible`, `user_on_demand`, and `internal` in two conceptual groups: ordinary user content and internal content. It SHALL NOT add audience, role, persona, expert-mode, authorization, or similar presentation categories to the content-admission schema.

#### Scenario: A design proposes a professional or administrator visibility class
- **WHEN** UI planning proposes a new audience or role class instead of using user need plus on-demand disclosure
- **THEN** the content-admission review rejects the new taxonomy and keeps role or authorization concerns in their owning systems

### Requirement: Observed visibility does not grant display permission
For existing or runnable UI work, the observed inventory SHALL record what is actually visible but SHALL NOT treat that observation or a direct display mapping as permission. Non-action observed content MUST resolve to an approved content-visibility item or a bounded blindspot.

#### Scenario: Existing internal content is already visible
- **WHEN** the observed UI contains an internal or unclassified non-action item that maps to an existing display owner
- **THEN** the review reports the observed leak instead of approving it because the current implementation already renders it

### Requirement: UI-visible capabilities map to behavior commitments
FlowGuard SHALL require UI-visible capabilities, controls, journeys, and
screen-level promises to map to Behavior Commitment Ledger rows when UI work
claims behavioral coverage.

#### Scenario: UI capability maps to commitment
- **WHEN** a UI flow exposes a user-visible capability
- **THEN** UI Flow Structure SHALL record the behavior commitment id that owns the capability

#### Scenario: Duplicate UI ownership blocks
- **WHEN** two UI regions claim independent ownership of the same behavior commitment
- **THEN** UI Flow Structure SHALL route to Behavior Commitment Ledger before broad confidence

