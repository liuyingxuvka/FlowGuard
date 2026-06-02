## ADDED Requirements

### Requirement: Full confidence requires model-code-test binding by default

Model-Test Alignment SHALL require required model obligations, owner code
contracts, and current passing test evidence to bind together by default before
reporting full green confidence.

#### Scenario: Required obligation has code and test bound together
- **WHEN** a required model obligation has an owner code contract
- **AND** current passing test evidence covers both that obligation and that
  owner code contract
- **THEN** Model-Test Alignment can treat that row as locked.

#### Scenario: Required obligation has no code owner
- **WHEN** a required model obligation has no owner code contract
- **THEN** Model-Test Alignment SHALL report a blocker.

#### Scenario: Test covers model but not code
- **WHEN** current passing test evidence covers a required model obligation
- **AND** it does not cover a code contract implementing that obligation
- **THEN** Model-Test Alignment SHALL report a blocker.

#### Scenario: Test binds the wrong code contract
- **WHEN** test evidence covers model obligation A
- **AND** the evidence covers a code contract that does not implement A
- **THEN** Model-Test Alignment SHALL report a blocker.

### Requirement: No compatibility switch for model-test-only green

FlowGuard SHALL NOT provide a compatibility switch that allows required
model-test-only evidence to produce full Model-Test Alignment green confidence.

#### Scenario: Model-test-only evidence is present
- **WHEN** an obligation and test evidence are both present
- **AND** no owner code contract is present
- **THEN** the result is blocked or scoped, not full green.

### Requirement: Binding report rows expose the lock state

Model-Test Alignment SHALL expose model-code-test binding rows that identify the
model obligation id, code contract id, test evidence id, status, and gap reasons.

#### Scenario: Human reads alignment output
- **WHEN** the alignment report is formatted or serialized
- **THEN** each required model obligation has visible binding status.
