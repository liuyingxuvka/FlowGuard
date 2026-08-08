## ADDED Requirements

### Requirement: Current topology evidence is independently produced and registered
Evidence used to activate or qualify the observed model-system head SHALL originate from an exact supervised terminal execution owned by the declared child or progress-contract evidence owner. A self-blueprint compiler, full model parent, ModelMesh consumer, or qualification call SHALL NOT generate, relabel, or register a passing current receipt for itself or for a child while evaluating the claim that consumes that receipt. Registration SHALL admit and verify an already terminal immutable receipt without launching or simulating its producer.

#### Scenario: Parent manufactures a child pass during aggregation
- **WHEN** the full model parent or blueprint compiler creates a passing child receipt or execution row inside the same aggregation that consumes it
- **THEN** observed authority SHALL reject the evidence as self-generated
- **AND** matching source, model, test, or snapshot fingerprints SHALL NOT make it independent

#### Scenario: Qualification registers its own current evidence
- **WHEN** a qualification or audit route executes, synthesizes, or rewrites an evidence result and registers that result as current before completing the same claim
- **THEN** registration and qualification SHALL be blocked
- **AND** the route SHALL require a separately supervised terminal producer receipt

#### Scenario: Existing terminal receipt is registered directly
- **WHEN** an immutable terminal receipt already names the exact producer owner, subject snapshot, covered child or progress contract, inputs, environment, result, and fingerprint
- **THEN** the authority store MAY verify and register that receipt without running its producer
- **AND** later parent aggregation SHALL consume the unchanged registered identity

### Requirement: Full model parent authority remains aggregation-only
The full model parent receipt SHALL prove only the declared aggregation over current child, reattachment, feedback-progress, and interface receipts. It SHALL NOT project its own terminal result onto a child, replace a missing child receipt, or become a second evidence producer for a child-owned obligation.

#### Scenario: Parent pass is reused as every child pass
- **WHEN** a full parent terminal receipt is assigned to two or more child obligations that lack their own terminal producer receipts
- **THEN** observed authority SHALL reject the child coverage and parent closure
- **AND** the full parent MAY remain only a failed or blocked aggregation result
