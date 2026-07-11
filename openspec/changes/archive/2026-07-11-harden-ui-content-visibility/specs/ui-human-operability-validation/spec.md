## ADDED Requirements

### Requirement: On-demand disclosure remains human-operable
Human-operability validation SHALL require every in-scope `user_on_demand` item to bind to an in-scope user task, a visible/enabled reveal control with a discoverable affordance contract, an action grammar whose feedback item resolves to that revealed content, a close or collapse path, and keyboard/focus-equivalent operation for hover-based disclosure.

#### Scenario: Hover detail has no keyboard equivalent
- **WHEN** optional details can be revealed by pointer hover but not by keyboard focus or an equivalent explicit control
- **THEN** human-operability validation blocks a complete or usable UI claim

#### Scenario: Expanded details cannot be dismissed
- **WHEN** a user reveals optional details and no close, collapse, blur, Escape, or equivalent return path exists
- **THEN** human-operability validation reports an incomplete on-demand interaction

#### Scenario: Reveal control has no content-bound feedback
- **WHEN** a reveal control is visible but its task grammar does not name the content item that appears
- **THEN** human-operability validation blocks the claim instead of treating generic feedback as proof
