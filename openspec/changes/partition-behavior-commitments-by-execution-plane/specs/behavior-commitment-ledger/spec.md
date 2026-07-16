## ADDED Requirements

### Requirement: Commitments declare one behavior plane
Every in-scope commitment SHALL declare exactly one production behavior plane: `product_runtime`, `agent_operation`, or `development_process`.

#### Scenario: Commitment form and plane are distinct
- **WHEN** a commitment declares a `commitment_kind` such as `ui`, `cli`, `workflow`, or `process`
- **THEN** ledger review SHALL still require a separate valid `behavior_plane`

#### Scenario: Unclassified migration row cannot pass
- **WHEN** an upgrade cannot classify a legacy commitment and records it as `unclassified` in migration diagnostics
- **THEN** the runtime ledger SHALL reject the row for broad confidence until it is classified

### Requirement: Commitments declare structured actor kind
Every commitment SHALL declare one actor kind from `end_user`, `external_system`, `application`, `ai_agent`, `developer`, or `automation`, while retaining a human-readable actor label.

#### Scenario: Free-text actor lacks kind
- **WHEN** a commitment has an actor label but no valid actor kind
- **THEN** ledger review SHALL report `commitment_actor_kind_missing_or_invalid`

### Requirement: Commitments expose bounded lookup bindings
The ledger SHALL support task terms, path patterns, tool ids, error signatures, and workflow families as optional lookup bindings without making those bindings a second behavior authority.

#### Scenario: Model miss adds reusable error signature
- **WHEN** a same-plane Model Miss produces a stable observed error signature
- **THEN** the owning commitment MAY add that signature to its lookup binding
- **AND** the commitment id and primary owner model SHALL remain unchanged

### Requirement: Canonical project ledger is machine-readable
Project templates SHALL store behavior commitments in one canonical `.flowguard/behavior_commitment_ledger/ledger.json` artifact and SHALL treat generated check results as evidence rather than source data.

#### Scenario: Project model loads canonical ledger
- **WHEN** the generated project BCL model is imported
- **THEN** it SHALL load and validate `ledger.json`
- **AND** SHALL NOT reconstruct a separate embedded commitment inventory

#### Scenario: Result artifact cannot become source
- **WHEN** `run_checks.py` writes `result.json`
- **THEN** later ledger loading SHALL continue to read `ledger.json`, not the prior result

### Requirement: Legacy ledger migration is boundary-only
FlowGuard SHALL provide dry-run and apply migration for the known legacy artifact shape and SHALL NOT execute unknown custom Python ledgers during conversion.

#### Scenario: Dry-run is non-mutating
- **WHEN** the upgrader reviews a legacy ledger without apply mode
- **THEN** it SHALL report proposed plane, actor, relation, and source changes without modifying the source or target

#### Scenario: Unknown custom Python requires manual conversion
- **WHEN** a Python ledger does not match the known official template shape
- **THEN** the upgrader SHALL report a manual-conversion blocker
- **AND** SHALL NOT execute that file to obtain commitments

#### Scenario: Migration activates one authority
- **WHEN** a canonical ledger conversion is applied successfully
- **THEN** the project adapter SHALL load only the canonical ledger
- **AND** the legacy embedded inventory SHALL no longer be an active success path

### Requirement: New templates use plane-aware commitment ids
New generated commitments SHALL default to `commitment:product:*`, `commitment:agent:*`, or `commitment:development:*` ids while preserving existing ids during the first migration when references remain valid.

#### Scenario: Existing id remains stable
- **WHEN** a legacy commitment can be classified without changing its semantic identity
- **THEN** migration SHALL preserve its id and update only the new plane-aware fields and relations

## MODIFIED Requirements

### Requirement: Dependencies remain explicit and closed
FlowGuard SHALL represent runtime commitment relationships as typed `relations` that reference registered commitments within the same ledger boundary and obey the declared same-plane/cross-plane relation matrix. Legacy `dependency_commitment_ids` SHALL be accepted only by the explicit artifact-upgrade boundary.

#### Scenario: Unknown relation target blocks
- **WHEN** a relation refers to an unknown commitment id
- **THEN** the ledger review SHALL report `commitment_relation_target_unknown`

#### Scenario: Cross-plane relation lacks rationale
- **WHEN** a relation crosses behavior planes without a non-empty rationale
- **THEN** the ledger review SHALL report `commitment_cross_plane_relation_missing_rationale`

#### Scenario: Relation direction is invalid
- **WHEN** a relation type and source/target plane pair is outside the declared relation matrix
- **THEN** the ledger review SHALL report `commitment_relation_plane_mismatch`

#### Scenario: Deterministic same-plane legacy dependency migrates
- **WHEN** a legacy dependency target exists and both commitments are deterministically classified in the same plane
- **THEN** the upgrader SHALL convert it to a `depends_on` relation

#### Scenario: Ambiguous legacy dependency requires review
- **WHEN** a legacy dependency crosses planes or either plane cannot be determined
- **THEN** the upgrader SHALL keep migration incomplete and require an explicit typed relation decision
