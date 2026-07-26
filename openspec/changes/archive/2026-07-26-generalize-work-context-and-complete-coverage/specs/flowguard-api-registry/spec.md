## ADDED Requirements

### Requirement: WorkContext is the sole public planning-context API cohort
FlowGuard SHALL expose provider-neutral, project-bounded, content-addressed,
read-only planning context through one `flowguard.work_context` owner, one
`WORK_CONTEXT_API` registry cohort, one `API_SURFACE["work_context"]` entry,
one `work-context` CLI command, and one `work-context-template` template
command backed by `work_context_template_files`. The API, CLI, and templates
SHALL use the same canonical WorkContext artifact roles, provider identity,
adapter identity, content fingerprints, currentness rules, and
language-neutral JSON schema.

#### Scenario: Public WorkContext cohort is inspected
- **WHEN** a caller inspects `flowguard.__all__`, `WORK_CONTEXT_API`,
  `API_SURFACE`, route discovery, CLI parsers, and public template commands
- **THEN** every supported WorkContext public symbol is present in the exact
  declared cohort
- **AND** all of those surfaces delegate to the same canonical WorkContext
  model and review owner

#### Scenario: Declared provider adapter is unavailable
- **WHEN** a WorkContext request names an unregistered adapter, a missing
  declared root, or unsupported provider artifacts
- **THEN** the sole WorkContext API returns an explicit
  unavailable/unsupported result
- **AND** it does not select an OpenSpec-specific reader, declared-file
  fallback, compatibility alias, or alternate success path

#### Scenario: WorkContext templates are generated
- **WHEN** a caller invokes the public WorkContext template command
- **THEN** the generated model, runner, and notes use only current
  `work_context` names, fields, API helpers, and CLI commands
- **AND** no generated path or content refers to `spec_context`,
  `SpecContext`, or a spec work-package execution bridge

### Requirement: SpecContext surfaces are removed by direct replacement
The WorkContext introduction SHALL directly remove the
`flowguard.spec_context` module, `SPEC_CONTEXT_API`,
`API_SURFACE["spec_context"]`, `SpecContext` types and readers, the
`spec-context` CLI, the `spec-context-template` command,
`spec_context_template_files`, generated `.flowguard/spec_context` paths, and
SpecContext-specific documentation templates. No deprecated export, alias,
forwarder, compatibility reader, fallback parser, dual emission, or migration
runtime SHALL preserve those surfaces.

#### Scenario: Retired Python surface is imported
- **WHEN** a caller imports a retired SpecContext type, helper, module,
  registry group, or template helper
- **THEN** the retired name is absent rather than forwarding to WorkContext
- **AND** current API parity checks require the corresponding WorkContext
  surface where applicable

#### Scenario: Retired CLI or template command is invoked
- **WHEN** a caller invokes `spec-context`, `spec-context-template`, or a
  generated SpecContext runner
- **THEN** the retired command or path is unavailable
- **AND** FlowGuard does not silently reinterpret it as `work-context` or
  `work-context-template`

#### Scenario: Installed or generated surface is scanned
- **WHEN** source, templates, generated artifacts, public docs, and installed
  consumer projections are checked after replacement
- **THEN** the governed inventory contains zero current SpecContext public
  surfaces
- **AND** exactly one WorkContext API, CLI, and template owner remains

## REMOVED Requirements

### Requirement: Spec work-package APIs have one public owner
**Reason**: Provider work-package, reconciliation, snapshot, receipt, reuse,
and cached-check APIs create an execution bridge that is outside the
read-only WorkContext boundary and no longer has a current runtime owner.

**Migration**: Read planning artifacts through the sole WorkContext API and
registered read-only adapters. Keep provider lifecycle operations with the
provider and keep FlowGuard model, test, and process evidence with their native
FlowGuard owners.
