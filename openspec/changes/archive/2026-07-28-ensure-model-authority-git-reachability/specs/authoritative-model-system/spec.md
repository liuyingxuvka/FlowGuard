## ADDED Requirements

### Requirement: Published observed authority is reconstructable from the release tree
The release verifier SHALL require every file in the selected snapshot's
resolved model input inventory to be reachable from the exact committed source
tree when a project publishes an observed model-system head. A local
working-tree file, ignored file, untracked file, alternate checkout, or
historical evidence artifact SHALL NOT satisfy release authority.

#### Scenario: Every authority input is committed
- **WHEN** release validation examines the selected observed snapshot
- **AND** the snapshot and every declared model input path resolve to the exact committed tree with matching content
- **THEN** the release may treat model-authority Git reachability as satisfied
- **AND** ordinary model currentness and evidence gates remain separately required

#### Scenario: Model input exists only in the local working tree
- **WHEN** the observed snapshot references a model file that exists locally but is ignored or untracked
- **THEN** release validation reports the exact missing path and blocks publication
- **AND** it does not drop that model from the live inventory or infer another authority

#### Scenario: Runner input exists only in the local working tree
- **WHEN** the model file is tracked but its snapshot-declared runner or another resolved input is ignored or untracked
- **THEN** the same authority-input reachability gate blocks publication
- **AND** a locally passing runner execution does not substitute for committed reachability
