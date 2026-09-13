# Target-neutral release descriptors

FlowGuard's release consumer is target-neutral. The same finite convergence
route can verify FlowGuard itself, SkillGuard, or an unrelated software
repository. A release is described by an explicit JSON target descriptor; the
descriptor is the only place that supplies the target's identity and release
surface.

```json
{
  "target_id": "example-service",
  "version": "2.4.0",
  "tag": "v2.4.0",
  "repository": "owner/example-service",
  "default_branch": "main",
  "distribution_kind": "source_only",
  "required_source_paths": [
    "README.md",
    "src/example_service/__init__.py"
  ],
  "required_check_ids": [
    "validation-owner:pytest"
  ],
  "assets": []
}
```

`required_source_paths` and `required_check_ids` are finite, explicit target
obligations. `distribution_kind` is either `source_only` or
`source_and_assets`; the latter also lists each asset and its SHA-256 digest.
The descriptor does not need Python metadata, a FlowGuard installation, a
SkillGuard registry, or any target-specific package convention.

The convergence order is deliberately one-way:

1. Freeze the target descriptor and the functional parent owner plan.
2. Execute only missing functional owners, or reuse exact-current terminal
   receipts.
3. Consume the immutable candidate receipt once for the tag and published
   phases.
4. Replaying the same terminal is read-only and creates no new owner, lease,
   freshness pointer, or validation epoch.

Nested model depth is independent of this release route. A target may use any
finite hierarchy (parent, child, cross-child connection, and additional
descendants); FlowGuard checks each declared boundary and connection without
requiring a fixed depth or multiplying every state combination into one
Cartesian table.

The public module command requires a descriptor explicitly:

```powershell
python -m flowguard release-verify --root . --target release-target.json --phase local-candidate --parent-receipt <parent-receipt-id> --receipt-root .flowguard/evidence/validation-owners --output candidate-receipt.json --json
python -m flowguard release-verify --root . --target release-target.json --phase tag --candidate-receipt candidate-receipt.json --parent-receipt <parent-receipt-id> --receipt-root .flowguard/evidence/validation-owners --output tag-receipt.json --json
```

The published phase adds the explicit repository and remote tag/release
identity. Release evidence stays in a controlled work directory and is not
copied into the target's source package.
