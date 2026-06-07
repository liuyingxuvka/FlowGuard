## ADDED Requirements

### Requirement: API Registry Reflects Thin Breaking Schema
FlowGuard's public API registry SHALL export the new thin schema names and MUST
not preserve removed dataclass field aliases as public compatibility helpers.

#### Scenario: Thin gate type exported
- **WHEN** users import risk evidence ledger helpers from `flowguard`
- **THEN** `RiskEvidenceGate` is exported with the ledger helpers

#### Scenario: Removed aliases absent
- **WHEN** API-surface tests inspect first-read or full exports
- **THEN** removed compatibility names and old field aliases are absent
