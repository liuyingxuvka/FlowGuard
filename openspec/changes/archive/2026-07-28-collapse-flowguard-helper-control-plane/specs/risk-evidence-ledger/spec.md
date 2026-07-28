## ADDED Requirements

### Requirement: RiskEvidenceLedger owns final broad confidence
RiskEvidenceLedger SHALL be the final broad confidence owner for done, release,
archive, publish, production, or full claims that depend on FlowGuard route
evidence.

#### Scenario: Closure helper pass is insufficient
- **WHEN** a closure helper, maintenance scan, or child report is passing
- **THEN** a broad claim MUST still be unsupported until RiskEvidenceLedger
  consumes current proof rows for the relevant risks

#### Scenario: Single-route matrix is insufficient
- **WHEN** ContractExhaustionMesh generated cases pass a single route matrix
- **THEN** RiskEvidenceLedger MUST require composite handoff acceptance for
  any case that needs multi-route closure before broad confidence is allowed

### Requirement: Ledger consumes owner-route evidence only
RiskEvidenceLedger SHALL consume current evidence from public owner routes or
explicitly identified helper evidence that has been consumed by a public owner.

#### Scenario: Internal helper evidence bypasses owner
- **WHEN** a risk row cites only internal helper evidence that no owner route
  consumed
- **THEN** the ledger MUST report unsupported confidence for that row
