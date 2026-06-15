## ADDED Requirements

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
