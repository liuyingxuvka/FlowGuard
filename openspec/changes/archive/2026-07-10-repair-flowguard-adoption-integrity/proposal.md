## Why

FlowGuard's project record can report healthy adoption while its generated `AGENTS.md` block is stale and its skill verifier silently omits a skill that lacks the very control directory being scanned. Adoption and suite-membership claims must therefore be derived from canonical inventories and semantic comparisons before any project upgrade can be trusted.

## What Changes

- Add one canonical, bidirectionally validated inventory for the kernel plus all sixteen public satellite skills.
- Make project adoption generation preserve every current governance rule, including Behavior Commitment Ledger, Primary Path Authority, path-sensitive commitments, latest-schema-first behavior, and default replacement.
- Add dry-run and semantic-diff behavior to project upgrade so an operator can see rule loss before any managed block is rewritten.
- Make project audit compare package, manifest, generated managed-block semantics, recorded version, and actual skill membership instead of accepting markers alone.
- Replace check-directory-driven and hard-coded suite discovery with inventory-versus-filesystem reconciliation; a missing control root becomes a failure rather than an omitted subject.
- **BREAKING**: incomplete, extra, duplicated, or semantically stale adoption records will no longer receive a healthy project-audit result.

## Capabilities

### New Capabilities

- `flowguard-suite-inventory`: Defines canonical skill-suite membership, bidirectional discovery, ownership metadata, and omission/extra-member failure behavior.

### Modified Capabilities

- `project-adoption-version-gate`: Requires semantic managed-block parity, safe dry-run upgrades, and version/content checks before project adoption can pass.

## Impact

Affected surfaces include `flowguard/project_adoption.py`, project-audit and project-upgrade CLI behavior, `AGENTS.md` generation, `.flowguard/project.toml`, suite marker/readiness scripts, tests, adoption logs, and the generated suite inventory. This change is the prerequisite for all other changes in this upgrade program; it does not rewrite skill prompts, topology rules, evidence receipts, model regression execution, installation, or release behavior.
