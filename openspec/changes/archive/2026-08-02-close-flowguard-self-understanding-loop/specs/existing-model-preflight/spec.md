## ADDED Requirements

### Requirement: Preflight emits provenance-bound observations without claiming sufficiency
Existing-model preflight SHALL identify task-relevant current-model observations, unknown surfaces, unmapped surfaces, ownership conflicts, and not-triggered routes with provenance. It SHALL NOT claim that the task is sufficiently understood.

#### Scenario: Existing model is found but task coverage has not run
- **WHEN** preflight identifies a current model and its owner
- **THEN** it reports the observation and leaves understanding sufficiency not-run

#### Scenario: Greenfield work has no existing model
- **WHEN** no existing modeled system is in scope
- **THEN** preflight reports a typed not-triggered result rather than a successful existing-model claim

### Requirement: Preflight has one lossless task-coverage projection
The current preflight input and native report SHALL project model, surface, ownership, unknown, scoped, and blocking findings into task facts and one existing-model owner resolution without AI-authored field copying. A satisfied resolution SHALL require one current native proof artifact covering the exact projection obligations.

#### Scenario: AI omits one preflight surface while copying fields
- **WHEN** the standard projection contains a current covered or missing surface that a hand-written subset omits
- **THEN** the standard projection remains authoritative and the smaller hand-written subset cannot support sufficiency
