## ADDED Requirements

### Requirement: One manifest-backed model simulator
FlowGuard SHALL provide one public simulator command that audits and consumes the canonical model-regression manifest rather than maintaining a second model catalog or discovering an alternate executable owner.

#### Scenario: User lists registered models
- **WHEN** the user invokes the simulator in list mode
- **THEN** the command reports every registered model id, tier, availability, and native runner after manifest audit without executing a model

#### Scenario: Manifest is incomplete
- **WHEN** the canonical manifest omits a discovered model or names a missing required model or runner
- **THEN** the simulator returns blocked and executes no model

### Requirement: Selection is explicit and complete
The simulator SHALL require one or more model selectors or an explicit all-model option for execution, SHALL support exact ids and declared glob selectors, and SHALL reject an unmatched selector instead of reporting an empty successful run.

#### Scenario: One model is selected
- **WHEN** a current registered model id is supplied
- **THEN** the simulator executes only that model's declared native runner and reports its terminal result

#### Scenario: Selector matches no model
- **WHEN** a supplied exact id or glob matches no available registered model
- **THEN** the simulator returns invalid input and executes no model

#### Scenario: Execution scope is omitted
- **WHEN** execution is requested without a model selector or the explicit all-model option
- **THEN** the simulator returns invalid input rather than silently running all models

### Requirement: Native runners retain domain authority
The simulator SHALL dispatch to the runner declared by each selected manifest entry and SHALL NOT reinterpret model semantics, replace target-owned checks, or create a second successful implementation path.

#### Scenario: Native runner fails
- **WHEN** a selected model's declared runner exits nonzero or reports a non-pass terminal result
- **THEN** the simulator preserves that non-pass result and cannot promote it to success

### Requirement: Simulator results are durable and bounded
Every retained simulator run SHALL produce one terminal report, one receipt per executed model, complete compressed stdout/stderr evidence, bounded diagnostics, and a scoped current-head update only after all terminal artifacts are durable.

#### Scenario: Model emits a large JSON report
- **WHEN** a native runner emits a large complete report on stdout
- **THEN** the complete stream is retained once as a compressed evidence object and parent/child JSON contains references and bounded summaries rather than another full copy

#### Scenario: Run stops before terminal result
- **WHEN** the simulator is interrupted before the terminal report is durable
- **THEN** it does not update the scoped current head and the incomplete artifacts cannot support a current success claim
