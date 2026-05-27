# model-miss-child-reattachment Specification

## Purpose
TBD - created by archiving change add-child-model-reattachment-gate. Update Purpose after archive.
## Requirements
### Requirement: Child model misses return through parent mesh
The model-first Skill SHALL require a post-runtime model miss repaired inside a
local child FlowGuard model to rerun the affected parent ModelMesh reattachment
gate before the miss can be closed.

#### Scenario: Child miss repair belongs to a parent mesh
- **WHEN** runtime, test, replay, log, or manual validation exposes a model miss
  and the repair changes a child model that belongs to a parent ModelMesh
- **THEN** the agent reruns the child checks and the affected parent ModelMesh
  reattachment gate before closing the miss

#### Scenario: Child-local green result without parent consumption
- **WHEN** a repaired child model is green but the parent ModelMesh does not
  consume the updated child evidence id
- **THEN** the model miss remains open or blocked rather than closed

### Requirement: Model-miss adoption records reattachment outcome
Post-runtime model-miss adoption evidence SHALL record whether a child repair
required parent reattachment and, when required, the parent mesh decision or the
reason it remains blocked.

#### Scenario: Reattachment passes
- **WHEN** a child model repair passes the affected parent ModelMesh
  reattachment gate
- **THEN** the adoption note records the parent mesh decision and consumed child
  evidence id

#### Scenario: Reattachment is blocked
- **WHEN** a child model repair cannot reconnect to the parent mesh because of
  interface drift, ownership drift, stale evidence, or missing parent
  consumption
- **THEN** the adoption note records the blocker instead of reporting the miss
  as closed
