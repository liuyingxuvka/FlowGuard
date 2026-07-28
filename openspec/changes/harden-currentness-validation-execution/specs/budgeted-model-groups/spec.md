## ADDED Requirements

### Requirement: Budgeted graph fingerprints include executable semantics
A reusable budgeted graph fingerprint SHALL bind the canonical implementation
identity of every configured callable, including inspectable code, defaults,
closure values, relevant module file content, explicit configuration, and
declared helper inputs. Module and qualified name alone MUST NOT authorize
reuse.

#### Scenario: Same qualified name has a different body
- **WHEN** two callables have the same module and qualified name but different
  executable bodies
- **THEN** their budgeted graph fingerprints differ and prior ledger evidence
  is not reused

#### Scenario: Helper or default changes
- **WHEN** a consumed helper implementation, default value, closure value, or
  declared configuration changes
- **THEN** the graph fingerprint changes for the exact consuming model group

#### Scenario: Uninspectable callable has no explicit identity
- **WHEN** a configured callable cannot be inspected and the caller supplies no
  explicit implementation fingerprint
- **THEN** graph construction blocks instead of falling back to its name

#### Scenario: Executable semantics are unchanged
- **WHEN** code, defaults, closures, module inputs, helpers, and configuration
  all retain exact canonical identity
- **THEN** the same graph fingerprint remains eligible for exact ledger reuse
