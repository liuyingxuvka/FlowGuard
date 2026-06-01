## ADDED Requirements

### Requirement: Kernel references use compact handoff stubs for satellite-owned protocols
The FlowGuard Skill Kernel SHALL avoid carrying full duplicate copies of
satellite-owned reference protocols.

#### Scenario: Duplicate protocol copy is detected
- **WHEN** a kernel reference file is byte-for-byte identical to a satellite
  reference file
- **THEN** skill documentation tests fail or require the kernel copy to become
  a compact handoff stub

#### Scenario: Handoff stub remains useful
- **WHEN** an agent opens a kernel-side handoff stub
- **THEN** it states that the satellite owns the detailed protocol
- **AND** it names the satellite skill and detailed reference file to load next
