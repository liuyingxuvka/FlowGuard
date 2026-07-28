## ADDED Requirements

### Requirement: Similarity compares materialized exact-intent identities
Model Similarity Consolidation SHALL compare stable commitment ids,
`business_intent_id` values, business path ids, expected terminals, material
state writes, side effects, public surface ids, and evidence freshness when it
classifies same-workflow, duplicate, adapter, shared-kernel, and false-friend
relations for an affected intent family.

#### Scenario: Same exact intent exposes a reuse candidate
- **WHEN** two materialized signatures share the same exact business-intent identity and expected terminal and overlap in material state writes or side effects
- **THEN** Model Similarity Consolidation SHALL recommend reuse or extension of the existing boundary and SHALL identify the existing commitment and primary-path candidate for downstream review

#### Scenario: Similar labels hide different external semantics
- **WHEN** two signatures have similar labels but differ in preconditions, expected terminal, failure boundary, material state writes, side effects, safety boundary, or another externally observable contract
- **THEN** Model Similarity Consolidation SHALL classify the difference as a false friend or intentional variant and SHALL NOT recommend same-intent consolidation

#### Scenario: Signature lacks stable identity evidence
- **WHEN** a signature has only a free-text intent label or path name without the materialized commitment, business-intent, terminal, surface, and current-evidence fields required by the claimed relation
- **THEN** Model Similarity Consolidation SHALL scope the relation and SHALL NOT present it as a complete exact-intent comparison

### Requirement: Similarity handoffs materialize downstream obligations
Model Similarity Consolidation SHALL preserve the affected surface ids, matched and different
semantic elements, commitment and path identities, required evidence,
downstream owner, and unresolved inventory gaps in each handoff for same-intent
reuse, duplicate review, or a separate boundary. An opaque relation or handoff
id alone SHALL NOT satisfy Existing Model Preflight, BCL, PPA, UI, or broad
confidence requirements.

#### Scenario: Reuse handoff carries concrete obligations
- **WHEN** a similarity relation recommends reuse of an existing exact business intent
- **THEN** the handoff SHALL name the affected surfaces, existing commitment, primary-path candidate, matched terminal and effects, missing evidence, and the existing downstream owners that must decide and validate reuse

#### Scenario: Inventory completeness is not established
- **WHEN** the supplied signatures do not account for every affected-family surface declared by Existing Model Preflight
- **THEN** Model Similarity Consolidation SHALL expose the omitted-member gap and SHALL NOT claim complete same-intent coverage

#### Scenario: Similarity does not select runtime authority
- **WHEN** a relation identifies an existing path as a strong reuse candidate
- **THEN** Model Similarity Consolidation SHALL hand the candidate to the existing BCL/PPA owners and SHALL NOT create, merge, or select a runtime authority itself
