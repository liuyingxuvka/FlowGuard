## ADDED Requirements

### Requirement: Pre-code test design and executed evidence are distinct
Model-test alignment SHALL distinguish planned obligations, oracle definitions, and known-bad cases prepared before implementation from test executions produced after implementation. Not-run planned evidence SHALL NOT be reported as executed or passing evidence.

#### Scenario: Oracle exists before implementation
- **WHEN** an obligation and oracle are defined but the implementation test has not run
- **THEN** alignment reports pre-code-ready and executed-evidence not-run

#### Scenario: Executed evidence targets another model identity
- **WHEN** a test passes against a model identity different from the current maturation identity
- **THEN** the evidence is stale for the current alignment claim

### Requirement: Structure recommendations bind to current model authority
Any model-derived code-structure recommendation used for implementation SHALL reference the exact current maturation and implementation-admission identities.

#### Scenario: Recommendation predates maturation revision
- **WHEN** the model or maturation identity changes after the structure recommendation
- **THEN** the recommendation is stale until re-derived or explicitly revalidated
