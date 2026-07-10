# UI Journey, Structure, And Text Protocol

Use this protocol after the interaction model is reviewed. Complete app claims require journey coverage before structure/text derivation; component-only scope may record a narrower boundary.

## Journey coverage

Use `UIJourneyCoverage`, `UIJourneyEntryPoint`, `UIFeatureJourney`, `UITerminalActionAllowance`, `UIResidualBlindspot`, and `review_ui_journey_coverage(...)`.

Record launch state; launch entry points; feature states/events; success terminals; failure/recovery/cancel/exit events; every reachable actionable control/event owner; allowed terminal actions; and blindspot reason, owner, validation boundary, and rationale.

Block missing/unreachable entries or success terminals, unknown paths, reachable actions/events without owner or blindspot, recoverable failures without handling, terminal outgoing actions without allowed purpose, and blindspots without disposition.

## Structure derivation

Derive parent surface, regions/screens/menus/panels/overlays, state/control/display/event-to-region maps, parent/child edges, stable global controls, contextual/local controls, information ownership, overlay blocking scope, validation boundaries, and rationale.

Keep first-level persistent controls stable, second-level contextual controls with their owning workflow, third-level controls near their local data/state, and destructive actions separate. Block wrong-level controls, duplicate same-level functions, missing region owners, unstable global placement, or structure derived before model/journey review.

## Text hierarchy

Use `UITextHierarchyBlueprint`, `UITextElement`, `UITypographyToken`, and `review_ui_text_hierarchy(...)` to map page/region headings, control labels, status/progress/success/failure text, helper/validation/empty/recovery slots, display labels, state-to-text ownership, and repetition rationale.

Semantic hierarchy levels are not a command to create a distinct visual font size per level. Text with similar jobs should reuse treatments; prefer grouping, spacing, weight, color role, or placement before a one-off visual text style. Preserve justified editorial/brand/warning/state-critical exceptions.

Block labels that disagree with modeled consequence, text without state/control/display owner, error/recovery copy without its path, competing truth sources, and copy/design handoff that contains prose but no ownership maps.
