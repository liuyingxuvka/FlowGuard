# public-model-miss-template Specification

## Purpose
This capability defines FlowGuard's Public Model Miss Template behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Template encodes observed and generalized bad cases
The public `model-miss-template` SHALL generate a model-miss review artifact
that records the observed issue and at least one same-class generalized bad
case before the review can be marked complete.

#### Scenario: Template user captures a model miss
- **WHEN** a user fills in the generated model-miss review for an observed bug
- **THEN** completion requires both the observed issue and a same-class
  generalized bad case

#### Scenario: Same-class generalization is missing
- **WHEN** the generated review records only the observed issue
- **THEN** the generated checks fail the review as a point-fix-only repair

### Requirement: Template checks reject point-fix-only modeling
The public `model-miss-template` SHALL include a broken point-fix-only scenario
or mutation that demonstrates the checks fail when the model accepts the known
bug as the whole target and omits same-class generalization.

#### Scenario: Broken point fix is exercised
- **WHEN** the generated template checks run their negative scenario
- **THEN** the scenario fails unless the model distinguishes the observed bug
  from the broader bad-case class

### Requirement: Generated notes separate target from holdout
The public `model-miss-template` SHALL generate notes that explain the known bug
is validation or holdout evidence, not the sole model target.

#### Scenario: Notes describe the known bug role
- **WHEN** the template writes its model-miss notes
- **THEN** the notes identify the observed issue, the same-class generalized
  bad case, and the known bug's validation or holdout role

### Requirement: Release sync covers public template distribution
The implementation SHALL update version metadata and changelog entries, then
sync and verify the installed local Skill and configured shadow workspace
before release completion is claimed.

#### Scenario: Release readiness is checked
- **WHEN** the public template hardening is prepared for release
- **THEN** version metadata, changelog, installed Skill content, and shadow
  workspace imports all reflect the same implementation
