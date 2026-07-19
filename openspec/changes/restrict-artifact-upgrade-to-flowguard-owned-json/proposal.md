## Why

FlowGuard v0.58.3 `project-upgrade` treated any JSON object with a numeric
`schema_version` as a FlowGuard artifact. A real Khaos upgrade therefore
rewrote a target-owned retrieval fixture from integer `1` to string `"1.0"`,
breaking the target's canonical evaluator after FlowGuard's own release gates
had passed.

## What Changes

- Restrict JSON handling to a finite two-owner boundary: exact current
  `report`/`trace` envelope registrations (no writer) or the exact historical
  behavior-ledger producer shape from commit `56083c1e` (one dedicated
  direct-to-current writer).
- Preserve unknown and target-owned JSON byte-for-byte, even when it contains a
  numeric `schema_version`, a `payload` field, or lives under a directory that
  FlowGuard scans.
- Keep the supported historical behavior ledger on its single typed,
  deterministic direct-to-current migration path; keep registered
  `report`/`trace` envelopes current-only.
- Add a real project-upgrade regression that proves target-owned JSON content
  and SHA-256 identity remain unchanged while a typed historical FlowGuard
  behavior ledger is migrated successfully in the same run.
- Keep the bundled behavior-ledger template as an exact current canonical
  producer so strict runtime loading never depends on omitted-field defaults.
- Release the corrected behavior as FlowGuard v0.58.4 with no fallback,
  compatibility reader, path-based ownership guess, or dual parser.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `artifact-schema-upgrade`: Direct artifact upgrade may write only the exact
  historical `56083c1e` behavior-ledger shape; exact current registered
  envelopes are observed without serialization, and shared markers or partial
  legacy shapes do not grant ownership.
- `project-adoption-version-gate`: Artifact scanning and project upgrade may
  write only the exact historical behavior-ledger owner and must leave every
  unknown or target-owned JSON artifact unchanged.

## Impact

- Affected implementation: `flowguard/artifact_upgrade.py`, the
  `project-upgrade` path that consumes it, and the bundled current
  behavior-ledger template.
- Affected evidence: project-adoption model, artifact/project upgrade tests,
  SkillGuard-maintained FlowGuard suite contract, installation parity, and
  release verification.
- No target project, Khaos repository, FlowPilot repository, or third-party JSON
  schema becomes part of FlowGuard's ownership boundary.
