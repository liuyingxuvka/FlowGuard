## ADDED Requirements

### Requirement: Modeled targets use exact ownership and unmodeled targets use explicit adoption discovery
Existing Model Preflight SHALL resolve current modeled targets only from the validated observed authority, exact affected blueprint ids, behavior commitments, and canonical relations. A target with no current DNA MAY enter explicit adoption candidate discovery, but candidate paths MUST remain non-authoritative and MUST NOT support an understanding or implementation-readiness claim.

#### Scenario: Current modeled target has an exact owner
- **WHEN** the validated observed authority maps the requested behavior or changed surface to an exact owner closure
- **THEN** preflight returns that closure and its canonical affected relations without lexical owner guessing or root-model substitution

#### Scenario: Modeled lookup is blocked
- **WHEN** behavior commitment or affected-owner resolution is missing, stale, ambiguous, or blocked
- **THEN** preflight preserves the blocker and MUST NOT change the result to fallback based on filename, token, class-name, or repository search matches

#### Scenario: Target has no adopted DNA
- **WHEN** a target has no validated current model authority
- **THEN** preflight may return candidate discovery context for adoption
- **AND** the result explicitly states that current understanding, ownership, and implementation readiness are unproved

### Requirement: Preflight consumes only bounded canonical relation handoffs
Full Existing Model Preflight SHALL consume canonical relation handoffs only after exact current owner and endpoint identities have been resolved. The relation MAY support reuse, extension, child-model, separate-boundary, Code Structure, or Architecture Reduction decisions, but it MUST NOT create a similarity-review prerequisite, maintenance group, change-impact inventory, or standalone completion claim.

#### Scenario: Current relation supports a bounded decision
- **WHEN** current blueprint, commitment, or topology authority emits a canonical relation for two in-scope endpoints
- **THEN** preflight records the relation id, type, source authority, endpoints, currentness, affected members, and any unresolved gap
- **AND** it preserves the downstream owner's proof requirements

#### Scenario: False friend keeps boundaries separate
- **WHEN** a canonical relation records cross-plane, different-intent, or false-friend evidence
- **THEN** preflight may keep the boundaries separate while preserving that exact evidence
- **AND** shared wording alone MUST NOT override the current owner identities

#### Scenario: Relation evidence is absent or stale
- **WHEN** no current canonical relation covers a proposed reuse or reduction decision
- **THEN** preflight reports the exact unresolved ownership or relation gap
- **AND** it MUST NOT infer a maintenance group or run a free-form similarity search

## MODIFIED Requirements

### Requirement: Self-maintenance preflight handoff
Existing Model Preflight SHALL feed exact current owner, duplicate-boundary, same-intent surface, and canonical relation findings to the existing self-maintenance owners before a new FlowGuard route boundary is added.

#### Scenario: Similar existing route exists
- **WHEN** preflight resolves a current route, owner, or canonical relation that can carry the requested responsibility
- **THEN** it SHALL recommend reuse, extension, child model, or Architecture Reduction before creating a new boundary
- **AND** it SHALL NOT create or require a similarity maintenance group

### Requirement: Full preflight proves the current owner map only
A full Existing Model Preflight result SHALL mean that the current bounded owner/model map and duplicate-boundary risks are understood; it SHALL NOT by itself claim task-local model sufficiency or implementation permission.

#### Scenario: Full preflight precedes open maturation gaps
- **WHEN** preflight is full but triggered current-owner coverage contributions or typed coverage gaps remain unresolved
- **THEN** downstream maturation MUST remain open and implementation admission MUST NOT infer readiness from the preflight decision

### Requirement: Preflight contributes current-system coverage to maturation
Existing Model Preflight SHALL project its selected current owners, expected same-intent surfaces, state/field/effect/entrypoint responsibilities, mesh boundaries, and unresolved current-owner coverage gaps as typed task-local maturation coverage contributions.

#### Scenario: Current surface omitted by candidate
- **WHEN** preflight independently identifies an in-scope current surface that the candidate maturation input omits
- **THEN** the compiled maturation universe MUST retain that surface as an uncovered item

## REMOVED Requirements

### Requirement: Existing model preflight consumes model angle deliberation
**Reason**: Concrete coverage gaps now feed TaskCoverageDemand and ModelMaturation directly.
**Migration**: Use exact affected-owner and typed maturation evidence.

### Requirement: ExistingModelPreflight consumes angle and similarity helpers
**Reason**: The independent angle route and standalone similarity engine are retired.
**Migration**: Consume canonical DNA, BCL, affected topology, and minimal typed relations directly.

### Requirement: Similarity evidence in full preflight
**Reason**: Requiring a standalone similarity review, maintenance groups, change-impact ids, and impacted-sibling inventories duplicates current blueprint ownership and canonical affected topology.
**Migration**: Consume a bounded canonical relation handoff only after exact current endpoints and source authority resolve; let the downstream owner materialize its own obligations.

### Requirement: Missing ledger fallback remains explicit
**Reason**: A visible fallback still creates a second understanding path and can disguise unresolved current ownership.
**Migration**: Preserve the blocked result for modeled targets or enter non-authoritative adoption discovery for unmodeled targets.
