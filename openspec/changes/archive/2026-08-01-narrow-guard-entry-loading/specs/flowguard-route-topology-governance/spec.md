## ADDED Requirements

### Requirement: Public routes expose discriminating admission profiles
Every public FlowGuard route SHALL expose one current route profile containing stable positive-condition ids, forbidden-condition ids, minimum inputs, first action, conditional reference edges, deepening triggers, owner route, and claim boundary. The profile SHALL remain owned by the existing route topology and MUST NOT create a second router or public alias.

#### Scenario: Clear public route exists
- **WHEN** task facts satisfy one public route's positive conditions, satisfy its minimum inputs, and do not hit a forbidden condition
- **THEN** the route decision selects that route and exposes only its first action and conditional reference map

#### Scenario: Near-neighbor route differs
- **WHEN** a task shares vocabulary with one route but its structured facts satisfy a different route's discriminating condition
- **THEN** the matching owner route is selected without lexical fallback

### Requirement: Route conflicts remain visible
Public route selection SHALL preserve zero-candidate and multiple-candidate outcomes as explicit unresolved decisions. It MUST NOT choose by declaration order, lexical score, or caller self-assertion.

#### Scenario: Multiple routes remain applicable
- **WHEN** task facts satisfy more than one public route and no declared owner relation resolves the conflict
- **THEN** route selection returns a conflict with all candidate ids and no selected route

#### Scenario: Forbidden condition applies
- **WHEN** a route's forbidden condition is evidenced by the task facts
- **THEN** that route is excluded with the condition id and evidence disposition visible

### Requirement: All public route admissions have known-bad coverage
The FlowGuard AI trigger model SHALL include positive, near-neighbor negative, forbidden, and unresolved-conflict evidence for every public route. Coverage SHALL include Architecture Reduction, Behavior Commitment Ledger, Contract Exhaustion Mesh, Field Lifecycle Mesh, and Model Topology Hazard Review.

#### Scenario: Public route inventory changes
- **WHEN** the public route topology adds, removes, or renames a route
- **THEN** route-profile and trigger-model checks block until the full admission evidence inventory matches the current public routes

### Requirement: Current model authority exposes one typed build-to-activate handoff
FlowGuard SHALL expose one current-format model-revision builder that derives the live candidate, canonical diff, affected closure, exact native-owner evidence coverage, and accepted revision from the sole observed head and one exact-current terminal-pass full model-regression parent receipt. The builder MUST reject stale, scoped, incomplete, skipped, blocked, foreign-manifest, wrong-toolchain, wrong-environment, wrong-obligation, or inexact-child evidence; MUST write immutable content-addressed candidate and revision artifacts; and MUST NOT execute models, activate authority, change the observed head, accept a compatibility format, or create an alternate activation path.

#### Scenario: Exact current full parent receipt is supplied
- **WHEN** a caller supplies stable revision, task, and snapshot ids plus a terminal-pass full model-regression parent receipt whose complete children exactly match current model-owner inputs and obligations
- **THEN** the builder returns one accepted current-schema revision and candidate with exact content-addressed paths while the observed authority head remains unchanged

#### Scenario: Parent evidence is stale or incomplete
- **WHEN** the supplied parent receipt is scoped, stale, skipped, blocked, bound to a different manifest, missing one current owner, or differs from an independently verified child receipt
- **THEN** generation fails visibly and writes no accepted revision or candidate artifact

#### Scenario: Activation is requested implicitly
- **WHEN** revision generation succeeds without a separate activation command
- **THEN** the observed authority pointer and generation remain unchanged
