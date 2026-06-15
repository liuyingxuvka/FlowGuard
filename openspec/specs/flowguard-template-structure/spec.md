# flowguard-template-structure Specification

## Purpose

Define route-scoped template ownership while preserving the public
`flowguard.templates` compatibility facade.
## Requirements
### Requirement: Route-scoped template ownership
FlowGuard SHALL store route template bodies in route-scoped internal modules
while preserving `flowguard.templates` as the public compatibility facade.

#### Scenario: Existing compact facade remains compatible
- **WHEN** a caller imports the default model-miss, model-test-alignment, or
  UI-flow template factory from `flowguard.templates`
- **THEN** the factory emits a compact runnable template for that route

#### Scenario: Full template facade is explicit
- **WHEN** a caller needs the deep scaffold for model-miss,
  model-test-alignment, or UI-flow structure
- **THEN** a corresponding full-template factory and CLI command emits the full
  route template files

### Requirement: Template split has parity evidence
The system SHALL validate compact and full template facade behavior with public
template tests and CLI smoke coverage.

#### Scenario: Compact template text is validated
- **WHEN** route template text is loaded
- **THEN** public template tests verify runnable templates, risk-purpose
  headers, private-marker scans, line budgets, and required safety gate text

#### Scenario: Full template remains discoverable
- **WHEN** full template commands are inspected
- **THEN** CLI smoke tests verify they print and write the deep route template
  files without replacing the compact defaults

### Requirement: Public starter template demonstrates minimum value
The public project template SHALL demonstrate a minimum valuable formal model shape with a protected error class, modeled state, side effects, completion evidence, at least one known-bad case, and executable proof that the known-bad case is rejected.

#### Scenario: Project template includes completion evidence
- **WHEN** the project template is printed or written
- **THEN** its model contains a completion evidence concept and an invariant or check that forbids completion without evidence

#### Scenario: Project template includes bad-case calibration
- **WHEN** the project template run script executes
- **THEN** it demonstrates that at least one broken variant or known-bad case is rejected through the formal proof gate

#### Scenario: Project template avoids direct Explorer entry
- **WHEN** the project template run script is inspected
- **THEN** it uses the formal check plan entry and does not present direct `Explorer(...)` as the model entry route

### Requirement: Risk intent template exposes reuse fields
The Risk Intent CheckPlan template SHALL show how to declare template reuse, protected error classes, completion evidence, side effects, known-bad cases, and executable known-bad proof.

#### Scenario: Risk intent template teaches template ids
- **WHEN** the Risk Intent template is inspected
- **THEN** it includes structured template reuse fields rather than prose-only reuse notes

#### Scenario: Risk intent template teaches proof rows
- **WHEN** the Risk Intent template is inspected
- **THEN** it includes a structured known-bad proof row for the declared known-bad case

### Requirement: Starter templates demonstrate harvest closure
FlowGuard SHALL show a harvest closure review in public starter templates that demonstrate risk intent, check plans, or risk-template library usage, in addition to template search and minimum model review.

#### Scenario: Risk intent template is generated
- **WHEN** an agent generates the Risk Intent CheckPlan template
- **THEN** the example check plan includes a template harvest review field

#### Scenario: Risk template library template is generated
- **WHEN** an agent generates the risk-template library template
- **THEN** the example run prints a harvest closure review result

#### Scenario: Starter templates avoid fallback routes
- **WHEN** generated starter templates are inspected
- **THEN** they MUST NOT teach fallback explorers, compatibility entry routes, or direct Explorer-only model completion

