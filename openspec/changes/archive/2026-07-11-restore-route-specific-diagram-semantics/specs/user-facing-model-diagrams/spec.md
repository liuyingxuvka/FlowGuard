## ADDED Requirements

### Requirement: Route-Specific Diagram Semantics Survive Prompt Compaction
FlowGuard compact skill prompts SHALL preserve route-owned diagram meanings instead of flattening distinct models into a generic flowchart. The kernel MUST retain a cross-Guard diagram intent gate, and the DevelopmentProcessFlow, UI Flow Structure, Model-Test Alignment, Code Structure Recommendation, and ModelMesh prompts MUST identify the relationships represented by their diagram edges. Diagram guidance MUST remain explanatory and MUST NOT replace executable validation or LogicGuard argument semantics.

#### Scenario: Compact prompts retain their edge meanings
- **WHEN** FlowGuard skill-documentation regression tests inspect the canonical compact prompts
- **THEN** the kernel rejects generic cross-Guard flattening
- **AND** process edges represent order, invalidation, or revalidation; UI edges represent reachability or interaction transitions; alignment edges represent coverage; code-structure edges represent ownership/calls/adaptation/exposure/validation; and mesh edges represent delegation/reattachment/output consumption

#### Scenario: Prompt compaction removes route meaning
- **WHEN** a future prompt rewrite keeps generic diagram wording but removes a required route-owned edge meaning
- **THEN** FlowGuard's source skill regression MUST fail before installation or release confidence is claimed

#### Scenario: Installed suite is older than canonical prompts
- **WHEN** canonical route-specific diagram guidance differs from the global or downstream installed FlowGuard suite
- **THEN** active AI behavior MUST be reported as unsynchronized until whole-suite installation and content parity checks pass
