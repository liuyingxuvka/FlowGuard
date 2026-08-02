## ADDED Requirements

### Requirement: Specialized maturation receipts reuse the canonical receipt authority
FlowGuard SHALL represent maturation evidence as a typed projection of the canonical immutable evidence receipt and SHALL NOT create a second store, currentness flag, or fallback receipt format.

#### Scenario: Canonical receipt verification fails
- **WHEN** the underlying evidence receipt is missing, altered, stale, ineligible, or bound to different obligations
- **THEN** the specialized maturation verification also fails visibly
