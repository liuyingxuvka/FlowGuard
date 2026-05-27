# ui-text-hierarchy-blueprint Specification

## Purpose
TBD - created by archiving change add-ui-text-hierarchy. Update Purpose after archive.
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
