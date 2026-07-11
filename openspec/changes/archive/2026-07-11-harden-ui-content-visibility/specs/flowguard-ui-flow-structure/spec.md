## ADDED Requirements

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
