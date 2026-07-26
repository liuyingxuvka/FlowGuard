## RENAMED Requirements

- FROM: `### Requirement: ExistingModelPreflight consumes provider context after plane lookup`
- TO: `### Requirement: ExistingModelPreflight consumes WorkContexts after plane lookup`

## MODIFIED Requirements

### Requirement: ExistingModelPreflight consumes WorkContexts after plane lookup
ExistingModelPreflight SHALL perform canonical Behavior Commitment Ledger
plane-first lookup before consuming an explicit collection of zero, one, or
many reviewed WorkContexts. It SHALL preserve every context's adapter, native
work, native owner, subject lane, artifact, behavior-source-surface, and
fingerprint identities separately from behavior ownership. WorkContext SHALL
remain read-only source and process context, and the selected primary behavior
plane SHALL be determined by the matching commitment rather than forced to
`development_process`.

#### Scenario: OpenSpec task mentions a product behavior
- **WHEN** an OpenSpec WorkContext artifact describes a product-runtime
  behavior and plane-first lookup selects its existing product commitment
- **THEN** preflight SHALL keep the product-runtime commitment and current
  primary model as behavior owner and preserve the WorkContext only as a typed
  source and process-context relation

#### Scenario: Provider context is stale or unmapped
- **WHEN** any required WorkContext lacks a current fingerprint, registered
  adapter, bounded root, native owner, required artifact role, or typed BCL
  source mapping for a claimed behavior
- **THEN** preflight SHALL report the exact scoped context gap and SHALL NOT use
  the artifact or provider status as complete model evidence

#### Scenario: Several current contexts inform one task
- **WHEN** OpenSpec, declared planning files, and release material are all
  configured for the same preflight
- **THEN** preflight SHALL preserve every distinct context and artifact
  identity, reconcile their typed commitment targets, and SHALL NOT select the
  first adapter as an implicit primary source

#### Scenario: A context targets another behavior plane
- **WHEN** a development planning artifact targets an existing
  `agent_operation` or `product_runtime` commitment
- **THEN** preflight SHALL allow that commitment's plane to remain primary and
  SHALL connect the WorkContext only through a typed source or target relation

#### Scenario: A WorkContext is declared as a runtime surface
- **WHEN** a caller attempts to classify WorkContext itself as a UI, API, CLI,
  alias, adapter, wrapper, helper, or compatibility behavior surface
- **THEN** preflight SHALL reject the ownership merge because WorkContext is
  external planning context rather than a same-intent runtime entrypoint

#### Scenario: A target context is presented as current implementation
- **WHEN** a `normative_target` or `counterfactual_experiment` WorkContext is
  presented as observed current-model authority
- **THEN** preflight SHALL keep the lanes separate and SHALL require the
  existing ModelRevisionSet activation path before observed ownership changes

#### Scenario: Normative contexts conflict
- **WHEN** two current normative WorkContexts map incompatible semantics to the
  same commitment or business intent
- **THEN** preflight SHALL report the BCL conflict and SHALL NOT resolve it by
  adapter order, provider preference, or fallback
