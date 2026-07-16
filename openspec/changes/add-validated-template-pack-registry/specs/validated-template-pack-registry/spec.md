## ADDED Requirements

### Requirement: Canonical validated template-pack manifest
FlowGuard SHALL accept only the current `flowguard.template-pack-manifest.v1` schema for template-pack selection and SHALL require its declared manifest digest to equal the canonical digest of all semantic manifest content.

#### Scenario: Current sealed manifest is accepted
- **WHEN** a manifest has a non-empty id and version, structurally valid entries, and the canonical declared digest
- **THEN** manifest validation returns the canonical manifest identity without findings

#### Scenario: Unknown or stale manifest is rejected
- **WHEN** a manifest uses an unknown schema or its declared digest is absent or differs from current semantic content
- **THEN** manifest validation fails closed and selection cannot receive a selectable disposition

### Requirement: Structurally closed template entries
Every template-pack entry MUST declare a unique non-empty template id and version, integer priority, exact top-level field ownership, exact required parameters, and a JSON-compatible template field map. A manifest MUST contain at most one base entry; the base MUST have no predicates and MUST NOT be composable, while every specialized entry MUST have at least one predicate.

#### Scenario: Owned fields and template fields agree
- **WHEN** an entry's owned fields exactly equal the top-level keys in its template field map and its declared parameters exactly equal its placeholders
- **THEN** the entry passes structural validation

#### Scenario: Entry authority is ambiguous
- **WHEN** ids are duplicated, more than one base is declared, a base has predicates or is composable, a specialized entry has no predicate, or fields/parameters do not agree
- **THEN** the manifest is invalid and reports the precise structural findings

### Requirement: Bounded hard-predicate matching
FlowGuard SHALL evaluate template predicates as an all-or-nothing conjunction over top-level selection-context keys using only `equals`, `one_of`, `contains`, `contains_all`, and `exists`. FlowGuard MUST NOT execute arbitrary predicate code or use fuzzy scores.

#### Scenario: All predicates match
- **WHEN** every declared hard predicate for a specialized entry evaluates true against the selection context
- **THEN** that entry is included in the specialized match set

#### Scenario: One predicate fails or is missing
- **WHEN** any declared predicate evaluates false or its context key is absent, except for an explicit `exists: false` predicate
- **THEN** that entry is excluded from the specialized match set

#### Scenario: Predicate operator or operand is invalid
- **WHEN** an entry declares an unknown operator or an operand shape not supported by that operator
- **THEN** manifest validation fails before selection

### Requirement: Explicit zero-match and base-template behavior
FlowGuard SHALL evaluate specialized entries before any base entry. With zero specialized matches, it SHALL select the sole declared base with disposition `base_selected`, or emit disposition `no_match` when no base is declared.

#### Scenario: Declared base handles zero matches
- **WHEN** no specialized entry matches and the valid manifest declares one base entry
- **THEN** the selection receipt identifies only that base entry and records `base_selected`

#### Scenario: Zero matches remain explicit
- **WHEN** no specialized entry matches and the valid manifest has no base entry
- **THEN** the selection receipt records `no_match` with no selected template ids

#### Scenario: Base never competes with specialized matches
- **WHEN** at least one specialized entry matches
- **THEN** the base entry is excluded from matched and selected template ids

### Requirement: Deterministic one-match selection
FlowGuard SHALL select the sole matching specialized entry with disposition `selected` and SHALL preserve its exact identity in the selection receipt.

#### Scenario: Exactly one specialized entry matches
- **WHEN** a valid manifest and context produce one specialized match
- **THEN** that entry is the only selected template id and the receipt records `selected`

### Requirement: Fail-closed multi-match composition
With multiple specialized matches, FlowGuard SHALL compose only when every match explicitly declares `composable` and all owned-field sets are pairwise disjoint. Canonical composition order MUST be ascending `(priority, template_id)`. All other multiple-match cases SHALL produce `conflict` without selected template ids.

#### Scenario: Multiple disjoint composable entries match
- **WHEN** every matching entry is composable and no top-level field has more than one owner
- **THEN** the receipt records `composed` and selected ids in canonical order

#### Scenario: A matching entry refuses composition
- **WHEN** multiple entries match and at least one matching entry is not composable
- **THEN** the receipt records `conflict`, names the non-composable matches, and selects none

#### Scenario: Matching entries claim the same field
- **WHEN** multiple composable entries match but at least two claim the same top-level field
- **THEN** the receipt records `conflict`, names the conflicting fields, and selects none

### Requirement: Canonical selection receipts
Every selection attempt SHALL emit a `flowguard.template-pack-selection-receipt.v1` receipt containing the manifest digest, canonical context digest, matched ids, selected ids, disposition, findings, and a digest of the receipt content.

#### Scenario: Selection receipt is deterministic
- **WHEN** the same valid manifest and JSON-compatible context are selected repeatedly
- **THEN** every semantic receipt field and the selection digest are identical

#### Scenario: Invalid manifest remains auditable
- **WHEN** selection receives an invalid or stale manifest
- **THEN** it emits `invalid_manifest` with findings and no selected ids rather than guessing a template

### Requirement: Strict deterministic template instantiation
FlowGuard SHALL instantiate only a current receipt with disposition `selected`, `base_selected`, or `composed`. It SHALL require supplied parameter keys to exactly equal the selected entries' declared parameters, recursively substitute `${parameter}` string placeholders, and merge only disjoint top-level owned fields.

#### Scenario: Current selection instantiates
- **WHEN** a selectable current receipt and the exact required parameters are supplied
- **THEN** FlowGuard renders the selected template field maps and emits an `instantiated` instance receipt

#### Scenario: Parameters are missing or extra
- **WHEN** supplied parameter keys differ from the exact selected parameter set
- **THEN** instantiation is blocked with explicit missing or unexpected parameter findings

#### Scenario: Selection cannot be instantiated
- **WHEN** a receipt has `no_match`, `conflict`, `invalid_manifest`, or is stale
- **THEN** FlowGuard emits a blocked instance receipt and no rendered field map

### Requirement: Chained instance receipts and stale validation
Every instance attempt SHALL emit a `flowguard.template-pack-instance-receipt.v1` receipt binding the manifest digest, selection digest, canonical parameter digest, selected ids, status, findings, rendered field map, and its own digest. Receipt validators SHALL recompute the expected current result and return `current` only for exact identity equality; they MUST NOT mutate or renew an old receipt.

#### Scenario: Selection input changes
- **WHEN** manifest content or selection context changes after a selection receipt was created
- **THEN** selection-receipt validation returns `stale`

#### Scenario: Instance input or output changes
- **WHEN** manifest content, selection context, parameters, selected identities, or rendered output differs from the instance receipt
- **THEN** instance-receipt validation returns `stale`

#### Scenario: All chained identities remain equal
- **WHEN** the manifest, context, selection, parameters, and rendered output reproduce the receipt exactly
- **THEN** receipt validation returns `current`

### Requirement: FlowGuard file templates project through a target-owned neutral handoff
FlowGuard SHALL expose the current file-template factory inventory as one strict `skillguard.target_template_projection.v1` object only after exact native route selection, and SHALL keep generated-file, factory, validator, and claim semantics FlowGuard-owned.

#### Scenario: Exact file-template route selects one domain factory
- **WHEN** the target supplies a declared `route:flowguard-template:*` route
- **THEN** the native registry marks exactly that factory plus the validated base as applicable and the central selector chooses the domain factory without lexical scoring

#### Scenario: Unknown template route blocks
- **WHEN** the route is not declared by the current FlowGuard file-template inventory
- **THEN** the target adapter blocks before emitting a consumable neutral projection
