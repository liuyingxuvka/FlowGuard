## ADDED Requirements

### Requirement: AI entry reports proven understanding depth and exact gaps
The FlowGuard AI entry SHALL report the deepest proven blueprint layer and the status of every triggered layer using current structured results. It SHALL identify the exact missing or stale model, semantic source, implementation surface, CodeContract, test node, assertion, resource, oracle, intent contribution, owner, and evidence reference rather than self-rating its understanding.

#### Scenario: Only inventory and traceability are proven
- **WHEN** source inventory and model-to-code traceability pass but independent semantics or row-level test evidence is missing
- **THEN** AI reports the deepest proven layer as traceability
- **AND** it does not describe the software blueprint as complete or reconstructable

#### Scenario: Static blueprint is complete
- **WHEN** every required static layer has current evidence and empirical reconstruction has not run
- **THEN** AI reports static blueprint complete and reconstruction `not_run`
- **AND** it explains that no rebuild was performed

#### Scenario: A user asks what remains unknown
- **WHEN** the user requests a sufficiency or gap explanation
- **THEN** AI translates current structured findings into exact owner/evidence gaps and bounded next actions
- **AND** skipped, stale, blocked, and not-run states remain distinct

### Requirement: Lightweight use, sufficiency, implementation admission, and user choice remain independent
The AI entry SHALL default ordinary work to current authority identity plus the smallest affected blueprint neighborhood. Whole-software qualification SHALL activate only for an explicit whole-blueprint, export, self-qualification, or release obligation. Model sufficiency, DevelopmentProcessFlow implementation admission, and the user's authorization to write code SHALL remain independent decisions.

#### Scenario: A small scoped change is requested
- **WHEN** current affected ownership is known and no whole-blueprint claim is requested
- **THEN** AI loads and validates only the affected neighborhood and required ancestors
- **AND** it does not scan, export, or reconstruct the whole project

#### Scenario: User authorizes code before understanding is sufficient
- **WHEN** the user permits implementation but required model or blueprint gaps remain unresolved
- **THEN** AI preserves the user's choice while reporting implementation admission blocked or scoped by its native owner
- **AND** permission does not upgrade the understanding result

#### Scenario: User asks to bypass modeling
- **WHEN** the user explicitly chooses direct production work within an otherwise authorized scope
- **THEN** AI records the choice and preserves all skipped or unresolved model claims
- **AND** it does not falsely report skipped understanding checks as passed
