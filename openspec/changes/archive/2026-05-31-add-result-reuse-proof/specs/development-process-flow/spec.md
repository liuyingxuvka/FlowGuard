## ADDED Requirements

### Requirement: Development process planning accounts for reuse-ticket freshness
DevelopmentProcessFlow SHALL treat model and test reuse tickets as validation
evidence that can be invalidated by later writes.

#### Scenario: Later code write invalidates reused test result
- **WHEN** a development plan reuses a previous test result
- **AND** a later action changes a tested artifact, test source, dependency, or
  environment boundary named by the reuse ticket
- **THEN** the minimum revalidation plan SHALL require rerun or refreshed reuse
  proof before done confidence

#### Scenario: Unchanged evidence can remain scoped current
- **WHEN** the reuse ticket and proof artifact remain current after all later
  writes
- **THEN** DevelopmentProcessFlow MAY treat the reused result as current
  validation evidence within the ticket's declared scope
