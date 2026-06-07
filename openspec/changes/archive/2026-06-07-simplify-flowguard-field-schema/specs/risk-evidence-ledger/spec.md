## ADDED Requirements

### Requirement: Risk Rows Use Compact Gate Lists
The risk evidence ledger SHALL represent optional route-specific confidence
checks with typed gate rows instead of route-specific columns on each
`RiskEvidenceRow`.

#### Scenario: One required topology gate
- **WHEN** a risk requires topology-hazard review evidence
- **THEN** the row records one gate with kind `topology_hazard`, the evidence
  id, required/current flags, confidence, and scoped reasons

#### Scenario: No unused gate fields
- **WHEN** a risk has no model split, test split, or analogous defect scan
- **THEN** the row does not expose empty model-split, test-split, or
  analogous-scan fields

### Requirement: Removed Risk Row Fields Are Not Accepted
The risk evidence ledger MUST reject or fail fast on removed route-specific
gate constructor fields rather than silently accepting legacy aliases.

#### Scenario: Old gate field supplied
- **WHEN** code constructs a `RiskEvidenceRow` with
  `topology_hazard_required`
- **THEN** construction fails because the field has been removed

## REMOVED Requirements

### Requirement: Route-Specific Gate Columns
**Reason**: Route-specific columns make every risk row carry dozens of unused
fields and cause agents to overfill low-frequency gate data.

**Migration**: Use `RiskEvidenceGate(kind=..., evidence_id=..., required=...)`
inside `RiskEvidenceRow.gates`.
