## ADDED Requirements

### Requirement: Current observed authority binds model path quality
Every new or materially changed model in current observed authority SHALL bind one current compact path-quality summary and detailed-evidence fingerprint from ModelMaturation. Observed authority SHALL remain faithful to current implementation behavior and SHALL NOT promote an unimplemented normative improvement.

#### Scenario: Changed model lacks a current summary
- **WHEN** a changed model has no current path-quality summary or has a stale or unresolved result for the claimed boundary
- **THEN** current authority activation fails for that affected model set
- **AND** no prior revision or parent result acts as fallback

#### Scenario: Whole-self qualification is explicitly requested
- **WHEN** FlowGuard explicitly qualifies its complete current self blueprint rather than an ordinary affected revision
- **THEN** the accepted authority SHALL bind one exact-current path-quality result for every current model owner under the same candidate snapshot
- **AND** changed-model-only coverage SHALL remain valid for ordinary revisions but SHALL NOT close the whole-self qualification claim

#### Scenario: Normative path is not observed
- **WHEN** a normative target proposes a different path that is not yet implemented and evidenced
- **THEN** current observed authority retains the implemented path and its current result
