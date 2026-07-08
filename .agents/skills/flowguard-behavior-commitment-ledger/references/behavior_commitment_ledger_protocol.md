# Behavior Commitment Ledger Protocol

Use the ledger as the upstream behavior inventory. Source surfaces are docs,
APIs, commands, UI capabilities, skills, tests, OpenSpec requirements, release
notes, or process docs that promise behavior. Commitments are the external
promises those surfaces make.

Each commitment records actor, trigger, expected result, failure boundary,
source refs, one primary owner model, subordinate supporting or child models,
dependencies, evidence ids, validation boundary, and rationale. A scoped-out
row still needs owner, reason, validation boundary, and rationale.

For `path_sensitive=true`, attach Primary Path Authority evidence with
`behavior_path_binding_from_primary_path_report()`. The ledger does not run a
second fallback checker. If PPA is blocked, the commitment is blocked.

For broad done, release, publish, archive, production, or full confidence,
project the ledger through `behavior_commitment_contract_exhaustion_plan()`.
Pass generated case ids, shard ids, receipt ids, and risk gate ids to
Model-Test Alignment, TestMesh, and Risk Evidence Ledger.
