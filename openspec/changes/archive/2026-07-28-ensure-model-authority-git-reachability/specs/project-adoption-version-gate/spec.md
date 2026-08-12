## ADDED Requirements

### Requirement: Release validation closes clean-clone model-authority reachability
FlowGuard release validation SHALL compare the current observed snapshot's
complete resolved input closure with Git's tracked source inventory before
creating a release tag. The check SHALL report deterministic missing paths and
SHALL fail closed when Git inventory cannot be read.

#### Scenario: Local audit passes using ignored authority inputs
- **WHEN** project audit passes in a maintainer working tree
- **AND** one or more current snapshot inputs are absent from Git's tracked inventory
- **THEN** local-candidate release verification blocks before tagging
- **AND** a clean-clone project audit is required before corrective release confidence

#### Scenario: Annotated remote tag is queried through a command wrapper
- **WHEN** published verification resolves an annotated tag on a platform where caret characters can be interpreted by a command wrapper
- **THEN** the Git query avoids a caret-bearing command argument
- **AND** verification still requires the exact peeled tag row to equal the local release commit
