## Context

FlowGuard already has one current observed model authority, a canonical
project-blueprint builder, strict portable serialization, and explicit
validation-owner receipts. This change composes those existing owners; it does
not create a parallel optimizer, reconstruction route, or second bundle
authority.

## Decisions

1. Keep `prompt_budget.review_prompt_bundles` as the single prompt telemetry
   owner and add a unique persistent-context projection.
2. Keep the existing ArchitectureReduction protocol file as the detailed
   owner, but admit it only from the explicit contraction/retirement route.
3. Use the existing `project-blueprint-portable-export` and
   `portable-blueprint-verify` commands to materialize and isolate the self
   bundle; no new reconstruction command is introduced.
4. Record leaf execution gaps honestly in the existing self-maintenance
   payload; do not create thousands of duplicate tests.
5. Freeze source, model, toolchain, installation, and Git identities before
   one final validation parent and the v0.68.9 release.

## Verification

- Focused prompt-budget and skill-document checks after route edits.
- Portable export followed by isolated portable verification.
- Affected model/test alignment and self-maintenance checks once the product
  changes are stable.
- One foreground frozen final validation parent before release.
