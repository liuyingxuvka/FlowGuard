## ADDED Requirements

### Requirement: Product-scope UI language is reviewed by the existing UI route
FlowGuard UI Flow Structure SHALL compare typography, component, navigation,
interaction, feedback, recovery, and transition semantics across every declared
surface included in a complete-product UI claim. Repeated UI expressions of the
same exact business intent SHALL reuse one canonical semantic grammar or record
a typed bounded exception with scope, reason, owner, validation boundary, and
current evidence. This review SHALL remain part of `ui_flow_structure` and
SHALL NOT create a new route, ledger, or owner.

#### Scenario: Complete-product surfaces reuse one semantic grammar
- **WHEN** a complete-product claim declares multiple pages, windows, menus, dialogs, or other UI surfaces that expose the same exact business intent
- **THEN** UI Flow Structure SHALL verify that their typography role, component role, navigation placement, interaction, feedback, recovery, and transition semantics reuse the canonical grammar for that intent

#### Scenario: Unexplained cross-surface drift blocks product confidence
- **WHEN** two declared UI surfaces expose the same exact business intent with conflicting action, navigation, feedback, recovery, or transition semantics and no typed bounded exception
- **THEN** UI Flow Structure SHALL report a product-language consistency blocker and SHALL NOT support complete-product confidence

#### Scenario: Scoped UI work does not overclaim product coverage
- **WHEN** UI work declares a component-local or surface-local validation boundary rather than a complete-product claim
- **THEN** UI Flow Structure SHALL review the declared boundary and SHALL preserve the unreviewed product surfaces as an explicit scope limitation

### Requirement: Business-bearing UI surfaces reuse the existing commitment and primary path
UI Flow Structure SHALL require every business-bearing UI capability, action
grammar, functional chain, and transition projection to bind to the existing Behavior Commitment Ledger
commitment id, stable exact `business_intent_id`, and singular PPA
`primary_path_id`. Multiple controls or surfaces for that exact intent SHALL
map to the same commitment and primary path; an additional surface SHALL NOT
create a delegate commitment or independent successful business path.

#### Scenario: Multiple UI entry surfaces share one behavior owner
- **WHEN** a button, menu item, keyboard shortcut, and dialog action expose the same exact business intent
- **THEN** their UI records SHALL name the same commitment id, business intent id, and primary path id and their functional chains SHALL reach that selected path

#### Scenario: UI surface creates an independent same-intent handler
- **WHEN** a new UI surface for an existing exact business intent reaches a different independently successful business path
- **THEN** UI Flow Structure SHALL report a path-binding blocker and SHALL route the duplicate path to the existing BCL/PPA and Architecture Reduction owners

#### Scenario: Pure UI behavior does not invent a commitment
- **WHEN** an expand, collapse, focus, local selection, or equivalent interaction creates no external business promise, terminal, material state write, or business side effect
- **THEN** UI Flow Structure SHALL keep that interaction in the existing UI model without creating a Behavior Commitment Ledger row

### Requirement: Product-language hardening preserves the three visibility classes
Product-language review SHALL use exactly `user_visible`, `user_on_demand`, and
`internal` for UI content admission. It SHALL NOT add audience, role, persona,
expert-mode, authorization, product-language, or similar presentation classes,
and it SHALL NOT treat observed visibility as permission to expose internal
content.

#### Scenario: Product-language work proposes another visibility class
- **WHEN** a product-language review proposes a fourth visibility class for an administrator, professional, expert, persona, or platform
- **THEN** UI Flow Structure SHALL reject the new taxonomy and SHALL express the need through the existing user need, on-demand disclosure, platform exception, or owning authorization system

#### Scenario: Existing UI exposes internal path metadata
- **WHEN** an observed UI displays an internal commitment id, path id, evidence state, audit field, or routing diagnostic without a typed user-facing need
- **THEN** UI Flow Structure SHALL classify the item as an internal-content leak rather than accepting it as product-language content
