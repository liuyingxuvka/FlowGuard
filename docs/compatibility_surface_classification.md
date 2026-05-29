# Compatibility Surface Classification

Compatibility surface classification is a pre-reduction check inside
Architecture Reduction. It asks whether a candidate contraction is removing
ordinary duplicate code or changing a surface that exists to support an old,
alternate, or public path.

Use it before treating these surfaces as safe contraction work:

- old command aliases, event names, or input shapes;
- migration or recovery branches;
- pass-through adapters for earlier contracts;
- public facades kept for imports, CLIs, APIs, or file formats;
- negative tests that prove retired inputs are rejected;
- historical mappings or archived compatibility evidence.

## Classifications

`current_contract`

The surface is still part of the current behavior contract. Removing or
collapsing it is blocked unless a separate behavior-changing change explicitly
updates the contract.

`boundary_adapter`

The edge remains supported, but the implementation should immediately translate
into the current owner contract. Public boundary adapters require StructureMesh
or equivalent public-entrypoint parity evidence.

`negative_legacy_test`

The old path is not supported, and the surface proves it is rejected. Do not
delete this evidence as dead code unless replacement rejection evidence is
cited.

`archive_only`

The material can remain as historical evidence only. It must not retain runtime
authority. If it can still write current state or authorize current behavior,
the classification is blocked.

`prune_candidate`

The surface appears obsolete and may be contracted when the linked
Architecture Reduction candidate also has ready proof status.

`evidence_needed`

The surface looks compatibility-related, but FlowGuard lacks enough evidence to
decide. Linked candidates are not ready until the missing evidence is supplied.

## Relationship To LegacyPathDisposition

`CompatibilitySurfaceClassification` happens before contraction. It tells an
agent or tool what kind of surface it is looking at.

`LegacyPathDisposition` happens during repair or closure. It proves that an old
or alternate executable path was deleted, blocked, delegated to the repaired
contract, repaired to the same contract, or explicitly scoped out.

Do not substitute one for the other. A surface classified as `prune_candidate`
may still need a `LegacyPathDisposition` later if it remains executable in a
closure claim.

## Minimal Review Pattern

1. Declare the observable architecture contract.
2. Map model elements to code nodes.
3. List contraction candidates.
4. Add compatibility-surface classifications for old or alternate-looking
   surfaces.
5. Run `review_architecture_reduction()`.
6. Send public entrypoint work to StructureMesh, replay gaps to conformance or
   Model-Test Alignment, and closure of executable old paths to
   `LegacyPathDisposition`.
