## ADDED Requirements

### Requirement: Route profiles declare entry role
FlowGuard SHALL classify every route profile with an explicit route role and
entry policy before the profile can support AI-facing route discovery.

#### Scenario: Public owner route is directly selectable
- **WHEN** a route profile is classified as `public_owner`
- **THEN** the profile MUST use `entry_policy=direct`
- **AND** the profile MAY appear in the AI-facing public route map

#### Scenario: Internal helper route is not directly selectable
- **WHEN** a route profile is classified as `internal_feeder` or `data_helper`
- **THEN** the profile MUST name a `canonical_owner_route` or
  `absorbed_by_route`
- **AND** it MUST NOT appear as a direct AI-facing route starter

#### Scenario: Delegated mode route is owner-selected
- **WHEN** a route profile is classified as `delegated_mode`
- **THEN** the profile MUST use `entry_policy=via_owner`
- **AND** the owner route MUST name the mode in its own profile or guidance

### Requirement: Public route map excludes internal helpers
FlowGuard SHALL expose a compact public route map containing only public owner
routes and explicitly scoped public facades.

#### Scenario: AI route discovery reads public routes
- **WHEN** an AI agent reads `FLOWGUARD_ROUTE_API` or `ROUTE_STARTER_API`
- **THEN** it sees only public owner routes and starter helpers for those
  owners

#### Scenario: Advanced helper remains importable
- **WHEN** implementation code or focused tests need an internal feeder helper
- **THEN** the helper MAY remain importable from advanced or full helper
  inventories
- **AND** that availability MUST NOT make the helper a public route starter

### Requirement: Old helper surfaces require disposition
FlowGuard SHALL classify old helper prompts, route ids, template commands,
aliases, wrappers, and compatibility-like entries before they are retained.

#### Scenario: Obsolete helper prompt is deleted
- **WHEN** an old helper prompt only duplicates a current owner route
- **THEN** FlowGuard MUST remove it or rewrite it to point at the owner route

#### Scenario: Public facade requires proof
- **WHEN** an old helper surface is intentionally retained for public users
- **THEN** ArchitectureReduction or StructureMesh evidence MUST classify it as
  a current public facade before it remains in the public route map

### Requirement: No fallback helper route
FlowGuard SHALL NOT keep a fallback path from a current owner route back to an
old helper-first route for canonical behavior.

#### Scenario: Old route cannot satisfy current coverage
- **WHEN** a claim cites only an old helper-first route result
- **THEN** FlowGuard MUST treat the claim as incomplete for the current owner
  route unless the owner route consumed that evidence explicitly
