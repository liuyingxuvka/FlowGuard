# FlowGuard Primary Path Authority

Primary Path Authority enforces one rule for path-sensitive work: one business
intent has one primary runtime authority. If the primary path fails, expose the
failure and repair that primary path instead of automatically running an
alternate implementation and returning success.

Use it when feature work, bug repair, compatibility cleanup, field migration,
helper-route cleanup, install sync, or release confidence could leave old
paths, aliases, wrappers, helper routes, compatibility facades, old fields,
backup caches, migration paths, or recovery tools as hidden runtime authority.

Broad claims require ContractExhaustionMesh Cartesian coverage, TestMesh shard
evidence, and Risk Evidence Ledger gates.

Authority uniqueness is keyed by the stable exact `business_intent_id`, not by
the pair of intent text and path name. Two different path ids for the same
exact intent are still two competing authorities. PPA consumes the complete
affected surface/candidate inventory from existing Preflight and Behavior
Commitment evidence, reuses an equivalent current path when one exists, and
requires current RuntimePathEvidence plus proof-artifact coverage before a
green decision. Additional public surfaces may delegate, remain manual-only,
migrate, be removed, or be scoped with evidence; they cannot become a second
independent success path.
