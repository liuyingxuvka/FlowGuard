## ADDED Requirements

### Requirement: Post-green retry loops backpropagate into ModelMesh evidence
Post-runtime Model Miss Review SHALL treat stuck retry, repeated rejected
packet, same-input resend, missing repair feedback, and child-local-green but
parent-stuck failures after a previous FlowGuard pass as model misses that must
backpropagate into the existing ModelMesh and evidence chain.

#### Scenario: Same packet repeats after rejection
- **WHEN** runtime, test, replay, log, or user evidence shows a rejected packet
  being resent without changing the modeled input or repair target
- **AND** prior FlowGuard evidence was green or used for a confidence claim
- **THEN** Model-Miss Review SHALL classify the failure as a missed input branch,
  state coarse boundary, invariant weakness, or evidence overclaim
- **AND** the repair SHALL add or scope a same-class model/test obligation

#### Scenario: Rejection feedback did not name the repair
- **WHEN** a rejected handoff fails to tell the upstream model which field,
  body, owner, or repair command is required
- **THEN** the miss review SHALL backpropagate the gap into ModelMesh closure
  feedback tokens, transition coverage, owner code contract, and same-class
  evidence before broad closure

#### Scenario: Child green does not reattach to parent
- **WHEN** a child model or child test is green locally
- **AND** the parent remains stuck, stale, or unable to consume the child output
- **THEN** Model-Miss Review SHALL route closure through the existing parent
  child-reattachment, ModelMesh closure, Model-Test Alignment, and TestMesh
  evidence gates
