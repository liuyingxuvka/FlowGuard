## ADDED Requirements

### Requirement: Public starter template demonstrates minimum value
The public project template SHALL demonstrate a minimum valuable model shape
with a protected error class, modeled state, side effects, completion evidence,
and at least one known-bad case.

#### Scenario: Project template includes completion evidence
- **WHEN** the project template is printed or written
- **THEN** its model contains a completion evidence concept and an invariant or check that forbids completion without evidence

#### Scenario: Project template includes bad-case calibration
- **WHEN** the project template run script executes
- **THEN** it demonstrates that at least one broken variant or known-bad case is rejected

### Requirement: Risk intent template exposes reuse fields
The Risk Intent CheckPlan template SHALL show how to declare template reuse,
protected error classes, completion evidence, side effects, and known-bad cases.

#### Scenario: Risk intent template teaches template ids
- **WHEN** the Risk Intent template is inspected
- **THEN** it includes structured template reuse fields rather than prose-only reuse notes
