## ADDED Requirements

### Requirement: Spec-check proof artifacts bind exact session identity
A proof artifact for a spec-check receipt SHALL bind the receipt id, begin/post snapshot ids, command/input/tool/environment fingerprints, covered obligations, terminal status, and result fingerprint.

#### Scenario: Receipt is reused
- **WHEN** a current passing spec-check receipt is reused
- **THEN** the proof artifact and reuse ticket SHALL both resolve to the exact immutable receipt and current session/input boundary

#### Scenario: Receipt path exists but identity is incomplete
- **WHEN** a result file exists without the complete proof and reuse bindings
- **THEN** it SHALL NOT support current evidence or archive readiness
