# flowguard-route-topology-governance Specification

## Purpose

Define the typed ownership and liveness rules for FlowGuard route handoffs so every target resolves to one authority, every allowed cycle has bounded progress, and routing hazards produce deterministic blocking diagnostics.
## Requirements
### Requirement: Typed Route Handoffs
Every route handoff SHALL declare a `target_kind`, `target_id`, activation condition, and claim scope. Allowed target kinds MUST be `skill`, `internal_route`, `helper_api`, or `external_action`, and the target MUST resolve under the rules for its declared kind.

#### Scenario: Skill handoff resolves
- **WHEN** a handoff declares `target_kind=skill`
- **THEN** its target id resolves to exactly one member of the canonical FlowGuard suite inventory

#### Scenario: Internal route is mislabeled as a skill
- **WHEN** a kernel-owned internal route is declared with `target_kind=skill`
- **THEN** topology validation fails with a target-kind-mismatch diagnostic

#### Scenario: Target is dangling
- **WHEN** a handoff names an id that is absent from the appropriate target registry
- **THEN** topology validation fails and identifies the source route, target kind, and unresolved id

### Requirement: Unique Route Ownership
Every public-owner/direct route SHALL have exactly one canonical public skill owner. Every internal route SHALL have exactly one owner skill and one internal route id. Duplicate, missing, or contradictory ownership MUST block route closure.

#### Scenario: Public route has no owner
- **WHEN** a public-owner/direct profile omits `skill_name`
- **THEN** topology validation fails with a missing-public-owner diagnostic

#### Scenario: Route has two owners
- **WHEN** two skills claim primary ownership of the same public route id
- **THEN** topology validation fails with both claimants and no fallback owner is selected

### Requirement: Bounded Cycle Liveness
Every strongly connected route component SHALL declare a progress measure, an allowed evidence or state delta, terminal success and blocked conditions, and a finite re-entry bound. Re-entry without the declared delta MUST terminate as blocked at or before the bound.

#### Scenario: Rework loop makes progress
- **WHEN** a cycle re-enters with a new accepted evidence receipt that changes its progress measure
- **THEN** the cycle may continue within its declared bound

#### Scenario: Rework loop repeats unchanged
- **WHEN** a cycle re-enters with unchanged inputs and no allowed delta
- **THEN** liveness validation reaches the typed blocked terminal before exceeding the re-entry bound

#### Scenario: Cycle lacks a bound
- **WHEN** a strongly connected component has no finite re-entry or review bound
- **THEN** topology validation fails with an unbounded-cycle diagnostic

### Requirement: Deterministic Topology Diagnostics
Topology validation SHALL produce deterministic machine-readable findings for dangling targets, target-kind mismatch, missing/duplicate owners, unbounded cycles, absent terminals, and unchanged-loop progress. Findings SHALL include affected route ids and SHALL prevent broad routing confidence.

#### Scenario: Multiple hazards exist
- **WHEN** a graph contains both a dangling target and an unbounded cycle
- **THEN** the result reports both hazards in stable order and returns a failing status

### Requirement: Portable Temporal Topology Evidence
When a topology review makes a portable liveness or fairness claim, the system SHALL consume current executable temporal obligations and checker findings for the same portable model identity.

#### Scenario: Current temporal receipt supports topology claim
- **WHEN** the topology and portable checker consume the same graph identity and all required temporal obligations pass
- **THEN** the portable liveness or fairness claim may pass within the declared bound

#### Scenario: Metadata-only fairness is rejected
- **WHEN** fairness is described in route metadata without a current executable obligation and receipt
- **THEN** the portable fairness claim remains unverified

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

### Requirement: One canonical declaration owns every public route identity
The system SHALL project public route admission, coverage ownership, skill identity, documentation identity, and contract identity from one canonical declaration. Missing, conflicting, or retired identities SHALL fail visibly and SHALL NOT be repaired through aliases or fallback mappings.

#### Scenario: Coverage and admission use different owner identities
- **WHEN** generated coverage ownership differs from generated admission ownership for one public route
- **THEN** topology validation fails and names both conflicting projections

#### Scenario: Retired route identity is supplied
- **WHEN** a caller supplies a retired route identifier
- **THEN** the system rejects it without translating it to the current identifier

### Requirement: Retired routes are removed after responsibility reattachment
Route topology governance SHALL remove an intentionally retired route only after every still-required admission, transition, negative case, and completion obligation is attached to exactly one current route owner.

#### Scenario: Route protection has been migrated
- **WHEN** every retained protection has a current owner and executable evidence
- **THEN** the retired node and all incoming/outgoing current relations are absent from the route declaration and generated topology

#### Scenario: Retired route remains reachable
- **WHEN** any public profile, handoff, template, prompt, CLI, or generated topology still reaches the retired route
- **THEN** topology validation blocks closure as a dangling or duplicate route owner
