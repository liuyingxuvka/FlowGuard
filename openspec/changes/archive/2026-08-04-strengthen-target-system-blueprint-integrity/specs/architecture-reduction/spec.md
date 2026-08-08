## ADDED Requirements

### Requirement: Cleanup completeness uses an independent candidate denominator
A whole-target or self-cleanup review SHALL derive its expected candidates independently from the review that classifies proof. The denominator SHALL cover applicable command routes, branches, adapters, wrappers, facades, helpers, repeated validations, duplicate owners, and oversized boundaries, and every member SHALL end as `retain`, `contract`, or `unresolved`.

#### Scenario: Discovery source is disabled and candidates become empty
- **WHEN** one required discovery source is unavailable and the candidate list is empty
- **THEN** cleanup completeness SHALL be unknown or incomplete
- **AND** it SHALL NOT claim that nothing needs cleanup

### Requirement: Self-reduction dispositions are explicit current evidence
Every denominator surface and signal SHALL receive an independently produced typed disposition bound to the exact current self-blueprint, target revision, implementation inventory, denominator fingerprint, and candidate identity when the signal forms a contraction candidate. A singleton signal MAY be retained only when its exact source surface has a current public contract, behavior owner, or unique delegation owner. A signal that forms a contraction candidate SHALL NOT be retained merely because its source surface exists; it requires either candidate-specific evidence that the compared members have different commitments or observable contracts, or current contraction proof. Absence of either authority SHALL remain `unresolved` and block cleanup release readiness.

#### Scenario: Unmatched branch is automatically labeled retain
- **WHEN** independent discovery finds a branch signal that has no current typed retain record and no verified contraction proof
- **THEN** the branch SHALL remain `unresolved`
- **AND** the cleanup report SHALL NOT become release-ready

#### Scenario: Caller supplies a label-only self-blueprint
- **WHEN** a caller supplies an object with passing labels or fingerprints that is not the exact typed blueprint rebuilt from the current target root
- **THEN** self-reduction SHALL reject the object before candidate classification

#### Scenario: An owned singleton helper has no contraction relation
- **WHEN** one helper signal does not form a multi-surface contraction candidate
- **AND** its exact source surface has a current behavior owner and current source evidence
- **THEN** self-reduction MAY emit a typed retain disposition for that exact signal
- **AND** an otherwise identical signal without current ownership evidence SHALL remain `unresolved`

#### Scenario: Similar surfaces form a contraction candidate
- **WHEN** two or more surfaces form one candidate with the same observable-contract identity
- **THEN** current existence or source ownership alone SHALL NOT retain the candidate signals
- **AND** the candidate SHALL require exact different-commitment retain evidence or verified contraction proof

### Requirement: Reduction proof is non-circular and externally bounded
Only current observable equivalence or public-facade delegation evidence independent from candidate generation SHALL authorize `contract`. Same-origin fingerprints, code size, lexical similarity, or internal happy-path equality SHALL NOT authorize contraction.

#### Scenario: Candidate and safety proof come from the same blueprint row
- **WHEN** no independent behavior contract, execution evidence, or facade-delegation proof supports a candidate
- **THEN** the candidate SHALL remain `unresolved` with a risky-keep boundary

#### Scenario: External consumer still uses an internal-looking facade
- **WHEN** internal tests pass after removing a facade but a current external consumer contract fails
- **THEN** the reduction SHALL be blocked

### Requirement: Reduction proof is independently verified and execution-unique
Self-reduction SHALL accept proof authority only from the repository's one current canonical validation-owner store. A candidate proof SHALL be a child-bound aggregate over independently executed, exact-current owner receipts: at minimum one test execution bound to the candidate's own observable-contract coverage and candidate-level parity evidence covering caller/consumer, state, side effect, and error obligations. The producer SHALL execute each child under bounded process-tree supervision before saving a passing receipt; a caller-authored leaf receipt, alternate temporary store, relabeled suite receipt, timeout, cancellation, failed command, skipped child, blocked child, or cleanup-unconfirmed process tree SHALL NOT authorize contraction. The consumer SHALL reload the aggregate and every child from the canonical store, rebuild their current owner contexts, run the native verifier, and compare exact receipt identities and obligations. Different candidates SHALL NOT reuse one aggregate, proof artifact, result fingerprint, child execution, or execution-owner identity through different wrappers.

#### Scenario: Typed proof wrapper contains caller-authored current booleans
- **WHEN** a structurally valid proof carries a caller-authored passing verification but the canonical receipt or current context does not verify
- **THEN** the candidate SHALL remain `unresolved`

#### Scenario: Two candidates rewrap one proof execution
- **WHEN** two candidate proof records use different receipt ids but share one proof artifact, result fingerprint, or execution identity
- **THEN** both candidates SHALL be blocked from contraction readiness until independently owned evidence exists

#### Scenario: Caller writes a passing leaf receipt without running its command
- **WHEN** a caller stores a passing validation-owner leaf whose payload merely asserts test and four-way parity success
- **THEN** self-reduction SHALL reject it because no supervised child executions and child-bound aggregate exist

#### Scenario: A current test is unrelated to the candidate
- **WHEN** a passing test receipt names a current global test that is absent from the candidate's observable-contract coverage
- **THEN** the test SHALL NOT satisfy the candidate proof

#### Scenario: One parity child is missing
- **WHEN** the aggregate omits caller/consumer, state, side-effect, or error parity evidence required for the candidate
- **THEN** contraction readiness SHALL remain blocked

### Requirement: Cleanup evidence is refreshed before and after contraction
Any implemented contraction SHALL invalidate affected model, inventory, topology, resource, binding, consumer-parity, and test evidence and SHALL require current before-and-after identities before release. A read-only review SHALL also recheck its governed source and proof-owner identities immediately before publication so a concurrent write cannot turn an earlier bundle into a current result.

#### Scenario: Source changes after a green cleanup review
- **WHEN** a candidate is implemented after the review fingerprint was created
- **THEN** the pre-change review SHALL become stale
- **AND** affected post-change evidence SHALL be required before acceptance

#### Scenario: Source changes during a cleanup review
- **WHEN** another writer changes a governed source or proof input after the review begins but before its result is published
- **THEN** the final currentness recheck SHALL block publication of a green review

### Requirement: Candidate proof executes exact tests and behavior parity
A contraction proof SHALL execute every exact candidate-related test node and every candidate-bound behavior replay under the explicit proof producer. Test evidence SHALL report the requested and collected node identities, require every collected node to pass, require zero skipped, xfailed, xpassed, deselected, missing, or unrelated nodes, and prove execution of the exact nontrivial oracle members bound by current coverage. Process exit zero, an empty collection, `assert True`, and caller-authored pass counts SHALL NOT establish test authority. Candidate parity SHALL execute every affected implementation member and public entrypoint reached by the candidate and SHALL compare its current input, output, state, effect, and error case oracles; checking only metadata labels or dimension names SHALL NOT establish parity.

#### Scenario: Exit zero hides an xfailed candidate test
- **WHEN** the exact candidate command exits zero but one requested node is xfailed, skipped, deselected, missing, or backed only by a trivial assertion
- **THEN** the test child SHALL be rejected
- **AND** the candidate SHALL remain unresolved

#### Scenario: Parity script checks dimension names only
- **WHEN** a parity child confirms that five dimension labels are present without executing every candidate member and its bound oracle lines
- **THEN** the parity child SHALL be rejected as metadata-only evidence

### Requirement: Facade and caller authority is derived and unambiguous
Public-facade proof facts SHALL be derived from the current self blueprint, current BehaviorCommitmentLedger source surface and commitment, and exact behavior/code binding. A proof caller SHALL NOT submit delegation, intent, commitment, primary-path, owner-contract, or independent-authority facts. Caller discovery SHALL resolve calls to canonical implementation surface ids. A qualified or short symbol MAY be normalized only when it resolves to exactly one current surface; a call matching several surfaces SHALL produce an explicit candidate caller-resolution gap.

#### Scenario: Caller fills every facade field with passing values
- **WHEN** a caller supplies internally consistent facade delegation fields that are absent from or contradict the current ledger or code binding
- **THEN** no public-facade proof SHALL be produced

#### Scenario: One short call matches two helpers
- **WHEN** a raw short call can name two current surfaces
- **THEN** neither surface SHALL silently inherit that caller
- **AND** the affected candidate SHALL expose an ambiguity gap until a canonical surface-id edge exists

### Requirement: Candidate actions have one primary owner per code member
When several current candidates include the same code member, self-reduction SHALL derive at most one independently selected primary candidate action for that member. If no current authority selects one primary, every conflicting action SHALL remain blocked and the member SHALL remain unresolved.

#### Scenario: One helper is both a remove and merge target
- **WHEN** two proof-bearing candidates assign different actions to the same helper without one current primary-candidate binding
- **THEN** neither action SHALL be contraction-ready
- **AND** the conflict SHALL be named in the cleanup review

### Requirement: Canonical proof storage is repository-confined and non-reparse
The self-reduction consumer and producer SHALL derive the sole canonical validation-owner store from the repository root and SHALL expose no caller-selectable receipt-root input. The store, receipt, proof artifact, and every existing path component SHALL remain inside the resolved repository and SHALL NOT be a symlink, junction, mount substitution, or other reparse point.

#### Scenario: Canonical store name is a junction to another directory
- **WHEN** the expected store path or a proof artifact traverses a junction, symlink, reparse point, absolute path, or parent escape
- **THEN** proof publication and consumption SHALL fail visibly

### Requirement: Publication rechecks a fresh blueprint and denominator
The read-only review SHALL never execute proof commands. Immediately before returning its result, it SHALL rebuild the current self blueprint and independent reduction denominator from the repository root and compare their complete authority identities, candidate inventory, caller graph, and governed evidence with the initially reviewed bundle. The fresh rebuild is a currentness comparison only and SHALL NOT become a fallback authority.

#### Scenario: A new governed source appears during review
- **WHEN** a source, test, model, ledger, binding, or reduction-denominator member changes after initial discovery
- **THEN** the final fresh comparison SHALL block publication of the earlier review
