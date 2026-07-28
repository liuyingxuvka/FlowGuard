## ADDED Requirements

### Requirement: Runnable UI claim scope is explicit and non-omissible
UI Flow Structure SHALL require every implemented or runnable UI validation to
declare `complete` or `scoped` claim scope. A complete claim MUST provide the
current capability inventory and coverage review, observed UI inventory,
visible-surface review, content-admission plan, implementation run evidence,
and every declared blindspot. A scoped claim MUST name every omitted evidence
class and MUST NOT support broad done, release, or product-complete confidence.

#### Scenario: Complete claim omits capability coverage
- **WHEN** a runnable UI validation declares complete scope but supplies no
  current capability inventory or capability coverage review
- **THEN** UI validation blocks instead of treating omission as success

#### Scenario: Complete claim omits content admission
- **WHEN** a runnable UI validation declares complete scope but supplies no
  current content-admission plan
- **THEN** UI validation blocks even when controls and implementation runs pass

#### Scenario: Empty content plan is explicitly current
- **WHEN** the reviewed UI has no non-action candidate content
- **AND** an explicit current empty content-admission plan binds the same
  observed inventory and implementation revision
- **THEN** the empty plan satisfies the content-plan input without inventing
  candidate rows

#### Scenario: Scoped claim keeps omissions visible
- **WHEN** a validation intentionally reviews only one UI capability or journey
- **THEN** the result lists omitted inventories and evidence classes and cannot
  satisfy a complete runnable or release claim
