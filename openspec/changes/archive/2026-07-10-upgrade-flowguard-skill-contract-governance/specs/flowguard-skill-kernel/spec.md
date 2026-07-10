## ADDED Requirements

### Requirement: Compact Kernel Entrypoint
The kernel skill SHALL implement the standard entrypoint contract within a target budget of 120 lines. Detailed route inventories and specialist protocols SHALL be directly referenced rather than copied into the kernel. Any budget exception MUST be explicit, test-backed, and SHALL NOT weaken required headings or hard gates.

#### Scenario: Route table expansion exceeds budget
- **WHEN** generated or manually copied route details push the kernel beyond its approved budget without an exception
- **THEN** prompt-budget validation fails and directs the details to a routed reference

### Requirement: Generated Route Index
The kernel route index SHALL be generated from or parity-checked against the canonical route registry and suite inventory. It MUST identify public owner, delegated, and kernel-owned internal routes without inventing a new owner.

#### Scenario: New satellite is registered
- **WHEN** a canonical public satellite is added to the inventory and route registry
- **THEN** route-index check fails until the kernel projection includes the new route

### Requirement: Strict Broad Claim Boundary
The kernel SHALL state that missing, stale, skipped, `not_run`, `progress_only`, `scoped`, or `pass_with_gaps` evidence cannot support a broad done, full-governance, release, archive, or publication claim.

#### Scenario: Child result has gaps
- **WHEN** a required child route returns `pass_with_gaps`
- **THEN** the kernel output preserves that status and blocks broad closure
