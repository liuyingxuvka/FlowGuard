## ADDED Requirements

### Requirement: Development order makes path review conditional and current
DevelopmentProcessFlow SHALL run the affected model's lightweight path-quality review after requirement, intent, and owner closure are known and before behavior-sensitive implementation begins. Triggered deep review SHALL close before the corresponding broad implementation claim, while current `single_clear_path` results SHALL proceed without deep ceremony. Implementation or evidence changes SHALL stale and minimally refresh affected results before activation.

#### Scenario: Ordinary affected model has one clear path
- **WHEN** the lightweight result is current and no deep trigger applies
- **THEN** implementation proceeds with the compact result and no candidate expansion

#### Scenario: Implementation changes consumed identities
- **WHEN** code, helper, test, oracle, provider, dependency, or evidence changes after review
- **THEN** the affected result is refreshed before current activation
- **AND** unrelated models are not rerun unless topology requires them
