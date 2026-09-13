## ADDED Requirements

### Requirement: Runnable UI claim scope is explicit and non-omissible
UI Flow Structure SHALL require every implemented or runnable UI validation to
declare `complete` or `scoped` claim scope. A complete claim MUST provide the
current capability inventory and coverage review, observed UI inventory,
visible-surface review, content-admission plan, implementation run evidence,
and every declared blindspot. A scoped claim MUST name every omitted evidence
class and MUST NOT support broad done, release, or product-complete confidence.

#### Scenario: Missing runnable claim scope blocks

- **WHEN** an implemented or runnable UI validation omits its claim scope
- **THEN** UI validation SHALL report a missing claim-scope blocker and SHALL
  NOT infer complete scope from passing controls or implementation runs

### Requirement: Runnable UI evidence must include an independently produced proof artifact

When a UI implementation or functional-chain validation opts into a runnable
real-surface claim, a non-empty `evidence_ref` and caller-authored
`result=passed` SHALL NOT be sufficient. Each run and click-to-effect step
MUST consume a current `ProofArtifactRef` with a producer route, executed
command, terminal result path, zero exit code, subject and artifact
fingerprints, an external-contract assertion scope, and a separately
verifiable immutable producer receipt. The receipt MUST bind the same owner,
source/model/toolchain/environment identities, terminal-success state, result
fingerprint, and confirmed descendant cleanup. Missing, stale, internal-only,
progress-only, pathless, hash-mismatched, receipt-less, or otherwise
unverifiable proof MUST block the runnable claim while preserving schema-only
and explicitly scoped model tests.

#### Scenario: A fake evidence URI cannot qualify a runnable claim

- **WHEN** a runnable UI validation supplies `evidence_ref="evidence://..."`
  and `result="passed"` but no current proof artifact
- **THEN** the validation reports a missing runtime proof artifact and does not
  support broad runnable confidence

#### Scenario: A current external proof artifact qualifies a runnable claim

- **WHEN** every required run and step consumes a current externally scoped
  proof artifact with terminal fingerprints and exit code zero
- **THEN** the validation may support broad runnable confidence, subject to the
  independent UI inventory, journey, capability, content, and recovery gates

#### Scenario: A result file without a producer receipt cannot qualify

- **WHEN** a runnable UI validation points at a real result file with a matching
  hash but supplies no separately verifiable producer receipt
- **THEN** the validation reports a receipt blocker and does not support broad
  runnable confidence

#### Scenario: Complete claim omits capability coverage
- **WHEN** a runnable UI validation declares complete scope but supplies no
  current capability inventory or capability coverage review
- **THEN** UI validation blocks instead of treating omission as success

#### Scenario: Complete claim omits content admission
- **WHEN** a runnable UI validation declares complete scope but supplies no
  current content-admission plan
- **THEN** UI validation blocks even when controls and implementation runs pass

#### Scenario: Empty content plan is explicitly current
- **WHEN** the reviewed UI has no non-action candidate content
- **AND** an explicit current empty content-admission plan binds the same
  observed inventory and implementation revision
- **THEN** the empty plan satisfies the content-plan input without inventing
  candidate rows

#### Scenario: Scoped claim keeps omissions visible
- **WHEN** a validation intentionally reviews only one UI capability or journey
- **THEN** the result lists omitted inventories and evidence classes and cannot
  satisfy a complete runnable or release claim
