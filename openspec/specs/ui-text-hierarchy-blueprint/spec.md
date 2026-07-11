# ui-text-hierarchy-blueprint Specification

## Purpose
This capability defines FlowGuard's Ui Text Hierarchy Blueprint behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: UI text inventory is explicit
The system SHALL provide a UI Text Hierarchy Blueprint surface that inventories
visible and assistive UI text by state, region, role, owner, and semantic key.

#### Scenario: Text item has role and owner
- **WHEN** a UI blueprint includes a heading, label, helper note, status line,
  CTA, warning, error, empty-state message, loading message, or success/failure
  message
- **THEN** the blueprint records the text role, owning UI state, owning region,
  semantic key, and priority

#### Scenario: Orphan text is rejected
- **WHEN** visible UI text is listed without a state or region owner
- **THEN** the text hierarchy review reports it as orphan text

### Requirement: Primary text hierarchy is constrained
The system SHALL identify which text is allowed to be primary, secondary, and
tertiary in each UI state and region.

#### Scenario: State has one dominant message
- **WHEN** one UI state contains multiple high-priority headings, status lines,
  or explanatory blocks
- **THEN** the blueprint marks one dominant message or reports competing
  primary text

#### Scenario: Local affordance text stays local
- **WHEN** a control label or helper note only supports a local action
- **THEN** the blueprint keeps it at the local hierarchy level instead of
  promoting it above state-level guidance

### Requirement: Duplicate text needs a semantic rationale
The system SHALL detect repeated semantic text and require an explicit rationale
when repetition is intentional.

#### Scenario: Duplicate state message requires rationale
- **WHEN** two text items in the same state share the same semantic key
- **THEN** the review reports duplicate text unless the blueprint provides an
  accessibility, summary/detail, cross-region continuity, or confirmation
  rationale

#### Scenario: Assistive duplication can be preserved
- **WHEN** repeated text exists to support screen-reader, keyboard, or
  accessibility-visible guidance
- **THEN** the blueprint may preserve it when the assistive rationale and owner
  are explicit

### Requirement: State-specific text cannot leak across states
The system SHALL bind empty, loading, success, failure, warning, error, and
recovery text to the states where it is truthful.

#### Scenario: Loading text leaves after completion
- **WHEN** a UI state transitions from loading to success or failure
- **THEN** loading text is removed, hidden, or demoted according to the
  blueprint

#### Scenario: Failure recovery text appears with failure
- **WHEN** a recoverable failure state is visible
- **THEN** the blueprint includes recovery guidance or explicitly marks the
  state terminal

### Requirement: Warning and error text can escalate hierarchy
The system SHALL allow blocking warnings, destructive-action warnings, and
errors to outrank ordinary headings or helper text when the modeled state
requires user attention.

#### Scenario: Blocking warning outranks normal copy
- **WHEN** a destructive, irreversible, privacy-sensitive, or blocking state is
  active
- **THEN** the blueprint elevates the warning or error text above normal
  explanatory copy

#### Scenario: Non-blocking helper text does not dominate
- **WHEN** text only explains an optional local control
- **THEN** the blueprint keeps it below primary state guidance

### Requirement: UI text hierarchy remains separate from visual design
The UI Text Hierarchy Blueprint SHALL NOT replace visual design, final
copywriting, localization, browser QA, frontend implementation, or
accessibility testing.

#### Scenario: Blueprint hands off to implementation
- **WHEN** text roles, priorities, owners, and duplication rationales are clear
- **THEN** the resulting blueprint can be handed to frontend, design, copy, or
  accessibility workflows without claiming those workflows are complete

### Requirement: Visual handoff preserves calm text hierarchy
The UI Text Hierarchy Blueprint SHALL include handoff guidance that distinguishes
semantic text roles from final visual text treatments so downstream design does
not turn every semantic hierarchy level into a separate visual font size.

#### Scenario: Semantic roles share visual treatment when their jobs are similar
- **WHEN** a text hierarchy blueprint contains labels, helper text, status text,
  panel headings, or body text with similar local importance
- **THEN** the handoff guidance tells downstream design to consider reusing a
  visual text treatment instead of creating one visual size per semantic role

#### Scenario: Visual differences need a meaning or attention role
- **WHEN** a text treatment is visually different from nearby text through size,
  weight, color role, spacing, or placement
- **THEN** the handoff guidance records or requests the reason for the
  difference, such as primary focus, region scanning, local control, warning,
  helper text, quiet metadata, or brand expression

### Requirement: Typography noise is reported as a design smell
The UI Text Hierarchy Blueprint SHALL allow agents to report excessive one-off
text treatments as a design smell without treating the smell as a universal
hard failure or fixed font-size budget.

#### Scenario: One-off text treatments are flagged softly
- **WHEN** nearby text elements with similar jobs use unrelated visual
  treatments without a clear rationale
- **THEN** the review reports a typography hierarchy smell and recommends
  consolidation, reuse, grouping, spacing, weight, color role, or placement
  before adding another visual text style

#### Scenario: Intentional expressive exceptions are preserved
- **WHEN** a broader text treatment range is used for a hero, editorial,
  marketing, brand-heavy, warning, or state-critical purpose
- **THEN** the review preserves the exception when its attention or meaning role
  is explicit

### Requirement: Helper and status copy stays owned by UI purpose
The UI Text Hierarchy Blueprint SHALL keep helper copy, placeholder text,
status text, empty/loading/error messages, metadata labels, and disabled-state
reasons tied to an owning state, region, control, or display purpose.

#### Scenario: Helper copy has a useful purpose
- **WHEN** helper copy appears in a UI text hierarchy blueprint
- **THEN** the review verifies that the helper text has an owning state or
  control, a lower-priority role than the main task unless escalation is
  justified, and a user-facing purpose

#### Scenario: Placeholder is not treated as feature proof
- **WHEN** placeholder text appears in the UI surface
- **THEN** the review requires it to be marked as placeholder guidance or
  reports it when it is presented as completed product functionality

#### Scenario: Repeated helper copy needs value
- **WHEN** helper copy repeats a nearby label, button text, or status message
  with the same semantic meaning
- **THEN** the review requires an explicit user value or reports low-value
  repeated helper copy

#### Scenario: State messages do not compete
- **WHEN** one UI state contains multiple empty, loading, pending, error, or
  success messages with primary priority
- **THEN** the review reports competing state messages unless one message is
  clearly dominant or the repetition has an explicit rationale

### Requirement: Text hierarchy consumes approved content
The UI Text Hierarchy Blueprint SHALL create visible text elements only from approved `user_visible` content or `user_on_demand` content in a state reached by its explicit reveal event. Internal and unclassified content SHALL NOT gain visibility through text ownership, hierarchy, typography, or rationale fields.

#### Scenario: Internal metadata has a text owner
- **WHEN** internal metadata is assigned a text role, state, region, priority, or typography token
- **THEN** the text hierarchy review blocks the item because text ownership does not grant display admission

#### Scenario: Optional detail remains quiet until requested
- **WHEN** explanation or detailed status is classified `user_on_demand`
- **THEN** the blueprint keeps it absent from the default hierarchy and includes it only in the revealed-state hierarchy

