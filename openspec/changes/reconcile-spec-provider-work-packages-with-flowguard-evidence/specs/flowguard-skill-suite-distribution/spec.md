## ADDED Requirements

### Requirement: Managed skills declare V1 authority lifecycle
Every managed FlowGuard V2 contract source SHALL declare whether former V1 runtime surfaces are migration evidence or formally retired, and generated/installed artifacts SHALL preserve that decision.

#### Scenario: V2 exists but retirement evidence is incomplete
- **WHEN** a skill has a V2 contract trio and former V1 migration surfaces but lacks official calibration and retirement receipts
- **THEN** it SHALL resolve as `v2-migration`, V2 SHALL be the only runtime authority, and V1 SHALL NOT provide closure or release success

#### Scenario: Retired V1 surface remains
- **WHEN** a skill claims `v2-only` but a former V1 work contract, underscore check manifest, or V1 run record remains
- **THEN** runtime-authority, suite, and install validation SHALL block

#### Scenario: Formal retirement is attempted
- **WHEN** current content-addressed positive/shallow calibration, eligibility, completion, rollback, and residual-absence evidence all pass
- **THEN** the official atomic retirement workflow MAY remove only the exact former V1 runtime surfaces and prove `v2-only`
