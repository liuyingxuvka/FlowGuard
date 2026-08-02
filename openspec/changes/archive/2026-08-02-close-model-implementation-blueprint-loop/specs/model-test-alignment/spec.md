## ADDED Requirements

### Requirement: Blueprint alignment is bidirectional over the independent source inventory
For a software-blueprint claim, Model-Test Alignment SHALL verify both that every required model obligation has one current primary implementation binding and that every behavior-bearing implementation surface has a model obligation, owner contract, or explicit non-behavior terminal disposition. Caller-declared CodeContracts SHALL NOT define the complete source denominator.

#### Scenario: Source entrypoint has no declared contract
- **WHEN** independent discovery finds a public or behavior-bearing entrypoint with no model or owner-contract binding
- **THEN** blueprint alignment is blocked as an unowned implementation surface

#### Scenario: Duplicate primary implementations claim one obligation
- **WHEN** two non-delegating implementation bindings claim primary ownership of the same obligation
- **THEN** blueprint alignment fails with duplicate ownership

### Requirement: Path and symbol binding is insufficient for reconstruction closure
A blueprint-required implementation binding SHALL cite current source-independent semantic specifications and applicable oracles for its input/output behavior, state and effects, error behavior, and relevant order, retry, timeout, or decision rules. A path and symbol without those references SHALL remain traceability-only evidence.

#### Scenario: Function path exists without semantic specification
- **WHEN** a model obligation binds a current function path and symbol but lacks required semantic or oracle references
- **THEN** ordinary traceability may pass while blueprint reconstruction closure remains incomplete

#### Scenario: Hidden writer is discovered
- **WHEN** source discovery finds a state or effect writer not present in the bound semantic write inventory
- **THEN** alignment blocks the blueprint and identifies the writer
