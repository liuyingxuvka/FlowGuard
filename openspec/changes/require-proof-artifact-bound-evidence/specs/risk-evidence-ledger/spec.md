## MODIFIED Requirements

### Requirement: Evidence freshness and scope affect confidence
FlowGuard SHALL distinguish current proof evidence from stale, skipped,
progress-only, internal-path-only, not-run, declaration-only, missing-artifact,
and explicitly out-of-scope evidence before full confidence is claimed.

#### Scenario: Stale evidence blocks full confidence
- **WHEN** a risk row's proof evidence is stale or covers an older artifact
  version
- **THEN** the ledger review reports stale evidence and does not return full
  confidence

#### Scenario: Declaration-only evidence blocks strict full confidence
- **WHEN** strict ledger proof is required and a risk row's passing evidence
  does not include a current proof artifact reference
- **THEN** the ledger review reports declaration-only evidence and does not
  return full confidence

#### Scenario: Internal-path-only proof is not external proof
- **WHEN** a risk row's proof evidence only exercises an internal helper or
  implementation path while a public code contract is required
- **THEN** the ledger review reports internal-path-only evidence
