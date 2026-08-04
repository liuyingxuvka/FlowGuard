## ADDED Requirements

### Requirement: Project-neutral blueprint qualification preserves one model authority
The authoritative model system SHALL qualify a software blueprint from one exact current `observed_implementation` snapshot plus independently identified implementation, semantic, test, resource, oracle, and intent-lineage evidence. The qualification SHALL remain a derived view and SHALL NOT create another model-system head, relabel a target as current, or let a project-specific preset own generic blueprint semantics.

#### Scenario: Another Python project requests blueprint qualification
- **WHEN** a Python project supplies a bounded project definition, a current observed model-system snapshot, and supported discovery inputs
- **THEN** FlowGuard qualifies the project through the project-neutral blueprint path
- **AND** no FlowGuard-repository preset or FlowGuard-specific owner is required for the generic result

#### Scenario: A target contribution is present
- **WHEN** a future-intent contribution describes a candidate behavior that is not implemented by the current observed source
- **THEN** the contribution remains attached to a non-current candidate revision in the same logical model lineage
- **AND** the current observed head remains unchanged

#### Scenario: A project-specific preset attempts to become authority
- **WHEN** a project preset supplies inventory or binding defaults for the generic builder
- **THEN** the resulting blueprint continues to derive authority from the exact observed snapshot and native evidence owners
- **AND** the preset cannot create an alternate model head or evidence owner

### Requirement: Blueprint depth is licensed one independent layer at a time
Blueprint qualification SHALL report the status of implementation inventory, traceability, independent semantics, model-code-test binding, resource/oracle closure, static blueprint closure, and empirical reconstruction separately. It SHALL expose the deepest proven layer and the exact missing, stale, or blocked owner and evidence for every higher layer.

#### Scenario: Source scanning produced model and binding text
- **WHEN** the same production-source scan supplies an implementation surface, its claimed intended semantics, and its binding description without independent semantic evidence
- **THEN** inventory and traceability MAY pass
- **AND** independent-semantic and deeper blueprint layers remain incomplete

#### Scenario: One required evidence layer is stale
- **WHEN** model, semantic, code, test, resource, oracle, or intent-lineage evidence does not match the current consumed identity
- **THEN** the qualification reports the deepest lower layer that remains proven
- **AND** it names the stale layer, owner, subject, and fingerprint rather than collapsing the result into one broad boolean

#### Scenario: No discovery adapter supports a required source language
- **WHEN** the declared software boundary contains a behavior-bearing source for which no current discovery adapter is registered
- **THEN** static blueprint closure is blocked with the exact unsupported boundary member
- **AND** FlowGuard does not substitute a FlowGuard-specific fallback owner
