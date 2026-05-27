## MODIFIED Requirements

### Requirement: StructureMesh requires model-derived target split structure
FlowGuard SHALL require StructureMesh reviews for existing large-script or
large-module decomposition to include target child structure evidence derived
from a FlowGuard functional model before parent refactor confidence is claimed.

#### Scenario: Existing large script split has target structure evidence
- **WHEN** a StructureMesh plan reviews an existing large script split
- **THEN** the plan includes source model evidence, target child modules,
  FunctionBlock mapping, state-owner mapping, side-effect-owner mapping, facade
  plan, validation plan, and rationale

#### Scenario: Existing split lacks model-derived target structure
- **WHEN** a StructureMesh plan reviews an existing large script split without
  model-derived target structure evidence
- **THEN** StructureMesh reports a blocker and does not return a green continue
  decision

### Requirement: StructureMesh keeps its existing-code scope
StructureMesh SHALL remain scoped to existing large scripts, modules, packages,
commands, or API surfaces being decomposed, and SHALL NOT become the direct
entry point for no-code architecture planning.

#### Scenario: No-code architecture request
- **WHEN** a user asks for a structure recommendation before any code exists
- **THEN** the code structure recommendation route handles the request instead
  of StructureMesh

#### Scenario: Existing module decomposition
- **WHEN** an existing large module is being split
- **THEN** StructureMesh reviews the model-derived target split together with
  ownership, facade, dependency, config, and parity evidence

### Requirement: Target split derivation supports StructureMesh ownership review
Model-derived target split evidence SHALL be compatible with StructureMesh
partition ownership, module evidence, and public entrypoint evidence so the
target recommendation is reviewed rather than left as prose.

#### Scenario: Target recommendation enters the mesh
- **WHEN** a target structure recommendation exists for an existing split
- **THEN** StructureMesh consumes it as structured evidence and checks that its
  mappings align with partition owners and child modules

#### Scenario: Recommendation conflicts with ownership evidence
- **WHEN** the target recommendation assigns a state field or side effect to a
  different owner than the StructureMesh plan
- **THEN** StructureMesh reports a target ownership mismatch
