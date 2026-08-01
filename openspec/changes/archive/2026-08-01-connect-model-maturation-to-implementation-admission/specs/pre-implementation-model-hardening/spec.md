## ADDED Requirements

### Requirement: Modeling override is exact authorization, not a confidence waiver
The pre-implementation hardening gate SHALL represent an explicit request to proceed with open modeling gaps as bounded execution authorization over named actions, artifacts, gap fingerprints, and required validation, and SHALL NOT treat it as evidence that modeling is complete.

#### Scenario: Vague continue request cannot authorize unrelated work
- **WHEN** a request says to continue but does not accept named current gaps or define an exact implementation scope
- **THEN** the hardening gate MUST NOT convert it into broad implementation authorization

#### Scenario: Exact scoped authorization preserves gaps
- **WHEN** a request explicitly accepts named current gaps for one exact scope
- **THEN** the gate MAY authorize that scope while the open gaps and downgraded model confidence remain visible
