## ADDED Requirements

### Requirement: Native result bindings are exact
Model regression evidence SHALL bind each source case to one exact native result or an explicitly declared aggregate with its complete child set, oracle dimensions, raw artifact fingerprint, owner, and input identity.

#### Scenario: Marker has no native result
- **WHEN** a runner prints a success marker but does not emit a verifiable result object and raw artifact
- **THEN** the case is blocked or not_run and cannot satisfy its parent

#### Scenario: Same inputs are current
- **WHEN** the exact case, oracle, code, model, toolchain, and environment fingerprints match a terminal receipt
- **THEN** the receipt may be reused without launching a producer
