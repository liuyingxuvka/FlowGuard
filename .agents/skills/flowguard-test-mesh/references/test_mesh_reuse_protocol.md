# TestMesh Reuse Protocol

Load this file whenever a prior test result may be reused or only affected
owners may rerun.

## Reuse Identity

Reuse requires one immutable terminal producer receipt and a current
`TestResultReuseTicket`. Match maintenance unit, native owner, request, covered
ids, inventory revision, source inputs, verifier/toolchain, dependencies,
environment, result status, exit status, and proof-artifact fingerprints.

Different owners or maintenance units never share execution authority even
when command text is identical. A copied receipt, report summary, cache hit,
or matching filename is not evidence reuse.

## Selective Rerun

Recompute freshness from explicit component edges. Execute only missing or
stale owners, preserve exact-current successful children, then recompose the
parent from the new and reused receipt ids/fingerprints. Unknown impact blocks;
it never silently expands to an unowned run-all fallback.

## Terminal Dispositions

- exact-current passing producer receipt: `reuse_current`;
- no result or stale result: `execute`;
- malformed, tampered, ambiguous, in-flight, or cleanup-unconfirmed:
  `blocked`.

`--resume` is execution, not a read-only receipt audit.
