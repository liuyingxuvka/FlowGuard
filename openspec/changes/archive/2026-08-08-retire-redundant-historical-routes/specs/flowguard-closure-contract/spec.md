## ADDED Requirements

### Requirement: Closure consumes maturation and current-owner coverage evidence
FlowGuard Closure Contract SHALL consume an exact current ModelMaturation
decision and current evidence from every required affected owner when broad
confidence depends on understanding sufficiency. Closure SHALL validate those
identities and terminal states without creating an independent sufficiency
review or rejudging the owner evidence.

#### Scenario: Required maturation evidence is missing
- **WHEN** broad closure requires understanding sufficiency
- **AND** no exact current accepted ModelMaturation evidence covers the task and
  selected owner closure
- **THEN** closure MUST block full FlowGuard confidence

#### Scenario: A required current-owner coverage item is open
- **WHEN** maturation or an affected owner reports a required coverage item as
  missing, scoped, blocked, stale, skipped, not run, progress-only, or
  unresolved
- **THEN** closure MUST preserve that exact state and downgrade or block the
  broad claim

#### Scenario: Maturation and owner evidence are current
- **WHEN** the exact task, source, owner closure, model, code, test, topology,
  and evidence identities match the accepted maturation decision
- **THEN** closure MAY consume the terminal evidence subject to its remaining
  closure requirements
- **AND** it MUST NOT require a separate model-angle report

## REMOVED Requirements

### Requirement: Closure consumes model-angle review evidence
**Reason**: The independent model-angle evidence gate duplicates typed ModelMaturation and affected-owner coverage evidence.
**Migration**: Consume the exact current maturation decision and required current-owner terminal evidence directly.
