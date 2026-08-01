## ADDED Requirements

### Requirement: Broad closure requires exact current model maturation
Closure Contract SHALL require a current task/candidate/coverage-bound Model Maturation result for broad done, release, publish, production, or complete-FlowGuard claims and SHALL verify that Risk Evidence Ledger consumed the same maturation identity.

#### Scenario: Maturation evidence is absent
- **WHEN** a broad closure plan has no current maturation result or typed maturation evidence report
- **THEN** closure MUST NOT return full confidence

#### Scenario: Maturation is scoped or mismatched
- **WHEN** maturation is scoped, blocked, non-terminal, stale, has open gaps, or does not match the closure task/candidate/coverage identity
- **THEN** closure MUST block or scope the claim and report the exact mismatch

#### Scenario: Risk and closure share exact maturation
- **WHEN** the matching closed-for-task maturation result is current and the risk ledger identifies the same result
- **THEN** the maturation gate MAY support full closure while Closure Contract remains a material and identity checker rather than a second sufficiency judge
