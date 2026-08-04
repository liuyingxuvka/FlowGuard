## ADDED Requirements

### Requirement: Blueprint-driven reduction candidates are independently complete
ArchitectureReduction SHALL derive each contraction candidate from the current observed blueprint, independent implementation inventory, exact same-intent surface inventory, and current model-semantic-code-test evidence. Each candidate SHALL name the retained owner, proposed removed or delegated surfaces, observable contract, state and side effects, callers and consumers, proof status, and required affected revalidation.

#### Scenario: Duplicate-looking helpers have different effects
- **WHEN** two helpers share structure or names but current blueprint evidence shows different state writes, side effects, errors, or consumers
- **THEN** they are not an equivalence-ready contraction candidate
- **AND** similarity alone does not authorize merging or deletion

#### Scenario: One facade delegates completely
- **WHEN** a public facade has no independent success behavior and current evidence proves complete delegation to the retained primary path
- **THEN** ArchitectureReduction MAY classify the facade for retained-delegating or removable treatment according to its external contract
- **AND** the selected disposition remains explicit

#### Scenario: Candidate inventory omits a same-intent path
- **WHEN** independent discovery finds a same-intent adapter, wrapper, helper, alias, or public entrypoint absent from the candidate inventory
- **THEN** candidate completeness is blocked
- **AND** no contraction action is reported ready

### Requirement: Contraction requires behavior-preserving proof and lineage repair
Only equivalence-proven replacement or facade-proven delegation SHALL be eligible for contraction. After an authorized contraction, the same model lineage, implementation inventory, bindings, contracts, tests, and affected evidence SHALL be updated together; uncertain candidates SHALL remain typed unresolved obligations.

#### Scenario: Removal would orphan a model or test binding
- **WHEN** a proposed removed surface is still the sole implementation, consumer, CodeContract target, or test target for an active obligation
- **THEN** reduction is blocked until a valid replacement or retirement disposition is modeled and evidenced
- **AND** the surface is not deleted as dead code

#### Scenario: Evidence-ready contraction is applied
- **WHEN** an authorized contraction preserves the observable contract and every affected owner has a current target disposition
- **THEN** the resulting candidate revision updates the implementation inventory and all affected bindings
- **AND** affected model, test, topology, structure, installation, and process evidence is revalidated before closure

#### Scenario: A candidate remains uncertain
- **WHEN** equivalence, facade delegation, external use, or side-effect ownership cannot be established
- **THEN** ArchitectureReduction records the exact unresolved question and owner
- **AND** it does not convert uncertainty into a cleanup recommendation
