## MODIFIED Requirements

### Requirement: FlowGuard self-qualification uses the public project-neutral path
FlowGuard self-maintenance SHALL build and qualify its self-blueprint through the same target-system compiler, provider registry and snapshot, project-neutral builder, Python observation providers, test inventory, alignment, and qualification contracts available to other targets. The FlowGuard self definition SHALL be a thin bounded software preset and SHALL NOT duplicate generic assembly, semantic, provider, or evidence authority.

#### Scenario: Generic compiler behavior changes
- **WHEN** the target-system compiler, project-neutral builder, or a consumed schema changes
- **THEN** FlowGuard self-qualification exercises that exact current implementation and schema
- **AND** a FlowGuard-only alternate builder cannot keep the self check green

#### Scenario: FlowGuard-specific preset supplies repository boundaries
- **WHEN** self-maintenance loads FlowGuard's checked-in blueprint definition
- **THEN** the preset supplies only target-specific boundaries, provider selections, owner mappings, and declared resources
- **AND** generic qualification remains owned by the public provider-neutral path

#### Scenario: A non-code fixture follows the same core path
- **WHEN** regression supplies a bounded workflow or mixed target with equivalent current provider capabilities
- **THEN** both targets are compiled through the same target-system API and checker contracts
- **AND** target identity and provider kinds change only the declared target data
