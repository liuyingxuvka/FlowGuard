## ADDED Requirements

### Requirement: Self-reduction reviews the complete duplicate-path denominator
Blueprint-guided self-reduction SHALL discover candidate duplicate command routes, branches, adapters, wrappers, facades, helpers, validation paths, and repeated structures within the declared FlowGuard boundary. Every candidate SHALL receive an explicit retain, contract, or unresolved disposition.

#### Scenario: Duplicate path is not an oversized module
- **WHEN** two command or validation paths appear to own the same externally visible intent without forming an oversized module or identical syntax tree
- **THEN** the candidate inventory SHALL still include the relation for review

### Requirement: Broader discovery does not authorize deletion
No reduction candidate SHALL be contracted unless current observable-contract, primary-owner, equivalence or delegation, caller, lifecycle, and required-validation evidence licenses the action.

#### Scenario: Similar helpers lack equivalence proof
- **WHEN** two helpers look similar but their behavior equivalence and caller migration are unproven
- **THEN** the reduction report SHALL keep them unresolved
- **AND** no cleanup step SHALL delete or merge them

### Requirement: Self-reduction caller discovery is indexed once
The self-reduction reviewer SHALL derive caller ownership from one deterministic reverse call-alias index over the current governed implementation surfaces. It SHALL NOT rescan the complete surface inventory separately for every candidate member, and the indexed result SHALL preserve the exact caller identities produced by the declared call-matching semantics.

#### Scenario: A large self-blueprint contains many candidate members
- **WHEN** the reviewer evaluates caller relations for multiple oversized, route, branch, adapter, wrapper, helper, or validation candidates
- **THEN** each governed surface contributes its call aliases to the reverse index once
- **AND** candidate lookup returns the same exact caller set without a member-by-all-surfaces nested scan

### Requirement: Composed self-maintenance reuses one exact blueprint
When one invocation requests both self-blueprint qualification and architecture-reduction review, the command SHALL build the self-blueprint once and pass that exact fingerprinted bundle to the reduction reviewer. Reuse SHALL remain invocation-local and SHALL NOT create a fallback or second authority.

#### Scenario: Blueprint and reduction are reviewed together
- **WHEN** a caller selects the composed self-maintenance option
- **THEN** the result reports the same self-blueprint fingerprint in both bounded reviews
- **AND** no second self-blueprint build is executed

#### Scenario: A governed input changes before another invocation
- **WHEN** source, test, resource, model, or intent evidence changes
- **THEN** the next composed invocation builds a new current blueprint
- **AND** no prior in-memory or serialized bundle is silently accepted

### Requirement: Compact self-maintenance projects bounded fields directly
When compact output is requested, the composed self-maintenance command SHALL derive its bounded summary directly from the in-memory blueprint and reduction objects. It SHALL NOT first expand the complete blueprint or complete reduction payload merely to discard most of that material.

#### Scenario: A complete self-blueprint contains many code and test bindings
- **WHEN** the caller requests compact composed self-maintenance output
- **THEN** the command emits the declared bounded status and identity fields without invoking complete-payload expansion
- **AND** the full-detail path remains available only when the caller explicitly omits compact mode

### Requirement: Immutable large evidence fingerprints are computed once
Large immutable blueprint evidence consumed by more than one stage SHALL compute its canonical fingerprint once per object and reuse that exact value for downstream composition. Reuse SHALL NOT alter the fingerprint payload or create a mutable cache authority.

#### Scenario: Behavior evidence feeds both blueprint qualification and reduction
- **WHEN** the same immutable behavior report is consumed by both stages in one composed invocation
- **THEN** its complete fingerprint payload is evaluated once
- **AND** both stages receive the exact same canonical fingerprint

### Requirement: Large canonical payloads are fingerprinted without complete-copy amplification
Canonical fingerprint and byte-count calculation for a large blueprint payload SHALL stream the exact canonical JSON representation. The implementation SHALL NOT retain several complete serialized copies of the same logical payload while constructing its normalized physical projection.

#### Scenario: A normalized blueprint contains many exact coverage edges
- **WHEN** normalization computes logical identity, logical size, source size, and physical size
- **THEN** the canonical encoder feeds each fingerprint and count incrementally
- **AND** the logical payload is released before the physical projection is materialized
