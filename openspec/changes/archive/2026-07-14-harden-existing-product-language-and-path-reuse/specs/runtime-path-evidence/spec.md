## ADDED Requirements

### Requirement: Runtime path evidence preserves stable behavior authority identity
FlowGuard SHALL carry the stable `business_intent_id`, `behavior_commitment_id`, and selected `primary_path_id` through required runtime node contracts, runtime observations, and runtime path runs whenever the evidence supports a path-sensitive external behavior claim.

#### Scenario: Runtime observation matches the selected authority
- **WHEN** a required runtime observation names the expected business intent, behavior commitment, and selected primary path
- **THEN** Runtime Path Evidence SHALL retain all three identities in the aligned path result
- **AND** downstream consumers SHALL be able to bind the observation to that exact behavior authority without interpreting free-text intent labels

#### Scenario: Same intent follows a different path
- **WHEN** a runtime observation names the expected `business_intent_id` but a `primary_path_id` different from the selected primary path
- **THEN** Runtime Path Evidence SHALL report a path-authority mismatch
- **AND** the observation SHALL NOT support a current passing path-sensitive claim

#### Scenario: Broad path evidence omits a stable identity
- **WHEN** a done, release, publish, production, archive, or full-confidence runtime path claim omits the stable intent, commitment, or selected primary-path identity
- **THEN** Runtime Path Evidence SHALL keep the missing identity as a blocking gap rather than inferring it from a label, node name, or route name

### Requirement: Runtime path evidence covers the complete declared same-intent surface set
FlowGuard SHALL let a runtime path alignment plan declare the complete expected set of same-intent entry surfaces and Primary Path Authority candidate ids, and SHALL compare that expected set with the materialized runtime contracts and observations before reporting broad confidence.

#### Scenario: Expected surface has no runtime contract
- **WHEN** an expected UI, API, CLI, alias, adapter, wrapper, helper, or facade surface has no runtime node contract or explicit scoped disposition
- **THEN** Runtime Path Evidence SHALL report the expected surface as missing
- **AND** the alignment SHALL NOT treat the caller-selected subset as a complete same-intent inventory

#### Scenario: Expected candidate has no observation or disposition
- **WHEN** a declared Primary Path Authority candidate id has neither current runtime observation evidence nor an explicit non-runtime disposition
- **THEN** Runtime Path Evidence SHALL report the candidate as unaccounted
- **AND** broad no-fallback confidence SHALL remain unavailable

#### Scenario: Complete surface inventory is aligned
- **WHEN** every expected same-intent surface and candidate is represented by a current runtime contract and observation or by an explicit scoped disposition
- **THEN** Runtime Path Evidence MAY report the inventory-completeness portion of alignment as passing
- **AND** it SHALL expose the covered and scoped surface and candidate ids

### Requirement: Retained facade runtime evidence proves delegation to the selected primary path
FlowGuard SHALL treat a retained public facade, alias, adapter, or wrapper as a delegating surface rather than a second runtime authority, and SHALL require current runtime evidence that the surface reaches the selected primary path without owning independent business behavior.

#### Scenario: Facade delegates to the selected primary path
- **WHEN** a retained facade is invoked for a stable business intent
- **AND** the runtime trace shows the facade entering the selected primary path and reaching the primary path terminal
- **THEN** Runtime Path Evidence SHALL record the facade as delegating to that primary path
- **AND** the facade observation MAY support the declared compatibility boundary

#### Scenario: Facade returns success without the selected primary path
- **WHEN** a retained facade or adapter returns business success without an observed delegation to the selected primary path
- **THEN** Runtime Path Evidence SHALL report an alternate-success or delegation mismatch
- **AND** the facade evidence SHALL NOT support primary-path authority confidence

#### Scenario: Facade delegation evidence is stale
- **WHEN** the facade, selected primary path, owner code contract, or runtime binding changes after the delegation observation was produced
- **THEN** Runtime Path Evidence SHALL mark the delegation proof stale
- **AND** current facade compatibility confidence SHALL require a new observation
