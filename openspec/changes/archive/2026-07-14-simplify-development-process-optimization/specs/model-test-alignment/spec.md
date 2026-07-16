## ADDED Requirements

### Requirement: Repair groups reuse ordinary model-code-test alignment
Model-Test Alignment SHALL use its existing model obligations, primary owner code contracts, test evidence, freshness, and commitment bindings to prove every `affected_obligation_id` referenced by a process repair group. The repair group SHALL cite the corresponding current ordinary `owner_evidence_ids` and its required/current revalidation evidence. Model-Test Alignment SHALL NOT create a strategy-specific binding, cluster owner, or repair-batch owner.

#### Scenario: Repair group obligation has current ordinary alignment
- **WHEN** a repair group references an obligation whose primary code owner and current test evidence are present in the ordinary alignment plan
- **THEN** DPF may consume that alignment evidence for affected revalidation closure

#### Scenario: Repair group obligation lacks a primary owner
- **WHEN** a repair group references an obligation with no current primary owner code contract
- **THEN** ordinary Model-Test Alignment blocks closure without a strategy-specific fallback binding

## REMOVED Requirements

### Requirement: Strategy bindings resolve to model and code owners
**Reason**: `ProcessStrategyAlignmentBinding` duplicates the ordinary model-obligation, primary-code-owner, test-evidence, and freshness relationship already owned by Model-Test Alignment.

**Migration**: Delete the strategy binding type and `strategy_bindings` field. Repair groups reference affected obligation ids, and DPF consumes current ordinary MTA evidence for those ids. No replacement alias or parallel binding is added.
