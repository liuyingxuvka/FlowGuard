# Architecture Reduction proof details

This reference is conditional. Load it only for an explicit contraction, behavior retirement, or full Architecture Reduction proof audit. The main protocol owns route admission and the hard boundary; this file owns the detailed observable-contract, retirement, candidate, compatibility, and proof-status fields.

## Observable Contract

Before considering ordinary behavior-preserving contraction, declare the
behavior that must not change:

- source FlowGuard model id;
- source code boundary id;
- public entrypoints;
- observable outputs;
- observable state;
- observable side effects;
- validation boundaries;
- rationale.

This contract is the boundary for "same behavior." Internal proof fields may be
removed or merged only when the declared public behavior is preserved or the
report explicitly downgrades the proof to property-only. A property-only result
cannot authorize ordinary contraction. Intentional behavior retirement does
not pretend to satisfy equivalence; it uses the separately typed retirement
proof below.

## Intentional Behavior Retirement

Use `retire_behavior` only when the complete effective current product/DNA goal explicitly no
longer needs the behavior. It requires `proof_status=authorized_retirement` and
one exact-current `ArchitectureRetirementProof` that binds:

- the current-goal rationale and independently complete retirement inventory;
- retired Behavior Commitment Ledger commitments and behavior-block ids;
- model, code, test, public-interface, consumer, route, skill, prompt,
  topology-relation, release-claim, and negative-case identities;
- one disposition for every responsibility: `retire`, `replace`, `migrate`, or
  `retain_history`;
- every replacement or migration owner as exact-current and unambiguous;
- the complete required affected-validation route set and governed identity
  fingerprints.

Core DNA protections do not vanish just because a historical wrapper or route
is no longer needed. Required input/output, state/effect, topology,
model-code-test binding, negative-case/oracle, and bug-to-model-depth feedback
responsibilities must either remain under one current owner, move to one named
current owner with evidence, or receive an explicit product-level behavior
retirement disposition. Unknown responsibility is `unresolved`.

Retirement must leave zero alias, compatibility reader or adapter, fallback,
forwarder, alternate automatic success path, dangling current reference, or
retained runtime authority. Historical documents and immutable evidence may
remain only as archive history; they cannot keep runtime authority.

## Model-To-Code Mapping

Map model elements to implementation nodes before recommending contraction:

- FunctionBlock -> function, class, handler, command, component, or module;
- state field -> dataclass field, storage key, UI state, config, or record;
- side effect -> file write, API call, database write, subprocess, UI effect;
- public entrypoint -> CLI, API, export, UI route, command, or plugin surface.

If this mapping is absent, the review should block rather than producing a
code-level recommendation from model-only simplification.

## Candidate Types

Use `ArchitectureReductionCandidate` rows for candidate contractions:

- `merge_handlers`: two or more handlers can become one owner;
- `merge_modules`: modules can share one target module;
- `collapse_adapter`: an adapter only forwards or normalizes without owning
  behavior;
- `remove_branch`: a branch is dead, subsumed, or behavior-equivalent to
  another branch;
- `remove_state_field`: a state field is not part of the observable contract
  and does not affect required properties;
- `merge_state_phase`: two phases are behavior-equivalent at the observable
  boundary;
- `remove_duplicate_validation`: repeated validation paths prove the same
  obligation;
- `keep_public_facade`: internals can shrink but compatibility facade stays;
- `manual_review`: the candidate is intentionally deferred.

## Compatibility Surfaces

When a candidate exists because of an old, alternate, or compatibility-like
surface, add `CompatibilitySurfaceClassification` rows before deciding whether
the candidate is ready. Classify old command aliases, event names, input
shapes, migration branches, old/replaced fields, field aliases, public facades,
pass-through compatibility adapters, retired validation artifacts, and negative
legacy tests.

Use these classifications:

- `current_contract`: still active behavior; remove/collapse is blocked;
- `boundary_adapter`: edge stays but should translate into the current owner
  contract; public surfaces require StructureMesh;
- `negative_legacy_test`: evidence that retired input is rejected; do not
  delete unless replacement rejection evidence is cited;
- `archive_only`: historical evidence only; runtime authority blocks;
- `prune_candidate`: obsolete surface that can contract when proof status is
  ready;
- `evidence_needed`: insufficient evidence; linked candidates are not ready.

This classification is pre-reduction guidance. It does not replace
`LegacyPathDisposition` for post-repair closure when an old executable path
remains reachable.
It also does not replace FieldLifecycleMesh disposition when an old or
compatibility-like field remains reachable.

A retained same-intent facade preserves only an external entry boundary. It
must name the stable intent, active commitment, selected primary path, and owner
contract, with current evidence that it delegates to that path. Independent
business success, primary side effects, terminal mutation, or delegation to a
different same-intent path blocks keep-facade readiness.

A behavior selected for retirement cannot survive through a retained facade,
boundary adapter, old command/event/input alias, compatibility reader,
fallback, or forwarder. If an external contract is still required, classify it
as `retain` or migrate it to one current replacement owner; do not call the old
runtime path retired.

## Proof Status

Every candidate must have one proof status:

- `safe_by_equivalence`: preserves declared observable behavior;
- `safe_by_public_facade`: internals can shrink while the public facade stays;
- `authorized_retirement`: may end explicitly identified obsolete behavior
  only when the complete exact-current retirement proof passes;
- `property_only_safe`: preserves selected invariants only, not full behavior;
- `needs_conformance_replay`: needs real-code replay before code contraction;
- `risky_keep`: looks duplicate but should stay visible;
- `blocked_by_missing_evidence`: do not contract yet.

For ordinary actions, only `safe_by_equivalence` and
`safe_by_public_facade` can become ready contraction candidates.
`authorized_retirement` is ready only with `target_action=retire_behavior` and
one complete current `ArchitectureRetirementProof`; it is invalid on an
ordinary contract action. Property-only and replay-needed candidates are
useful diagnostics, not safe deletion or retirement proof.
Scoped, risky, or evidence-needed candidates that remain relevant should be
recorded as maintenance obligations with their owner route instead of prose
TODOs.

