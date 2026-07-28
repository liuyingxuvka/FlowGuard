## ADDED Requirements

### Requirement: Installed skill shells mirror route roles
FlowGuard Codex skill shells SHALL describe public owner routes, delegated
modes, internal feeders, and data helpers consistently with the route registry.

#### Scenario: Public skill names owner route
- **WHEN** an installed FlowGuard skill is a public owner route
- **THEN** its `SKILL.md` MUST identify that owner route and its hard gates

#### Scenario: Delegated mode skill is not generic first stop
- **WHEN** an installed FlowGuard skill is a delegated mode
- **THEN** its `SKILL.md` MUST say it is selected by the owning route except
  when explicitly requested

#### Scenario: Internal helper has no installed direct skill
- **WHEN** a helper is classified as an internal feeder or data helper
- **THEN** the installed skill set MUST NOT expose it as a direct Codex
  satellite unless a public facade is proven

### Requirement: Stale prompt wording is cleaned
FlowGuard Codex skill prompts SHALL NOT describe old helper-first same-class,
analogous-bug, simulator, scan, or closure routes as current canonical paths.

#### Scenario: Old same-class wording appears
- **WHEN** skill docs or prompt templates mention hand-written same-class cases
  as coverage
- **THEN** the wording MUST be rewritten to say those cases are seeds for
  ContractExhaustionMesh

#### Scenario: Old final-claim wording appears
- **WHEN** skill docs imply closure helpers or maintenance scans can support
  broad final confidence by themselves
- **THEN** the wording MUST be rewritten to require RiskEvidenceLedger and
  DevelopmentProcessFlow owner consumption
