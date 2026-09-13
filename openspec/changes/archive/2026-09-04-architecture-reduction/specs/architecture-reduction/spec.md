## ADDED Requirements

### Requirement: Architecture reduction provides compact and candidate-detail reads
Architecture Reduction SHALL provide an ordinary summary projection, an exact candidate-detail projection, and an explicit full-audit projection over the same complete candidate denominator.

#### Scenario: Ordinary self-maintenance read
- **WHEN** a caller requests routine cleanup guidance
- **THEN** the system SHALL return compact counts, decisions, blockers, fingerprints, and candidate ids without duplicating full evidence witnesses

#### Scenario: Candidate detail is requested
- **WHEN** a caller requests one candidate id
- **THEN** the system SHALL return that candidate's complete callers, consumers, contract, proof obligations, and next route from the same current inventory

### Requirement: Similarity and cost do not authorize contraction
The system SHALL require complete current caller, consumer, observable behavior, state, error, side-effect, public-surface, model, and test/oracle proof before classifying a surface or step as contraction-ready.

#### Scenario: Candidate resembles another route
- **WHEN** two routes have similar code or output shape but equivalence or replacement proof is incomplete
- **THEN** the candidate SHALL remain unresolved or retained
- **AND** no deletion, merge, delegation, alias, or fallback SHALL be authorized

#### Scenario: Proof-backed duplicate is contracted
- **WHEN** all caller, consumer, state, error, side-effect, public-surface, model, and test/oracle obligations are current and equivalent
- **THEN** the system MAY authorize one typed contraction action with one post-action owner
- **AND** the old path SHALL receive an explicit delete, delegate, replace, or scope disposition

### Requirement: Path optimization depth is evidence-bound
Every current model path SHALL expose a bounded structural cost measurement,
an optimization depth, and the current evidence identity that licensed that
depth. A low-cost path MAY remain lightweight; a high-cost or otherwise
triggered path SHALL remain visibly deep-required until a finite deep review
closes. A caller flag alone SHALL NOT create a high-cost conclusion.

#### Scenario: Ordinary low-cost model
- **WHEN** measured costs are below the declared thresholds and no other deep
  trigger is current
- **THEN** the result SHALL be `lightweight` with current cost evidence
- **AND** it SHALL not load or invent a deep candidate set

#### Scenario: Triggered model
- **WHEN** a cost, release, model-miss, explicit-request, growth, or necessity
  trigger is current
- **THEN** the result SHALL expose the trigger and its current evidence
- **AND** the result SHALL be `deep_required` or a current `deep_closed` result,
  never an unexplained `single_clear_path`

### Requirement: Compact reduction output keeps an actionable index
The compact projection SHALL retain a bounded candidate index that maps each
candidate id to its signal, source/code location, disposition, proof status,
missing proof, and required next route. It SHALL provide exact detail for one
candidate without embedding the full audit report.

#### Scenario: Candidate index read
- **WHEN** a consumer reads the ordinary reduction projection
- **THEN** it SHALL be able to choose one candidate and one owning next route
- **AND** unresolved and not-run states SHALL remain explicit

### Requirement: Prompt material has explicit staged admission
Prompt budgets SHALL distinguish catalog, preselection, admitted-core, and
triggered-expansion material. Each material edge SHALL declare whether it is
mandatory, its exact trigger, its owner, and its claim boundary. Natural-language
conditional wording SHALL not be the sole source of budget classification.

#### Scenario: Routine route uses only the admitted core
- **WHEN** a caller takes the ordinary FlowGuard route without a declared expansion trigger
- **THEN** the system SHALL admit the bounded core prompt material
- **AND** it SHALL report catalog and preselection counts without injecting triggered expansion material

#### Scenario: A declared trigger expands one owned satellite
- **WHEN** a caller declares a trigger owned by a specific satellite route
- **THEN** the system SHALL add only that satellite's triggered material
- **AND** the expansion SHALL retain its owner and claim fields in the budget report

### Requirement: Portable blueprint integrity is strict and target-neutral
Portable blueprint serialization SHALL reject duplicate keys, non-finite
numbers, and root/fingerprint drift; it SHALL write atomically and perform one
deep verification per trust boundary. It SHALL describe the target's bounded
state/transition/interface behavior without claiming that optional
reconstruction is ordinary validation.

#### Scenario: Invalid portable payload is rejected
- **WHEN** a portable blueprint contains duplicate keys or a non-finite number
- **THEN** verification SHALL fail visibly before the payload is accepted
- **AND** no alternate reader or fallback interpretation SHALL be attempted

#### Scenario: Valid portable payload is written atomically
- **WHEN** a target-neutral blueprint passes strict integrity checks
- **THEN** the system SHALL write it through one atomic replacement and return its canonical fingerprint
- **AND** the result SHALL remain an integrity claim rather than an executed reconstruction claim

### Requirement: Validation dependencies represent evidence consumption
The full-validation owner graph SHALL contain only explicit child-to-child
receipt dependencies. Unrelated owners SHALL not be blocked by list order, and
the final parent SHALL still require all required owners to reach terminal
success before release claims are made.

#### Scenario: An owner consumes a declared parent receipt
- **WHEN** a validation owner declares a parent evidence receipt
- **THEN** the graph SHALL schedule it after that receipt is terminal-success and current
- **AND** the owner SHALL retain its own receipt identity

#### Scenario: An unrelated owner has no dependency edge
- **WHEN** two owners share no declared evidence input
- **THEN** the graph SHALL not create an ordering edge between them
- **AND** either owner SHALL remain independently schedulable

### Requirement: Architecture cleanup preserves one current path
Cleanup SHALL not retain a second runtime authority, compatibility reader, fallback success path, or unbound wrapper after a contraction.

#### Scenario: Duplicate runner is replaced by its model entry
- **WHEN** a wrapper and its direct model runner are proven behaviorally equivalent
- **THEN** all blueprint, commitment, documentation, and test bindings SHALL point to the direct runner before the wrapper is removed
- **AND** no alias or forwarding wrapper SHALL remain
