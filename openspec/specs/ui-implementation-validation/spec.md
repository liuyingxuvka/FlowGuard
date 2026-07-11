# ui-implementation-validation Specification

## Purpose
This capability defines FlowGuard's Ui Implementation Validation behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: UI implementation validation is explicit
The system SHALL provide a UI implementation validation surface that
distinguishes model-complete UI design from running UI completion evidence.

#### Scenario: Implemented UI claim names evidence boundary
- **WHEN** a route claims a UI is implemented, runnable, or complete in the
  running interface
- **THEN** the validation records the source feature model, source UI
  interaction model, source journey coverage, implementation target, evidence
  freshness reference, validation boundaries, and rationale

#### Scenario: Design-only UI can stop before implementation evidence
- **WHEN** a route only claims model, structure, text hierarchy, or design
  contract completion
- **THEN** implementation click-through validation is not required as long as no
  running UI completion claim is made

### Requirement: Functional features align with UI journeys
The system SHALL verify that every user-visible feature contract is represented
by a UI journey, entry point, terminal action, or scoped implementation
blindspot.

#### Scenario: User-visible feature has UI journey coverage
- **WHEN** a feature contract declares `new_project` as user-visible UI
  functionality
- **THEN** the validation finds a matching journey, entry point, terminal action,
  or implementation blindspot for `new_project`

#### Scenario: Functional feature with no UI path is rejected
- **WHEN** a user-visible feature contract has no matching UI journey, event,
  entry point, terminal allowance, or blindspot
- **THEN** the implementation validation reports the feature as not exposed by
  the UI model

### Requirement: UI controls and events have functional ownership
The system SHALL verify that reachable actionable UI controls and modeled UI
events are either owned by a functional feature contract, classified as pure UI
behavior, or scoped to an implementation blindspot.

#### Scenario: UI-only close action is allowed
- **WHEN** a close, cancel, back, expand, collapse, or exit control is modeled
  as pure UI behavior
- **THEN** the implementation validation does not require a product feature
  contract for that control

#### Scenario: Actionable button without feature ownership is rejected
- **WHEN** a reachable actionable control is covered by UI journey coverage but
  has no feature contract, pure UI classification, or implementation blindspot
- **THEN** the implementation validation reports the control as functionally
  unowned

### Requirement: Real UI journey runs cover modeled feature paths
The system SHALL require browser, desktop automation, or manual click-through
evidence for every modeled feature journey when implemented UI completion is
claimed.

#### Scenario: Journey run verifies modeled steps
- **WHEN** a journey run validates the load-existing-project path
- **THEN** each step references modeled controls, events, source states, target
  states, a validation method, a passed result, and an evidence reference

#### Scenario: Missing run for feature journey is rejected
- **WHEN** a feature journey is declared in UI journey coverage
- **AND** no passed implementation run or scoped blindspot covers that feature
- **THEN** the implementation validation reports missing click-through evidence

#### Scenario: Success-only evidence does not cover failure recovery
- **WHEN** a modeled feature journey names failure, recovery, cancel, or exit
  events
- **AND** implementation evidence omits those modeled handling events
- **THEN** the implementation validation reports missing branch evidence

### Requirement: Evidence freshness is enforced
The system SHALL reject implementation evidence that does not identify the UI
model or implementation revision it validates.

#### Scenario: Current model revision is recorded
- **WHEN** validation evidence is recorded after the UI model and journey
  coverage are reviewed
- **THEN** the validation includes a model revision or fingerprint that can be
  compared with the current source model

#### Scenario: Missing or stale evidence revision is rejected
- **WHEN** implementation validation lacks a freshness reference or references a
  different source model revision than the supplied current revision
- **THEN** the validation reports stale or ungrounded evidence

### Requirement: Implementation blindspots are bounded
The system SHALL allow intentionally unverified UI implementation branches only
when they are recorded as blindspots with scope, reason, owner, validation
boundary, and rationale.

#### Scenario: Hard-to-automate branch is deferred with owner
- **WHEN** a desktop file picker branch cannot be automated in the current run
- **THEN** the implementation blindspot names the feature, controls or events,
  reason, owner, validation boundary, and follow-up rationale

#### Scenario: Unscoped implementation blindspot is rejected
- **WHEN** an implementation blindspot has no feature, control, event, reason,
  owner, validation boundary, or rationale
- **THEN** the implementation validation reports the blindspot as incomplete

### Requirement: Runnable UI claims include human-operability evidence when user-facing completeness is claimed
UI Implementation Validation SHALL require a current human-operability report
when an agent claims a UI is complete, human-operable, release-ready, or usable
by a person for in-scope user tasks.

#### Scenario: Implementation evidence lacks human-operability report
- **WHEN** an implemented UI has click-through or functional-chain evidence
- **AND** the final claim says users can operate or complete the UI tasks
- **THEN** implementation validation requires a passing or explicitly scoped
  human-operability report for the same target revision

### Requirement: UI implementation validation consumes capability coverage
UI Implementation Validation SHALL consume current UI functional capability coverage when a running UI is claimed implemented, runnable, complete, or wired for user-visible functions.

#### Scenario: Capability coverage is current
- **WHEN** implementation validation claims complete runnable UI behavior
- **THEN** it references the current capability inventory and a passing capability coverage report for the same model or implementation revision

#### Scenario: Capability coverage is missing
- **WHEN** implementation validation has feature contracts and journey runs
- **AND** no current capability coverage evidence is supplied for an in-scope user-visible function boundary
- **THEN** implementation validation blocks full runnable UI confidence

#### Scenario: Capability output evidence is missing
- **WHEN** a required capability has journey or click evidence
- **AND** its result-producing output contract is missing, failed, stale, or scoped without owner
- **THEN** implementation validation rejects full functional completion for that capability

### Requirement: Enabled controls prove a real functional chain
UI Implementation Validation SHALL require every in-scope enabled actionable
control to have a real functional chain or an explicit pure-UI/deferred
blindspot classification. A functional chain MUST bind visible control, UI
event, code owner, backend/local/native function, observed UI state or display
update, evidence reference, result, and current revision.

#### Scenario: Button click produces observed UI result
- **WHEN** an enabled button is part of a runnable or complete UI claim
- **THEN** implementation validation requires evidence that clicking the
  visible control triggered the modeled UI event, reached the declared code
  owner/function, and produced the expected observed UI state or display update

#### Scenario: API existence is insufficient
- **WHEN** a control only cites an API route, handler name, or local function
  without click evidence and observed UI result
- **THEN** implementation validation blocks runnable/complete UI confidence

#### Scenario: Label match is insufficient
- **WHEN** a control only proves that its label, accessible name, or DOM text is
  correct
- **THEN** implementation validation treats the evidence as render evidence,
  not functional-chain evidence

#### Scenario: Native dialog branch is manually bounded
- **WHEN** a functional chain enters a native dialog, file picker, permission
  prompt, or OS shell action that cannot be fully automated
- **THEN** the chain must include structured manual/native evidence,
  observable result or blindspot, owner, validation boundary, and rationale

### Requirement: UI completion claims require implementation validation
FlowGuard SHALL require `UIImplementationValidation` for claims that an
implemented UI is runnable, complete, or has buttons wired to real behavior.

#### Scenario: Runnable claim has no implementation validation
- **WHEN** an agent claims a UI is runnable, complete, or button wiring is
  finished
- **AND** no current implementation validation exists for the relevant target
  revision
- **THEN** the claim is blocked or downgraded to design/model-only confidence

### Requirement: UI evidence declares evidence kind
UI implementation validation SHALL allow render and implementation evidence to
declare the kind of evidence used for a runnable UI claim, including screenshot,
browser click-through, DOM text, computed style, geometry, accessibility or
ARIA, runtime trace, log, test result, and manual observation evidence.

#### Scenario: Screenshot evidence is accepted
- **WHEN** implementation validation records screenshot evidence for a visible
  UI surface
- **THEN** the evidence kind is accepted as a normal UI evidence type

#### Scenario: Evidence without kind is rejected
- **WHEN** implementation validation records render or implementation evidence
  without an evidence kind
- **THEN** the implementation evidence review reports the evidence as missing a
  declared kind

#### Scenario: Unknown evidence kind is rejected
- **WHEN** implementation validation records an evidence kind outside the
  supported UI evidence kind list
- **THEN** the implementation evidence review reports the evidence kind as
  unknown

### Requirement: Render evidence remains bound to UI model context
UI render evidence SHALL identify the source interaction model, implementation
target, evidence target, result, evidence reference, and model or
implementation revision before supporting a runnable UI completion claim.

#### Scenario: Render evidence names model context
- **WHEN** render evidence supports an implemented UI claim
- **THEN** it records the source UI interaction model, implementation target,
  evidence target, evidence reference, result, and current revision

#### Scenario: Stale render evidence is rejected
- **WHEN** render evidence references a model or implementation revision that
  differs from the current validation revision
- **THEN** the implementation evidence review reports stale render evidence

### Requirement: Runnable UI proves content admission behavior
UI Implementation Validation SHALL bind the current content-visibility plan to the implementation revision and a current observed-surface inventory. It SHALL provide structured per-content evidence rows that prove default-visible content is admitted, on-demand content is hidden, explicitly revealed, observed in the reveal target, and returned to hidden, and internal content is absent from the ordinary observed UI. A boolean review flag or one opaque evidence reference SHALL NOT satisfy this requirement.

#### Scenario: Runtime evidence proves default hidden and reveal
- **WHEN** a runnable UI claim includes `user_on_demand` content
- **THEN** current screenshot, DOM, desktop/manual observation, test, or equivalent evidence records the closed state, reveal event and revealed state, and return to the closed state

#### Scenario: Internal content appears in observed UI
- **WHEN** the current implementation renders content classified `internal` on an ordinary user surface
- **THEN** implementation validation blocks runnable, complete, usable, and release-ready UI claims

#### Scenario: Visibility evidence is stale
- **WHEN** the content-visibility plan, UI model, or implementation revision changes after the evidence was produced
- **THEN** the visibility evidence is stale and MUST be rerun before it supports completion

#### Scenario: One opaque evidence reference claims the whole boundary
- **WHEN** implementation validation supplies no per-content phase rows or no observed inventory
- **THEN** validation blocks the runnable UI claim even when the opaque reference is non-empty

#### Scenario: A content row cites another content item's observation
- **WHEN** default-visible or revealed evidence for one content item points only to an observed item for different content or a different UI state
- **THEN** validation rejects the row instead of treating the unrelated observation as per-content proof

