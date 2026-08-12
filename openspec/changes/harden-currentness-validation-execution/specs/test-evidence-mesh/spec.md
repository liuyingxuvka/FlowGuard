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

