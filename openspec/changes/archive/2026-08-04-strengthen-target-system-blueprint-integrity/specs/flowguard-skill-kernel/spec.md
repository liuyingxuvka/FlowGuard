## ADDED Requirements

### Requirement: The kernel exposes one canonical blueprint model
The FlowGuard kernel SHALL coordinate target-system blueprint work through the existing implementation inventory, model, structure, test, resource, intent, topology, and process owners. It SHALL use that one owner graph with direct typed gaps and SHALL NOT add a DNA mode, duplicate authority head, compatibility reader, or generic fallback owner.

#### Scenario: Whole blueprint task is explicit
- **WHEN** task facts explicitly request whole-target blueprint qualification
- **THEN** the kernel SHALL coordinate the existing native owners and return their exact layer results
- **AND** it SHALL NOT create a parallel blueprint format

### Requirement: Target product roles remain inside target models
The kernel MAY model actors, permissions, and roles declared by a target software or workflow, but SHALL NOT promote those target-specific roles into FlowGuard-global role catalogs or blueprint admission requirements.

#### Scenario: Approval workflow declares an administrator
- **WHEN** a target workflow contains administrator and requester roles
- **THEN** those roles SHALL remain members of that workflow model
- **AND** unrelated targets SHALL NOT inherit them
