## ADDED Requirements

### Requirement: Closure contract consumes complete bug repair evidence
The Closure Contract SHALL block or scope final confidence for a bug repair
unless current evidence covers the observed failure, same-class bug class,
model obligation, owner code contract, test evidence, stale-evidence review,
old-path/fallback disposition when relevant, and final risk-ledger decision.

#### Scenario: Complete bug repair closure passes
- **WHEN** a bug repair has current model-miss review, model-code-test
  alignment, freshness, compatibility/legacy-path, and risk-ledger evidence
- **THEN** the Closure Contract may allow full confidence for the repaired
  in-scope risk

#### Scenario: Missing bug repair link scopes claim
- **WHEN** a bug repair lacks current same-class proof, code-contract binding,
  old-path disposition, or freshness evidence
- **THEN** the final confidence claim remains scoped or blocked
