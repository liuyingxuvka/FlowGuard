## ADDED Requirements

### Requirement: Preflight inventories the affected same-intent surface family
Full Existing Model Preflight SHALL inventory the affected declared UI, API,
CLI, alias, adapter, wrapper, helper, and compatibility surfaces before it
admits a new model or implementation boundary for an existing business intent.
The inventory SHALL preserve known commitment ids, stable business-intent ids,
business path ids, expected terminals, material state writes and side effects,
owners, current evidence, and explicit unknown or scoped surfaces.

#### Scenario: Affected same-intent family is complete
- **WHEN** a proposed change adds or changes a surface for an existing business intent and every affected declared surface has a materialized ownership and evidence row
- **THEN** Existing Model Preflight SHALL use that inventory when deciding reuse, extension, duplicate-boundary review, or a separate intent boundary

#### Scenario: Known family member is omitted
- **WHEN** a known UI, API, CLI, alias, adapter, wrapper, helper, or compatibility surface for the affected intent is absent without an explicit scoped disposition
- **THEN** Existing Model Preflight SHALL report an incomplete same-intent inventory and SHALL NOT support broad reuse or new-boundary confidence

#### Scenario: A new surface is not a new behavior boundary
- **WHEN** a proposed page, control, API entrypoint, command, alias, or adapter has the same actor, trigger and preconditions, expected terminal, failure boundary, material state writes, and side effects as an existing intent
- **THEN** Existing Model Preflight SHALL recommend reuse or extension of the existing commitment and primary path rather than a new behavior boundary

### Requirement: Preflight reuses existing commitment and path owners
Existing Model Preflight SHALL hand the existing commitment id and
selected primary path candidate to Behavior Commitment Ledger and Primary Path
Authority when the affected-family evidence identifies an equivalent current
business intent. Preflight SHALL NOT create a Product Design Language route, intent
ledger, delegate commitment, path-reuse owner, or parallel runtime controller.

#### Scenario: Equivalent current path exists
- **WHEN** the affected-family inventory contains an existing path with the same exact intent semantics and current passing runtime evidence
- **THEN** Existing Model Preflight SHALL preserve the existing commitment and primary-path identities in its reuse handoff

#### Scenario: Material external semantics differ
- **WHEN** the proposed behavior differs in actor, trigger or preconditions, expected result or terminal, failure boundary, material state writes, side effects, safety boundary, or another externally observable contract
- **THEN** Existing Model Preflight SHALL preserve the typed difference and route it to the existing BCL and downstream owners for a distinct-intent decision rather than silently merging or creating a parallel same-intent path

#### Scenario: Evidence cannot prove equivalence
- **WHEN** similarity, runtime, source, or ownership evidence is missing, stale, skipped, not run, progress-only, or opaque
- **THEN** Existing Model Preflight SHALL keep the reuse or separate-boundary decision scoped and SHALL name the missing existing-owner evidence
