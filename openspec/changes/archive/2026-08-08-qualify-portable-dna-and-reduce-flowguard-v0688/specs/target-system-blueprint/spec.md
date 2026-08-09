## ADDED Requirements

### Requirement: Canonical target export preserves a portable target-neutral bundle
The canonical target export SHALL preserve all declared target-neutral blueprint layers, exact provider identities, model hierarchy, interfaces, resources, intent, implementation bindings, test/oracle bindings, and readiness statuses in a content-addressed portable bundle.

#### Scenario: Software target is exported
- **WHEN** a software target has current implementation, model, resource, intent, and test artifacts
- **THEN** the export SHALL preserve them without requiring a particular source language or repository layout

#### Scenario: Non-code workflow is exported
- **WHEN** a non-code workflow supplies participants, inputs, states, transitions, outputs, resources, intent, and verification
- **THEN** the export SHALL preserve those real workflow layers without fabricating Python modules, classes, or pytest members

### Requirement: Providers remain adapters rather than blueprint authorities
Provider adapters SHALL report target observations and qualified artifacts; they SHALL NOT inject a ready status, select a fallback provider, or create a second blueprint authority.

#### Scenario: Required provider is missing
- **WHEN** the declared target profile requires an adapter that is absent or stale
- **THEN** the target result SHALL be visibly blocked or incomplete and SHALL identify the provider gap
- **AND** the compiler SHALL NOT silently substitute a Python or synthetic provider
