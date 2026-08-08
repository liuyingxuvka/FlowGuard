## ADDED Requirements

### Requirement: Current intent completeness uses the independent model-owner denominator
Project intent readiness SHALL compare one effective current-intent owner binding with the complete model-owner denominator independently derived from the exact current observed model snapshot. Every current model owner SHALL have one binding to its exact current realization relation and one or more active cumulative intent contributions. Missing, extra, duplicate, foreign, root-level, or unresolved bindings SHALL block intent readiness. Contributions and bindings SHALL NOT define or shrink their own denominator.

#### Scenario: Latest revision describes only two of sixty current model owners
- **WHEN** the current observed snapshot contains sixty model owners
- **AND** the latest delta directly changes only two owners
- **THEN** intent readiness still requires exact effective bindings for all sixty owners
- **AND** the two-member delta SHALL NOT be reported as complete current system intent

#### Scenario: A contribution tries to define its own smaller denominator
- **WHEN** the cumulative view or projected inventory supplies bindings for fewer owners than the independently observed snapshot
- **THEN** readiness reports the exact missing owner identities and remains blocked
- **AND** no no-intent rationale, root binding, or shared fallback owner may close those missing rows

#### Scenario: One intent source supports several owners without shared ownership
- **WHEN** one source artifact or design goal legitimately informs several exact model owners
- **THEN** each owner SHALL retain its own owner-specific contribution record, compact binding, and exact realization relation
- **AND** those records MAY reference the same source artifact so its body is not copied, but one active contribution SHALL NOT acquire several primary owners

### Requirement: Every current behavior block consumes effective model intent
Behavior readiness SHALL use the independently observed current behavior-block denominator and require every block to consume at least one active cumulative intent contribution through its exact current model owner. A behavior SHALL be blocked when its intent reference is empty, missing, inactive, foreign to its model owner, or derived only from implementation code. Shared intent MAY cover sibling blocks only through their exact owner binding; behavior coverage SHALL remain distinct from model-owner coverage.

#### Scenario: Model owners are complete but one behavior has no intent
- **WHEN** the current-intent view covers every model owner
- **AND** one independently observed behavior block has no effective intent reference
- **THEN** model-owner intent coverage may remain complete
- **BUT** behavior and static-blueprint readiness remain blocked with that exact behavior identity

#### Scenario: Sibling behaviors consume one owner intent
- **WHEN** several current behavior blocks belong to one exact model owner
- **AND** that owner binding references one active current contribution
- **THEN** every sibling may consume the shared contribution through that owner binding
- **AND** no copied intent body or second intent authority is required

#### Scenario: Behavior references another owner's intent
- **WHEN** a behavior block cites an active contribution that is not bound to its exact current model owner
- **THEN** behavior readiness reports a cross-owner intent binding and remains blocked
- **AND** matching words, implementation similarity, or a root-level relation SHALL NOT authorize the reference
