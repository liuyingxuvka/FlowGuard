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

Within one bounded parent invocation, an immutable observation may carry each
independently verified exact-current child once and let several aggregates
reference their declared exact subsets. The aggregates keep distinct subjects,
owners, obligations, and result identities. After native producers terminate,
run one fresh source identity comparison, publish every new leaf from those
fresh owner contexts without per-leaf source rebuilding or receipt-store scans,
then reconcile the new receipt identities once. Matching identities do not
repeat child semantic verification, drift blocks publication, and a skipped
source comparison or receipt reconciliation is `not_run`. The observation is
transient and cannot become a persistent cache, receipt alias, alternate store,
or later-invocation success authority.

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
