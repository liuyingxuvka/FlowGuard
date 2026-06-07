## ADDED Requirements

### Requirement: Revalidation recommendations expose AI rerun metadata
DevelopmentProcessFlow SHALL include route, proof-artifact, freshness-gap, and
claim-scope metadata in revalidation recommendations so AI agents can identify
the minimum rerun or evidence-refresh action.

#### Scenario: Stale evidence recommends concrete rerun
- **WHEN** evidence is stale because a covered artifact or verifier artifact
  changed
- **THEN** the recommendation SHALL include the requirement id, evidence id,
  command when known, artifact ids, freshness gap codes, and claim scopes that
  remain blocked until rerun

#### Scenario: Proof artifact is required
- **WHEN** the lifecycle plan requires proof artifacts and a recommendation
  concerns missing or stale evidence
- **THEN** the recommendation SHALL mark that proof artifact evidence is
  required before broad claim confidence can be promoted
