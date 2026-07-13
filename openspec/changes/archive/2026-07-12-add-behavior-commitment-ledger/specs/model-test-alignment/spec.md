## ADDED Requirements

### Requirement: Model-test alignment maps evidence to commitment ids
FlowGuard SHALL require behavioral test evidence to map to behavior commitment
ids when the claim is about user-visible or externally reliable behavior.

#### Scenario: Test maps to commitment
- **WHEN** a test proves behavior registered in the ledger
- **THEN** Model-Test Alignment SHALL record the commitment id alongside model and obligation ids

#### Scenario: Test lacks commitment mapping
- **WHEN** a broad behavior claim has tests only mapped to local model ids
- **THEN** Model-Test Alignment SHALL report that commitment coverage is incomplete
