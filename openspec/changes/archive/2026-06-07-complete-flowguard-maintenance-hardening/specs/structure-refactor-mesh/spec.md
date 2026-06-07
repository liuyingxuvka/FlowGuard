## ADDED Requirements

### Requirement: Behavior-preserving module responsibility split
FlowGuard large-module reduction SHALL split coherent responsibilities behind stable public entry points and verify old public imports still work.

#### Scenario: Source-audit responsibility is split
- **WHEN** source-audit helpers are moved from an oversized module into a dedicated module
- **THEN** the original public import path, public API export, and existing tests continue to pass

#### Scenario: Future large-module split is planned
- **WHEN** another oversized module is selected for split
- **THEN** StructureMesh evidence identifies the responsibility boundary, facade compatibility, cycle risk, and validation required before release

