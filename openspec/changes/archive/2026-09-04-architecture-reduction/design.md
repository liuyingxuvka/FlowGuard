## Context

The existing architecture inventory already has a complete candidate
denominator and typed reduction decisions. The missing contract is the
ordinary read boundary: a compact summary must not silently discard unresolved
members, while candidate detail must be available by id without expanding the
whole report.

## Decisions

1. Keep the current ArchitectureReduction owner and projections; do not create
   a new optimizer or reconstruction route.
2. Make similarity and cost diagnostic signals only. A candidate becomes
   contraction-ready only after complete current proof and one post-action
   owner.
3. Retain dynamic, public, serialized, and unbound surfaces when proof is
   incomplete, and make the unresolved state visible.

## Verification

The existing ArchitectureReduction model, compact projection tests, model
regression receipt, and final release parent own executable verification. This
change only records their requirement boundary.
