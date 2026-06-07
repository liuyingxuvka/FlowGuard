# auto-model-test-mesh-split-derivation Specification

## Purpose
This capability defines FlowGuard's Auto Model Test Mesh Split Derivation behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Automatic split diagnostics
FlowGuard SHALL provide an executable helper that reviews model and validation
evidence metrics and decides whether direct evidence is small enough to consume
or must route through ModelMesh/TestMesh.

#### Scenario: Small direct evidence may continue
- **WHEN** a model/test candidate stays under configured thresholds and has no
  progress-only, pending, release-only, or broad-parent evidence flags
- **THEN** the auto split report returns OK and no required split routes

#### Scenario: Oversized model requires ModelMesh
- **WHEN** a model candidate exceeds the configured state threshold or has
  pending budgeted states
- **THEN** the auto split report requires ModelMesh split review
- **AND** direct parent confidence cannot rely on that model as complete proof

#### Scenario: Slow or broad validation requires TestMesh
- **WHEN** a test candidate exceeds the configured duration/test-count threshold
  or covers too many independent obligations as one broad command
- **THEN** the auto split report requires TestMesh split review
- **AND** direct parent confidence cannot rely on that test as complete proof

### Requirement: Target split recommendation
FlowGuard SHALL emit target ModelMesh/TestMesh split derivation recommendations
when a split is required and the candidate includes proposed children and parent
partition items.

#### Scenario: Model split recommendation has enough structure
- **WHEN** an oversized model candidate includes suggested child model ids and
  covered partition item ids
- **THEN** the report includes a `ModelTargetSplitDerivation` recommendation

#### Scenario: Test split recommendation has enough structure
- **WHEN** a slow or broad test candidate includes suggested child suite ids and
  covered partition item ids
- **THEN** the report includes a `TestTargetSplitDerivation` recommendation

#### Scenario: Missing child structure blocks broad confidence
- **WHEN** a split is required but the candidate has no suggested child ids or
  no covered partition items
- **THEN** the report includes a blocker explaining that target split derivation
  is missing

### Requirement: Development process split gate
DevelopmentProcessFlow SHALL consume auto split diagnostics before done, release,
archive, or publish confidence.

#### Scenario: Claim relies on oversized model evidence
- **WHEN** a process claim depends on evidence whose auto split status requires
  ModelMesh and no current split review exists
- **THEN** DevelopmentProcessFlow blocks the claim with a model split decision

#### Scenario: Claim relies on slow validation evidence
- **WHEN** a process claim depends on evidence whose auto split status requires
  TestMesh and no current split review exists
- **THEN** DevelopmentProcessFlow blocks the claim with a test split decision

### Requirement: Risk ledger split gate
The Risk Evidence Ledger SHALL represent required model/test split gates before
full confidence.

#### Scenario: Required model split gate is missing
- **WHEN** a risk row requires a model split gate but no current gate id/status
  is present
- **THEN** the ledger blocks full confidence

#### Scenario: Required test split gate is scoped
- **WHEN** a risk row has a current test split gate but its confidence is scoped
- **THEN** the ledger returns scoped confidence rather than full confidence
