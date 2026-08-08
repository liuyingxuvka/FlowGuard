## ADDED Requirements

### Requirement: Every affected model has one explicit native owner
A ModelRevisionSet SHALL map every changed or affected model and relation to exactly one declared native owner. Missing or unknown ownership SHALL block candidate acceptance and SHALL NOT be assigned to a generic ModelMesh or self-maintenance owner.

#### Scenario: Changed model id has no owner mapping
- **WHEN** a candidate diff contains a model whose native owner is absent from the frozen owner plan
- **THEN** the revision set SHALL be blocked before activation

### Requirement: Intent dispositions cover every changed model identity
When exact changed-target enforcement is active and a revision contains one or more intent contributions, the union of `changed_model_ids` from accepted dispositions SHALL cover every raw semantic identity that the intent-disposition schema can express. This denominator consists only of `obligation:`, `state:`, `transition:`, `invariant:`, and `relation:` ids found in revision-member changed elements or raw changed-relation ids. Model-instance, root, system, fingerprint, coverage, test, evidence-freshness, and other revision-accounting wrappers remain governed revision evidence but SHALL NOT be treated as unmapped intent. Accepted semantic targets outside the exact semantic diff SHALL remain invalid. A contribution-free revision with an explicit evidence-bound no-declared-intent rationale SHALL remain outside this contribution-coverage comparison.

#### Scenario: One diff member has no accepted intent mapping
- **WHEN** the exact revision diff changes two raw semantic identities but accepted intent dispositions map only one
- **THEN** intent review SHALL report `intent_changed_target_unmapped` with the exact missing identity
- **AND** the revision SHALL NOT be accepted

#### Scenario: Production diff also contains internal wrappers
- **WHEN** a revision contains model-instance, root, system, fingerprint, coverage, test, or freshness wrapper changes plus raw relations
- **AND** accepted dispositions cover every raw semantic relation and other expressible semantic id
- **THEN** the internal wrappers SHALL NOT create unmapped-intent findings
- **AND** the revision MAY pass this coverage gate subject to every other revision requirement

#### Scenario: Several accepted contributions jointly cover the diff
- **WHEN** accepted dispositions independently map disjoint changed model identities whose union covers the exact revision diff
- **THEN** changed-target coverage MAY pass subject to every other intent and revision gate

#### Scenario: Evidence-bound no-intent revision has no contributions
- **WHEN** a contribution-free revision carries the complete current no-declared-intent rationale and evidence required by the revision contract
- **THEN** this contribution-coverage comparison SHALL NOT create an unmapped-target finding

### Requirement: Revision acceptance consumes exact per-owner evidence
Each affected owner SHALL contribute its own exact current receipt covering its declared model members and obligations. An aggregate parent receipt MAY compose those children but SHALL NOT be copied or relabeled as their producer evidence.

#### Scenario: Aggregate receipt is duplicated across owner rows
- **WHEN** one parent receipt is inserted as the native receipt for several owners without exact covered-member producer rows
- **THEN** revision validation SHALL reject every unsupported owner row

### Requirement: Revision building independently re-verifies native-owner evidence
Before a native-owner receipt can make a revision evidence-complete, the revision builder SHALL reload that exact receipt from the canonical receipt store, derive the current owner contract, input, command, toolchain, environment, proof, result, and child-receipt context, and run the native receipt verifier itself. The aggregate receipt and every consumed child SHALL remain present with the same content identity through revision publication. A caller-supplied verification result MAY be carried as an immutable comparison artifact but SHALL match the independently derived result exactly and SHALL NOT be accepted as its own authority.

#### Scenario: Caller repairs a tampered receipt by self-reporting pass
- **WHEN** a caller changes a receipt contract, input, command, toolchain, environment, proof, result, or child identity, recomputes wrapper fingerprints, and supplies `current=true`, `eligible=true`, and `pass`
- **THEN** revision building SHALL reject the evidence against the canonical store and current verification context

#### Scenario: Canonical receipt is exact current
- **WHEN** the receipt loaded from the canonical store passes the independently derived current context and the supplied comparison result is exactly equal
- **THEN** the corresponding native owner MAY contribute evidence for only its exact affected obligations

#### Scenario: Canonical evidence disappears during revision building
- **WHEN** an aggregate receipt or one of its mapped child receipts is removed or replaced after initial verification but before the revision artifacts are published
- **THEN** revision building SHALL re-read the canonical store and block publication

### Requirement: Full model parents consume canonical execution composition
A model-regression parent used for revision building SHALL reference one canonical content-addressed execution receipt whose native contract binds the original tier, claim scope, complete selected-model denominator, current manifest, terminal result, and exact child receipts. The mutable parent wrapper and its recomputable fingerprint SHALL NOT be execution authority.

#### Scenario: A scoped parent wrapper is relabeled as full
- **WHEN** a scoped run happened to select the same model ids as the current full denominator and a caller rewrites its wrapper tier and claim scope to `full`
- **THEN** revision building SHALL reject it because the canonical execution receipt remains bound to the scoped contract

#### Scenario: The exact full parent is current
- **WHEN** the wrapper references the current canonical full-selection execution receipt and every consumed model child remains exact-current
- **THEN** the parent MAY support revision building within that exact manifest boundary

### Requirement: Multi-model blueprint revisions activate atomically
A blueprint-affecting revision SHALL freeze the observed base, complete candidate diff, affected closure, provider and inventory identities, per-owner receipts, and candidate snapshot before one atomic accept-and-activate decision.

#### Scenario: One affected model lacks current evidence
- **WHEN** all but one affected model have current passing owner receipts
- **THEN** no member of the candidate revision SHALL become observed authority
