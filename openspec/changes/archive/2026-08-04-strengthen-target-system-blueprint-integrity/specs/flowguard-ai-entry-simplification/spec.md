## MODIFIED Requirements

### Requirement: Whole-software blueprint work is task-triggered rather than a selectable depth mode
The AI entry path SHALL derive a whole-software blueprint obligation only from explicit blueprint, export, qualification, or owner-declared release facts. It SHALL NOT add a user-selectable duplicate depth mode, and ordinary work SHALL continue loading only the smallest affected current owner closure.

#### Scenario: User asks for an ordinary bounded code change
- **WHEN** no whole-software blueprint claim is requested or required
- **THEN** the entry path does not scan, export, or materialize the complete software blueprint

#### Scenario: User asks for a complete portable software blueprint
- **WHEN** the request explicitly claims or exports a whole-software blueprint
- **THEN** the entry path triggers the existing inventory, alignment, mesh, portable, and process owners and preserves their independent results

### Requirement: AI entry reports proven understanding depth and exact gaps
The FlowGuard AI entry SHALL report the deepest proven blueprint layer and the status of every triggered layer using current structured results. It SHALL identify the exact missing or stale model, semantic source, implementation surface, CodeContract, test node, assertion, resource, oracle, intent contribution, owner, and evidence reference rather than self-rating its understanding.

#### Scenario: Only inventory and traceability are proven
- **WHEN** source inventory and model-to-code traceability pass but independent semantics or row-level test evidence is missing
- **THEN** AI reports the deepest proven layer as traceability
- **AND** it does not describe the whole software blueprint as complete

#### Scenario: Static blueprint is complete
- **WHEN** every required static layer has current evidence
- **THEN** AI reports static blueprint complete and identifies `static_blueprint` as the deepest proven layer

#### Scenario: A user asks what remains unknown
- **WHEN** the user requests a sufficiency or gap explanation
- **THEN** AI translates current structured findings into exact owner/evidence gaps and bounded next actions
- **AND** skipped, stale, blocked, and not-run states remain distinct

### Requirement: Lightweight use, sufficiency, implementation admission, and user choice remain independent
The AI entry SHALL default ordinary work to current authority identity plus the smallest affected blueprint neighborhood. Whole-software qualification SHALL activate only for an explicit whole-blueprint, export, self-qualification, or release obligation. Model sufficiency, DevelopmentProcessFlow implementation admission, and the user's authorization to write code SHALL remain independent decisions.

#### Scenario: A small scoped change is requested
- **WHEN** current affected ownership is known and no whole-blueprint claim is requested
- **THEN** AI loads and validates only the affected neighborhood and required ancestors
- **AND** it does not scan, export, or materialize the whole project blueprint

#### Scenario: User authorizes code before understanding is sufficient
- **WHEN** the user permits implementation but required model or blueprint gaps remain unresolved
- **THEN** AI preserves the user's choice while reporting implementation admission blocked or scoped by its native owner
- **AND** permission does not upgrade the understanding result

#### Scenario: User asks to bypass modeling
- **WHEN** the user explicitly chooses direct production work within an otherwise authorized scope
- **THEN** AI records the choice and preserves all skipped or unresolved model claims
- **AND** it does not falsely report skipped understanding checks as passed

## REMOVED Requirements

### Requirement: AI entry reports compact reconstruction readiness
**Reason**: Compact depth and gaps already belong to the canonical blueprint-readiness summary; the separate reconstruction-named result duplicated that decision.

**Migration**: Consume owner status, behavior status, static-blueprint readiness, deepest proven layer, and first gap from the compact blueprint summary.

## ADDED Requirements

### Requirement: AI entry reports compact blueprint readiness
The AI entry surface SHALL report owner-level status, behavior-block status, static-blueprint readiness, deepest proven layer, and the first unresolved gap from compact content-addressed identities without loading the full software blueprint.

#### Scenario: User chooses direct implementation
- **WHEN** the user authorizes direct implementation while readiness is incomplete
- **THEN** the AI entry SHALL preserve the incomplete readiness report and the separate user choice
- **AND** it SHALL NOT claim that permission deepened understanding


### Requirement: AI understanding status is compact and affected-first
The ordinary AI entry SHALL return target identity, affected members, ordered layer statuses, deepest proven layer, first unresolved gap, gap count, and implementation-admission boundary directly from the current normalized affected neighborhood.

#### Scenario: Ordinary task asks whether understanding is sufficient
- **WHEN** a task identifies affected behavior or workflow owners without requesting whole-target qualification
- **THEN** the AI entry SHALL inspect only the exact affected neighborhood and required ancestors
- **AND** it SHALL NOT construct or serialize the complete target blueprint

### Requirement: Whole qualification is explicit and separately visible
The AI entry SHALL materialize a complete target blueprint only when task facts explicitly request blueprint creation, export, qualification, or a named self/release qualification obligation.

#### Scenario: User authorizes an ordinary code change
- **WHEN** whole-target qualification is not an explicit task fact
- **THEN** the entry SHALL keep whole materialization `not_run`
- **AND** implementation admission SHALL be decided only for the declared affected scope
