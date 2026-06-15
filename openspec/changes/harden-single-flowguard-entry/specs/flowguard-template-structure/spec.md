## MODIFIED Requirements

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
