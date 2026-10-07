## MODIFIED Requirements

### Requirement: Full model composition shares one frozen validation observation
A bounded full-model planning, execution, or parent-composition operation SHALL resolve the complete repository input manifest, receipt inventory, owner contexts, and exact-current child receipt set once for its initial frozen observation. Every sibling child decision and parent row in that operation SHALL consume those same exact identities rather than rebuilding the complete observation per child, per row, or per aggregate. For a serial one-job owner path, each terminal-success leaf SHALL be published only after its exact owner-local input identity, cleanup result, and tracked-metadata guard are current; that bounded check SHALL reuse the frozen manifest and SHALL NOT rebuild the full repository inventory or rescan all receipts per leaf. The final parent SHALL still perform the complete live source and receipt comparison, receipt reconciliation, and compare-and-swap publication. The existing parallel batch path SHALL retain its batch publication boundary and SHALL NOT be broadened by this serial rule.

#### Scenario: Fifty-one model children compose one parent
- **WHEN** one full-model operation plans or composes all required model children from unchanged repository and receipt-store inputs
- **THEN** instrumentation SHALL show one complete initial validation observation shared by every child decision
- **AND** the parent SHALL name the exact observation identity it consumed

#### Scenario: One child identity changes during composition
- **WHEN** the final freshness observation differs from the frozen observation for any consumed model input, owner context, receipt, or required child identity
- **THEN** parent publication SHALL be blocked as stale
- **AND** the operation SHALL NOT silently rebuild selected rows against the newer state or fall back to a full rerun

#### Scenario: Serial successful leaf publishes before the next owner
- **WHEN** a one-job model owner terminates successfully, descendant cleanup is confirmed, its exact owner-local inputs still match the frozen owner context, and the tracked-metadata guard is unchanged
- **THEN** the orchestrator SHALL persist that immutable successful leaf before starting the next serial owner
- **AND** it SHALL use a bounded owner-local freshness check without rebuilding the complete repository input manifest or rescanning the full receipt inventory

#### Scenario: Serial owner input or tracked source changes before leaf publication
- **WHEN** the owner-local freshness or tracked-metadata guard detects changed input, unconfirmed cleanup, or tracked mutation
- **THEN** the affected leaf SHALL NOT be published as terminal success
- **AND** any earlier exact-current successful leaf SHALL remain independently reusable

#### Scenario: Parallel leaves retain batch publication
- **WHEN** multiple selected model runners execute in a parallel batch
- **THEN** the orchestrator SHALL retain one complete final repository observation before publishing their validation-owner receipts
- **AND** every executed leaf SHALL use its owner context from that observation
- **AND** one post-publication receipt reconciliation SHALL verify the exact new receipts without a third complete repository observation

#### Scenario: Final source or receipt drift blocks the parent
- **WHEN** the final complete observation finds source, owner, environment, dependency, or receipt drift after one or more valid leaves were published
- **THEN** the parent SHALL remain unpublished
- **AND** the exact-current leaves SHALL remain available for a later parent only after independent verification

#### Scenario: Parallel cleanup residual survives a later freshness failure
- **WHEN** a parallel batch has one or more children whose descendant cleanup is unconfirmed and the final source or receipt freshness check fails
- **THEN** the orchestrator SHALL preserve every corresponding residual owner lease before running the failure-prone freshness check
- **AND** it SHALL release leases for children whose cleanup is confirmed
- **AND** it SHALL publish no leaf or parent receipt from the failed batch

## ADDED Requirements

### Requirement: Exact reverse-surface map inputs use one stable semantic identity
Model regression and validation-owner input resolution SHALL admit `.flowguard/structure/reverse-surfaces/implementation-surface-map.json` only when a model contract declares that exact normalized literal path. Before using it, the resolver SHALL validate the current map schema and verify `authoring_fingerprint` against the complete map payload excluding that field. The model-input identity SHALL retain authored surface, owner, intent, disposition, model-obligation, test, proof, and complete component-membership content, while excluding `authoring_fingerprint`, `authoring_status`, `current_revision`, `discovery_fingerprint`, `owner_receipt_identities`, `current_authority_join`, and `current_behavior_ledger_join`. It SHALL also exclude generated owner receipt IDs/fingerprints and actual canonical relative-path `#receipt:validation-owner:<route>:<32hex>` receipt references while retaining non-owner test/proof references. Model inventory, owner freshness, and affected-path impact planning SHALL use the same identity. Broad `.flowguard/**` and reverse-surface directory selectors SHALL continue to exclude this generated map, and the map SHALL NOT enter a shared group.

#### Scenario: Exact map input is explicitly declared in an independently scoped map operation
- **WHEN** a map operation explicitly declares the exact normalized map path for one or more model contracts
- **THEN** all selected model snapshots and owner observations SHALL contain the same semantic fingerprint for that path
- **AND** no other model SHALL acquire the path through a shared input group

#### Scenario: Bounded efficiency patch declares no reverse-map input
- **WHEN** this bounded efficiency patch has no selected contract that declares the exact canonical map path
- **THEN** map admission SHALL return no errors and no map proof without discovery, map I/O, or owner execution
- **AND** this patch SHALL retain conditional exact-map failure gates and the final complete reverse audit unchanged
- **AND** this result SHALL NOT claim whole-repository reverse-surface completeness or substitute an old map/receipt

#### Scenario: Broad reverse-surface selectors remain excluded
- **WHEN** a model declares `.flowguard/**/*` or a reverse-surface directory glob without the exact map literal
- **THEN** the generated map and discovery/evidence outputs SHALL remain excluded
- **AND** a mixed selector SHALL admit only the separately declared exact map path

#### Scenario: Authored semantics change while generated currentness changes
- **WHEN** a surface, owner, intent, disposition, model obligation, test/proof reference, or component member changes and the authoring fingerprint is recomputed
- **THEN** the model-input identity SHALL change

#### Scenario: Generated currentness changes without authored semantic changes
- **WHEN** only the declared derived currentness fields or generated owner-receipt identities change and the authoring fingerprint is recomputed
- **THEN** the model-input identity SHALL remain stable

#### Scenario: Map schema or authoring fingerprint is stale
- **WHEN** the exact map path is requested but its schema is not current or its full-payload authoring fingerprint does not match
- **THEN** input resolution SHALL return a typed failure before any owner starts
- **AND** it SHALL NOT fall back to raw map bytes or a broad selector

#### Scenario: Merged discovery omits a current implementation surface
- **WHEN** a merged discovery is presented for current map-owner admission
- **THEN** the source-only plan SHALL be rebuilt using the persisted shard row bound, every planned shard SHALL be rediscovered, and the complete merge SHALL be compared with the stored observation
- **AND** a missing surface SHALL remain blocked even when the stored surface count and discovery fingerprint are recomputed
- **AND** source bytes, planned source identities, shard ids, and the merged call graph SHALL remain bound to the same complete current source boundary


### Requirement: Continuation preserves one current producer per component
Continuation SHALL declare exact component input edges, one execution owner, immutable terminal receipts and separate policy/source identities. Only changed affected components SHALL rerun; unknown edges block. Pure stage decisions share one observation; owner pre/post/CAS/publication retain actual freshness. Failed outputs remain immutable and no same-episode retry hides effects.

#### Scenario: Failed sibling is rejected by model-parent consumer
- **WHEN** only required connection changes and its single execution fails while siblings are exact-current
- **THEN** siblings execute zero, failed receipts and noncurrent success parent are not reused, outer consumer refuses, no repair native producer starts, authority writes zero and descendant cleanup is confirmed
