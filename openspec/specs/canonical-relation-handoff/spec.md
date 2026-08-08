# canonical-relation-handoff Specification

## Purpose
Define a bounded, direct-current carrier that passes exact canonical relations and provenance to existing decision owners without creating a second discovery, routing, or completion authority.
## Requirements
### Requirement: Canonical relation handoffs are direct current evidence carriers
FlowGuard SHALL represent only the bounded relations already established by current observed authority, canonical blueprint ownership, behavior commitments, or affected topology. Each handoff SHALL name a stable relation id and type, exact endpoint identities, behavior plane when relevant, source authority and fingerprint, currentness, affected member ids, and any unresolved gap. The handoff is evidence input to its consuming owner and MUST NOT become a search engine, maintenance group, review route, recommendation authority, or completion gate.

#### Scenario: A canonical owner establishes a bounded relation
- **WHEN** current authority establishes a same-intent, shared-owner, affected-sibling, shared-mechanism, adapter-only, duplicate-boundary, or false-friend relation
- **THEN** FlowGuard emits one immutable canonical relation handoff with exact source and endpoint identities
- **AND** the receiving owner materializes the relation into its own cases, bindings, structure decision, reduction candidate, or scoped finding

#### Scenario: A relation is absent, stale, or opaque
- **WHEN** no current canonical relation connects two candidate endpoints, or the relation source is missing, stale, ambiguous, or cannot resolve both endpoints
- **THEN** FlowGuard preserves an unresolved relation gap
- **AND** it MUST NOT infer a maintenance group or launch a free-form repository similarity search to support a broad claim

#### Scenario: A relation crosses behavior planes
- **WHEN** two endpoints share language or implementation shape but belong to different primary behavior planes
- **THEN** the handoff records false-friend or typed related-context evidence
- **AND** the consuming owner MUST NOT merge their ownership or evidence without a separately established current relation

#### Scenario: A consumer receives relation provenance
- **WHEN** ExistingModelPreflight, ContractExhaustionMesh, Code Structure Recommendation, Model-Test Alignment, Architecture Reduction, Structure Simplification, or obligation-family parity consumes a canonical relation handoff
- **THEN** that consumer remains the sole owner of its native decision and proof
- **AND** the relation id alone MUST NOT satisfy the consumer's completion criteria
