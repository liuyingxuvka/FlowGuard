## ADDED Requirements

### Requirement: Portable blueprint references are stable and independently verifiable
A software-blueprint projection SHALL reference current portable model identities and verified implementation-binding identities without serializing arbitrary source callables or inferring semantics from source paths. Re-exporting unchanged current inputs SHALL produce the same canonical identity.

#### Scenario: Implementation reference changes without portable semantics changing
- **WHEN** a consumed implementation binding fingerprint changes after export
- **THEN** the blueprint projection becomes stale while the portable model identity remains independently unchanged

#### Scenario: Projection omits source text
- **WHEN** a blueprint is exported without an explicit source-archive requirement
- **THEN** the projection contains semantic and fingerprint references but no embedded production source text
