## ADDED Requirements

### Requirement: Reused TestMesh evidence is receipt-backed and independently verified
TestMesh SHALL count reused child evidence only after loading its immutable
producer receipt and concrete result artifact and independently verifying the
exact receipt identity, subject, owner, claim scope, covered obligation ids,
resolved functional inputs, verifier identity, result fingerprint, terminal
status, and receipt-store supersession state. Reuse-ticket, proof-reference,
and caller current/match fields are descriptive only and MUST NOT substitute
for verification.

#### Scenario: Exact-current child is reused
- **WHEN** the loaded child receipt and result independently verify against the
  frozen TestMesh requirement and no eligible receipt supersedes it
- **THEN** TestMesh MAY count the child without re-executing its producer

#### Scenario: Reuse metadata says current
- **WHEN** reuse metadata says current but the loaded receipt, result,
  obligation scope, or current input fingerprint differs
- **THEN** TestMesh MUST reject the reuse and invalidate only the owning child

### Requirement: TestMesh receipts cover the exact owned inventory
Each TestMesh child receipt SHALL bind the complete frozen inventory owned by
that child, including every applicable partition item, leaf matrix cell,
transition cell, payload case, generated case, coverage shard, and required
obligation. Parent composition MUST compare the receipt inventory with the
owner-plan inventory for exact equality and MUST NOT infer completeness from a
green command, a subset, a count, or an aggregate label.

#### Scenario: A green child omits one owned case
- **WHEN** a child exits zero but its receipt omits one item from its frozen
  owned inventory
- **THEN** TestMesh MUST classify the child coverage as incomplete and block
  parent composition

#### Scenario: Inventory changes after a child receipt
- **WHEN** an owned required item is added, removed, or rebound after a receipt
  was produced
- **THEN** only the affected child and its dependent parent closure MUST become
  stale

### Requirement: Payload coverage requires real executable result proof
A TestMesh payload case SHALL count as executed only when an owner receipt
binds the exact case id, input identity, executable command and implementation
identity, concrete result artifact, observed payload fingerprint, oracle
outcome, and terminal exit status. Planned examples, expected payloads,
schema-only checks, and synthetic proof references MUST NOT count as payload
execution.

#### Scenario: Expected payload matches the schema
- **WHEN** a planned or synthesized payload matches the declared schema but no
  executable owner receipt contains the observed result
- **THEN** TestMesh MUST keep the payload case `not-run`

#### Scenario: Executed payload result is current
- **WHEN** a loaded terminal-success receipt binds the exact payload case,
  executable implementation, observed output, oracle, and current inputs
- **THEN** TestMesh MAY count that case as current executable evidence

### Requirement: Runtime pytest evidence preserves exact leaf accounting
TestMesh runtime evidence SHALL keep the static `ProjectTestInventory`
separate from the concrete pytest collection.  A runtime result SHALL preserve
the exact requested, collected, deselected, and unrelated node identities,
materialize every concrete parameterized leaf, and record selected,
executed, reused, or not-run state together with the outcome and reason.
The parent projection SHALL expose both `selected_count` and
`explicitly_not_selected_count` and SHALL enforce
`planned = selected + explicitly_not_selected` in addition to
`planned = executed + reused + not_run`.
Parent totals and status SHALL be independently recomputed from the leaf rows;
a parent summary SHALL NOT manufacture a missing leaf or hide a skipped,
failed, xfailed, xpassed, or not-run leaf.

#### Scenario: One static parameterized node expands to multiple leaves
- **WHEN** a static inventory contains one parameterized pytest node and the
  native collection reports two concrete case ids
- **THEN** runtime evidence SHALL contain two distinct leaf identities,
  preserve their individual outcomes and reasons, and keep the static node as
  the parent match only

#### Scenario: Selected leaf has no terminal result
- **WHEN** pytest collection includes a selected concrete leaf but its native
  report contains no terminal result row
- **THEN** the leaf SHALL remain `not_run` with a visible reason
- **AND** a declared-complete parent SHALL remain blocked

#### Scenario: Parent skip total disagrees with concrete leaves
- **WHEN** one concrete leaf is skipped but a caller-supplied parent summary
  declares zero skipped tests
- **THEN** TestMesh SHALL report a parent/leaf count mismatch
- **AND** the parent SHALL remain blocked even when its process exit code is
  zero

#### Scenario: Exact current result is reused
- **WHEN** a concrete leaf is covered by an independently verified current
  producer receipt and is not executed in the current invocation
- **THEN** runtime evidence SHALL mark it `reused`, not `executed` or
  `not_run`, and SHALL retain its terminal outcome and receipt owner outside
  the static inventory artifact

### Requirement: Contract exhaustion runtime evidence reconciles the exact finite case inventory
ContractExhaustionMesh runtime evidence SHALL consume the exact generated case
inventory from one current `ContractExhaustionReport` and SHALL preserve each
case's required, selected, explicitly-not-selected, executed, reused, not-run,
outcome, reason, oracle status, and observed-result identity.  A native
execution owner SHALL provide terminal result rows or independently verified
reuse rows; the reconciliation owner MUST NOT launch a target, synthesize a
result, or treat a synthetic fault profile as live execution evidence.

#### Scenario: A finite contract case has no terminal row
- **WHEN** a required generated case is selected but neither an executed nor a
  reused terminal row names that exact case id
- **THEN** the case SHALL remain `not_run` with a visible reason
- **AND** a complete claim SHALL be blocked

#### Scenario: Runtime rows do not match the generated finite inventory
- **WHEN** a native result names an unknown case, both executed and reused rows
  name one case, or the observed oracle status disagrees with the generated
  expected status
- **THEN** runtime evidence SHALL preserve the mismatch as a blocker
- **AND** the parent SHALL NOT infer case closure from a green aggregate status

#### Scenario: Contract runtime evidence is complete and current
- **WHEN** every required generated case has one terminal executed or
  independently receipt-backed reused row, every row has an observed result
  fingerprint, the static report and finite coverage universe are current, and
  parent counts reconcile with case rows
- **THEN** the runtime report MAY expose a complete claim while preserving the
  exact report and universe fingerprints for downstream TestMesh composition
