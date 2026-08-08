## ADDED Requirements

### Requirement: Model-miss confidence consumes one canonical maturation result
After a model miss, RiskEvidenceLedger SHALL consume the exact affected commitment, canonical ContractExhaustion observed/same-class case set, updated model/code/test bindings, affected-topology replay, and one current ModelMaturation result. It MUST NOT require separate analogous-scan or model-angle evidence for the same closure claim.

#### Scenario: Model miss is fully repaired
- **WHEN** the canonical miss path has current owner, finite cases, executable oracles, updated bindings, replay evidence, and maturation result
- **THEN** the ledger evaluates that single result for the bounded claim

#### Scenario: Legacy parallel gate remains required
- **WHEN** a risk row still requires an independent analogous-scan or model-angle gate for the same miss
- **THEN** ledger schema/currentness validation reports duplicate legacy responsibility

## REMOVED Requirements

### Requirement: Risk rows can require analogous defect scan gates
**Reason**: ContractExhaustion now owns finite same-class cases and ModelMaturation publishes the one consumed result.
**Migration**: Bind the risk row to canonical case and maturation evidence.

### Requirement: Risk ledger consumes model-angle evidence
**Reason**: Concrete model-depth gaps are part of the current maturation result.
**Migration**: Consume the affected owner's current ModelMaturation evidence.
