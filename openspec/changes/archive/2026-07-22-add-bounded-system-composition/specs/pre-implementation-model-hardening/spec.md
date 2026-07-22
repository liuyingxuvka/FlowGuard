## ADDED Requirements

### Requirement: Anchored topology hazards can seed executable interactions
Topology-grounded hardening SHALL convert event edges, retry-identity mismatches, shared-writer/resource links, commit/emit/ack atomicity gaps, stale-cache authority gaps, late external confirmation, queue reorder/drop/duplicate boundaries, and unowned global properties into bounded interaction scenario seeds with exact anchors. It SHALL reference a current owner already resolved by BCL/preflight or emit `owner_missing`; topology reasoning SHALL NOT appoint a new authoritative property owner.

#### Scenario: Shared-writer hazard is anchored
- **WHEN** two model transitions write through the same resource owner
- **THEN** hardening emits both relevant ordering seeds and references the resolved system-property owner, or emits `owner_missing`, without claiming either schedule was executed

#### Scenario: Concern lacks a topology anchor
- **WHEN** an AI concern cannot name a model, transition, binding, resource, or property anchor
- **THEN** it remains observation-only and cannot create an executable-composition blocker
