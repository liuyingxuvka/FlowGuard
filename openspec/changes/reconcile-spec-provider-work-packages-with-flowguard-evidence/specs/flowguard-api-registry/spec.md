## ADDED Requirements

### Requirement: Spec work-package APIs have one public owner
FlowGuard SHALL export provider work-package, reconciliation, snapshot, receipt, reuse, and cached-check review surfaces through one canonical module and CLI owner.

#### Scenario: Public API is imported
- **WHEN** callers import the spec work-package API or invoke its CLI
- **THEN** the same canonical data model and language-neutral JSON schema SHALL be used without duplicate wrappers or alternate success paths

#### Scenario: Provider adapter is unavailable
- **WHEN** a requested provider marker or supported schema is absent
- **THEN** the API SHALL return an explicit unavailable/unsupported result rather than fabricate a package
