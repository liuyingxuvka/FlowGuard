## ADDED Requirements

### Requirement: Runtime gateway writes bind to runtime path nodes
Runtime Gateway Adoption SHALL allow gateway-mediated critical writes to bind
to runtime node ids so state mutation evidence can be traced to modeled
workflow path evidence.

#### Scenario: Gateway write names runtime node
- **WHEN** a critical write observation goes through a declared gateway
- **AND** the observation names a current runtime node id that is bound to the
  same state surface and code boundary
- **THEN** runtime gateway adoption SHALL accept the runtime node binding as
  supporting evidence

#### Scenario: Gateway write lacks required runtime node
- **WHEN** a gateway contract requires runtime path binding
- **AND** a critical write observation has no runtime node ids
- **THEN** runtime gateway adoption SHALL report missing runtime path evidence

#### Scenario: Runtime node writes unmanaged surface
- **WHEN** a runtime node observation records a state write to a critical
  surface not managed by the gateway named on the write observation
- **THEN** runtime gateway adoption SHALL block runtime-gateway confidence
