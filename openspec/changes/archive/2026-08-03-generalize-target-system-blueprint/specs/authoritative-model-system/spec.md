## ADDED Requirements

### Requirement: Observed authority binds target-system provider lineage
The sole observed model-system authority SHALL bind the exact target-system descriptor, provider-result identities, canonical intent inventory, behavior semantics, portable bindings, resource inventory, test inventory, and blueprint-readiness identity consumed by a broad DNA claim.

#### Scenario: Provider result changes after blueprint compilation
- **WHEN** a consumed provider input or result fingerprint changes after a blueprint was compiled
- **THEN** the affected blueprint layers and broad DNA claim SHALL become stale
- **AND** the observed model head SHALL remain truthful for its separately declared model boundary

### Requirement: Target kinds do not create alternate model heads
Composing software, workflow, service, agent, data-pipeline, or mixed target providers SHALL remain a derived projection of the current observed and target authorities. Target kind and provider selection SHALL NOT create a second observed model-system head.

#### Scenario: Workflow authority joins software observations
- **WHEN** a mixed target combines an observed software snapshot with an independently governed workflow contract
- **THEN** the blueprint SHALL preserve both authority identities and claim boundaries
- **AND** neither provider SHALL silently replace the observed model-system head
