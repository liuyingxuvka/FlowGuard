## ADDED Requirements

### Requirement: Preflight discovers executable composition context
Full existing-model preflight SHALL report current component fingerprints, existing system-definition references, candidate typed relations, business identities, shared-resource readers/writers, transaction/atomicity observations, queue/cache/external-confirmation owners, affected system properties, candidate changed roots, discovery-evidence identity, and unresolved dependency disposition when cross-model composition is relevant. Candidate relations SHALL remain proposed preflight findings until accepted into the strict portable-system definition by its owner; preflight SHALL NOT duplicate that definition's authoritative schema.

#### Scenario: Existing models should be composed
- **WHEN** a change affects two or more current models connected by an event, shared resource, retry, cache, external confirmation, or system property
- **THEN** preflight emits a `compose_existing_models` handoff with exact current owners, proposed relations, and unresolved items and does not create a duplicate system-model owner

#### Scenario: Dependency discovery is incomplete
- **WHEN** a required binding, identity, resource owner, or freshness fact is missing or ambiguous
- **THEN** preflight blocks executable-composition confidence or widens the candidate slice rather than assuming no impact
