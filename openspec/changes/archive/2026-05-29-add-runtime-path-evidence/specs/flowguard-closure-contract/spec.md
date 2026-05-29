## ADDED Requirements

### Requirement: Closure contract consumes runtime path alignment
FlowGuard Closure Contract SHALL consume runtime path alignment reports when a
broad done, release, publish, parent/child, or production-confidence claim
depends on real code following a modeled workflow path.

#### Scenario: Runtime path alignment supports full confidence
- **WHEN** a closure plan requires runtime path evidence
- **AND** the closure evidence includes a current full-confidence runtime path
  alignment report
- **THEN** runtime path alignment SHALL NOT block full closure confidence

#### Scenario: Runtime path alignment is missing
- **WHEN** a closure plan requires runtime path evidence
- **AND** no current runtime path alignment report is supplied
- **THEN** closure review SHALL block or scope the final confidence claim

#### Scenario: Runtime path alignment is scoped
- **WHEN** runtime path alignment is current but only scoped
- **THEN** closure review SHALL NOT promote that evidence to full production or
  parent confidence
