## REMOVED Requirements

### Requirement: Static blueprint and empirical reconstruction are separate claims
**Reason**: The empirical product claim and receipt branch has been retired. The authoritative model system licenses blueprint depth through the canonical ordered readiness layers only.

**Migration**: Consume the static-blueprint status, deepest proven layer, and exact gap set; external experiments have no model-authority status.

### Requirement: Published observed authority is reconstructable from the release tree
**Reason**: The requirement remains necessary, but its former title reused a retired product term for ordinary Git reachability and current snapshot derivation.

**Migration**: Use the release-tree reproducibility requirement; it preserves the same committed-input gate without naming a separate product path.

## MODIFIED Requirements

### Requirement: Observed authority remains revision truthful
An observed snapshot SHALL be current only while a fresh live re-observation and derivation from the model regression manifest and current source inventory exactly matches the observed head's subject revision, model-instance identities, resolved input inventories, required source-surface identities and fingerprints, referenced owner-artifact identities, coverage-universe fingerprint, and required evidence. Pointer-to-snapshot self-consistency SHALL be necessary but SHALL NOT be sufficient for a current authority result.

#### Scenario: Live inventory exactly matches the observed snapshot
- **WHEN** authority audit re-derives the current source and model inventory
- **AND** every required live identity and fingerprint exactly equals the corresponding observed-snapshot identity and fingerprint
- **THEN** the observed head may remain current subject to its native evidence gates
- **AND** the audit records the re-derived live-inventory fingerprint used for reconciliation

#### Scenario: Software changes without a matching observed snapshot
- **WHEN** source, deployment, configuration, a required source surface, an owner artifact, or another fingerprinted implementation input changes after the observed snapshot was validated
- **THEN** the system reports the observed authority as stale or blocked
- **AND** it does not relabel an existing target or experiment as observed

#### Scenario: Stored authority is internally consistent but live inventory differs
- **WHEN** the project pointer, stored snapshot fingerprint, stored subject revision, and stored coverage status agree with one another
- **AND** a fresh live re-observation has a different subject revision, model-instance set, source-surface set, owner-artifact fingerprint, resolved input inventory, or coverage fingerprint
- **THEN** authority audit reports `observed_source_inventory_stale`
- **AND** project audit, preflight, activation, release, and broad model coverage claims remain blocked until one accepted `ModelRevisionSet` updates the observed head

#### Scenario: A target is implemented
- **WHEN** implementation work realizes a validated normative target
- **THEN** the system builds and validates a new `observed_implementation` snapshot from the resulting live source inventory
- **AND** it links the new observed snapshot to the target through typed realization and supersession relations instead of changing the target's subject lane

### Requirement: Blueprint closure uses an independently discovered implementation universe
The authoritative model system SHALL consume fingerprinted implementation and resource inventories derived independently from declared models, code contracts, and tests before it licenses a whole-software blueprint claim. Every admitted inventory item SHALL have one explicit disposition, and unresolved files, parse failures, hidden state or effect writers, duplicate primary owners, and omitted required resources SHALL block static blueprint completion.

#### Scenario: Undeclared helper exists in production source
- **WHEN** independent discovery finds a behavior-bearing helper that is absent from the declared model and contract bindings
- **THEN** static blueprint closure is incomplete and identifies the helper

#### Scenario: Every admitted item has a current disposition
- **WHEN** the current inventory, bindings, resources, and owner fingerprints cover every item inside the declared boundary
- **THEN** the system may report static blueprint complete within that boundary

### Requirement: Blueprint depth is licensed one independent layer at a time
Blueprint qualification SHALL report the status of implementation inventory, traceability, independent semantics, model-code-test binding, resource/oracle closure, and static blueprint closure separately. It SHALL expose the deepest proven layer and the exact missing, stale, or blocked owner and evidence for every higher layer.

#### Scenario: Source scanning produced model and binding text
- **WHEN** the same production-source scan supplies an implementation surface, its claimed intended semantics, and its binding description without independent semantic evidence
- **THEN** inventory and traceability MAY pass
- **AND** independent-semantic and deeper blueprint layers remain incomplete

#### Scenario: One required evidence layer is stale
- **WHEN** model, semantic, code, test, resource, oracle, or intent-lineage evidence does not match the current consumed identity
- **THEN** the qualification reports the deepest lower layer that remains proven
- **AND** it names the stale layer, owner, subject, and fingerprint rather than collapsing the result into one broad boolean

#### Scenario: No discovery adapter supports a required source language
- **WHEN** the declared software boundary contains a behavior-bearing source for which no current discovery adapter is registered
- **THEN** static blueprint closure is blocked with the exact unsupported boundary member
- **AND** FlowGuard does not substitute a FlowGuard-specific fallback owner

### Requirement: Observed authority binds behavior-level blueprint evidence
The sole observed model-system authority SHALL reference the exact owner-level, behavior-block, resource, intent, test-binding, and canonical blueprint-readiness identities used for a self-qualification claim. A later layer SHALL NOT hide an earlier incomplete or stale layer.

#### Scenario: Current model snapshot points to an owner-level-only blueprint
- **WHEN** the observed snapshot is current but its behavior-block or readiness evidence is incomplete
- **THEN** observed model authority SHALL remain current for its declared model boundary
- **AND** the stronger software-DNA readiness claim SHALL remain incomplete

## ADDED Requirements

### Requirement: Published observed authority is reproducible from the release tree
The release verifier SHALL require every file in the selected snapshot's resolved model input inventory to be reachable from the exact committed source tree when a project publishes an observed model-system head. A local working-tree file, ignored file, untracked file, alternate checkout, or historical evidence artifact SHALL NOT satisfy release authority.

#### Scenario: Every authority input is committed
- **WHEN** release validation examines the selected observed snapshot
- **AND** the snapshot and every declared model input path resolve to the exact committed tree with matching content
- **THEN** the release may treat model-authority Git reachability as satisfied
- **AND** ordinary model currentness and evidence gates remain separately required

#### Scenario: Model input exists only in the local working tree
- **WHEN** the observed snapshot references a model file that exists locally but is ignored or untracked
- **THEN** release validation reports the exact missing path and blocks publication
- **AND** it does not drop that model from the live inventory or infer another authority

#### Scenario: Runner input exists only in the local working tree
- **WHEN** the observed snapshot references a runner input that is absent from the exact committed source tree
- **THEN** release validation reports the exact missing input and blocks publication
- **AND** local presence does not satisfy the published authority claim
