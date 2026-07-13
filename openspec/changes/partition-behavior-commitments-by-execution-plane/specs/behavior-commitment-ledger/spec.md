## ADDED Requirements

### Requirement: Commitments declare one behavior plane
Every in-scope commitment SHALL declare exactly one production behavior plane: `product_runtime`, `agent_operation`, or `development_process`.

#### Scenario: Commitment form and plane are distinct
- **WHEN** a commitment declares a `commitment_kind` such as `ui`, `cli`, `workflow`, or `process`
- **THEN** ledger review SHALL still require a separate valid `behavior_plane`

#### Scenario: Unclassified row cannot pass
- **WHEN** a commitment declares `unclassified`
- **THEN** the current ledger SHALL reject the row until the source declares one production plane

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

### Requirement: Former ledger shapes fail closed
FlowGuard SHALL accept only the canonical current ledger shape and SHALL NOT provide a migration reader, converter, upgrade command, alias, or second successful authority for former Python or JSON shapes.

#### Scenario: Former embedded Python inventory is presented
- **WHEN** a project presents commitments only through the former embedded Python inventory
- **THEN** current ledger loading SHALL fail closed
- **AND** SHALL NOT execute that file to obtain commitments

#### Scenario: Former JSON shape is presented
- **WHEN** a ledger uses a former field set or artifact shape
- **THEN** current ledger loading SHALL reject it with an actionable current-shape finding
- **AND** SHALL NOT translate it automatically

#### Scenario: Direct replacement activates one authority
- **WHEN** the project source is rewritten to the canonical current ledger
- **THEN** the project adapter SHALL load only that ledger
- **AND** the former embedded inventory SHALL remain a rejected negative fixture

### Requirement: New templates use plane-aware commitment ids
New generated commitments SHALL default to `commitment:product:*`, `commitment:agent:*`, or `commitment:development:*` ids. An existing semantic id MAY be authored directly in the current ledger when its current references remain valid; this is current authorship, not legacy translation.

#### Scenario: Current id remains stable
- **WHEN** a current commitment is rewritten without changing its semantic identity
- **THEN** the current source MAY retain its id while declaring all required plane-aware fields and relations

## MODIFIED Requirements

### Requirement: Dependencies remain explicit and closed
FlowGuard SHALL represent runtime commitment relationships as typed `relations` that reference registered commitments within the same ledger boundary and obey the declared same-plane/cross-plane relation matrix. Former `dependency_commitment_ids` input SHALL be rejected at every current entrypoint.

#### Scenario: Unknown relation target blocks
- **WHEN** a relation refers to an unknown commitment id
- **THEN** the ledger review SHALL report `commitment_relation_target_unknown`

#### Scenario: Cross-plane relation lacks rationale
- **WHEN** a relation crosses behavior planes without a non-empty rationale
- **THEN** the ledger review SHALL report `commitment_cross_plane_relation_missing_rationale`

#### Scenario: Relation direction is invalid
- **WHEN** a relation type and source/target plane pair is outside the declared relation matrix
- **THEN** the ledger review SHALL report `commitment_relation_plane_mismatch`

#### Scenario: Former dependency field is rejected
- **WHEN** a current ledger row carries `dependency_commitment_ids`
- **THEN** ledger loading SHALL reject the row rather than translating it

#### Scenario: Typed relation decision is explicit
- **WHEN** the desired dependency crosses planes or its direction is unclear
- **THEN** the current author SHALL choose an allowed typed relation and rationale before the ledger can pass
