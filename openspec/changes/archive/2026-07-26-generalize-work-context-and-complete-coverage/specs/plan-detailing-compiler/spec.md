## RENAMED Requirements

- FROM: `### Requirement: PlanDetail preserves provider task identity and mappings`
- TO: `### Requirement: PlanDetail preserves WorkContext identities and mappings`

## MODIFIED Requirements

### Requirement: PlanDetail preserves WorkContext identities and mappings
PlanDetail SHALL preserve every referenced WorkContext's context, adapter,
native work, native owner, subject lane, context fingerprint, artifact,
artifact role, artifact fingerprint, and behavior-source-surface identities
when external work material is projected into plan sources, steps, and
validations. A plan MAY reference zero, one, or many contexts. It SHALL map
behavior targets through BCL commitments and map validation to native
FlowGuard owners or typed scoped-out reasons without copying provider
execution or lifecycle authority.

#### Scenario: Specification tasks become plan steps
- **WHEN** task, plan, requirement, acceptance, or other role-bearing
  WorkContext artifacts are compiled into PlanDetail rows
- **THEN** every in-scope row SHALL retain its context and artifact identities,
  role, fingerprints, typed commitment targets, and native validation owner
  through DevelopmentProcessFlow and TestMesh projection

#### Scenario: Task text alone is used as identity
- **WHEN** similar artifact or task wording from parallel contexts would
  collapse two native work items
- **THEN** PlanDetail SHALL reject the ambiguous projection rather than infer
  identity from text or provider order

#### Scenario: One step uses several contexts
- **WHEN** a plan step is constrained by an OpenSpec requirement, a declared
  design file, and an observed release-history context
- **THEN** the step SHALL preserve all three context/artifact references and
  their distinct subject lanes without creating a singular primary-provider
  field

#### Scenario: Provider status is supplied as validation
- **WHEN** a WorkContext status artifact or native checkbox is listed as proof
  that a PlanDetail validation passed
- **THEN** PlanDetail review SHALL reject it and SHALL require current evidence
  from the declared native FlowGuard validation owner

#### Scenario: A provider command is embedded in a plan source
- **WHEN** a WorkContext projection attempts to carry a provider write,
  execute, validate, resume, synchronize, complete, or archive command
- **THEN** PlanDetail SHALL reject the projection rather than turn the
  read-only source into an executable action

#### Scenario: A context lacks a behavior mapping
- **WHEN** a WorkContext artifact makes an in-scope external behavior promise
  but has neither a typed BCL source/commitment mapping nor a scoped-out reason
- **THEN** PlanDetail SHALL report an unmapped-source blocker before the plan
  can support execution

#### Scenario: A context changes after compilation
- **WHEN** a referenced context or artifact fingerprint changes after
  PlanDetail was compiled
- **THEN** the affected source, step, validation, DevelopmentProcessFlow
  projection, and downstream evidence SHALL become stale
