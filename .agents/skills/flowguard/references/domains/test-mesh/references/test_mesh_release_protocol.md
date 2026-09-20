# TestMesh Release Protocol

Load this file for release, publish, archive, broad done, or full parent gates.

## Frozen Parent Gate

Freeze source, toolchain, environment, inventory revision, owner plan, covered
obligations, and exact child receipt set before starting the final parent.
There is exactly one final full validation owner for the maintenance unit.

Routine evidence may defer explicitly release-only children, but the release
gate must resolve every deferred, skipped, stale, not-run, and scoped item. A
routine pass cannot be promoted to release confidence.

## Parent Receipt

The parent receipt names all exact child ids/fingerprints, planned/executed/
failed/not-run counts, inventory revision, source/toolchain/environment
identity, terminal result, and proof artifacts. Reuse is limited to children
that independently satisfy `test_mesh_reuse_protocol.md`.

Do not run the final full gate through a Scheduled Task, unattended retry, or
parallel owner. If interrupted, complete the descendant-cleanup check before
any retry decision.

## Claim Boundary

TestMesh proves the declared validation inventory only. Distribution/install
parity, Git/tag/release identity, and broad risk remain separate evidence.
