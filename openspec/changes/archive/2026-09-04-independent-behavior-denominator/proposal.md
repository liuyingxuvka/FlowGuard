## Why

The current Behavior Commitment Ledger can validate registered commitments and
source surfaces, but it does not yet carry a typed independently discovered
inventory of externally observable behaviors. A ledger or test suite can
therefore appear complete while an unregistered public behavior, intent,
failure, recovery path, or specialist-owned surface was never included in the
denominator.

## What Changes

- Extend the canonical BCL payload with an optional, independently supplied
  behavior inventory. The inventory is not generated from BCL rows, tests, or
  caller-selected candidates.
- Give every discovered behavior a stable `behavior_id`, source fingerprint,
  public surface, intent, success outcome, explicit errors and recovery paths,
  owner, and one canonical disposition.
- Use four explicit inventory dispositions: `modeled`,
  `delegated_to_named_owner`, `explicitly_out_of_scope_with_reason`, and
  `blocked_gap`. Keep the historical BCL source-surface values (`delegated`
  and `scoped`) separate; they are not inventory dispositions and their
  existing ledger semantics remain unchanged.
- Add conservation checks for duplicate, missing, and unexpected behavior ids,
  plus identity separation between the discovery authority and the BCL ledger.
- Require disposition-specific handoff data: a modeled row names one BCL
  commitment and one primary model owner; a delegated row names a native owner
  inventory and typed relation; an out-of-scope row records reason, boundary,
  and rationale; a blocked gap records an explicit gap reason, boundary, and
  rationale.
- Keep completeness opt-in on the current ledger until a native discovery
  owner populates the project inventory. The repository adds only a bounded
  manifest materializer that resolves explicitly declared source files and
  fingerprints them; it is not a semantic discovery engine, second truth
  source, automatic test generator, or release/full validation route.
- Add a fail-closed public-surface gap report that counts explicit production
  declarations (Python API registry, CLI parser, templates, and console
  entrypoint) but never converts declaration names into behavior rows. The
  report records the unmanifested UI, file/config, installation, provider,
  fault/recovery, and release classes and keeps the whole-product denominator
  blocked until a native owner authors their semantic rows.

## Impact

The change affects the canonical BCL model, loader/upgrade round-trip,
public exports, the adoption/template payload, focused tests, and this OpenSpec
delta. It does not alter FlowGuard explorer or model-revision-set ownership,
and it does not claim that the current project has populated every behavior.
