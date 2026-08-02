## ADDED Requirements

### Requirement: Bounded software blueprints account for reconstruction resources
A bounded software blueprint SHALL identify required build, runtime, dependency, configuration, schema, data, asset, migration, external-service, and verification resources with current fingerprints or explicit external/scoped dispositions. Environment-variable semantics may be declared, but secrets SHALL NOT be embedded.

#### Scenario: Required build input is absent
- **WHEN** a required build manifest or runtime dependency has no current blueprint reference or explicit external disposition
- **THEN** static blueprint closure is incomplete

#### Scenario: External service is intentionally outside the boundary
- **WHEN** an external service contract and substitute or availability expectation are explicitly declared outside the implementation boundary
- **THEN** the resource can be external without being silently omitted
