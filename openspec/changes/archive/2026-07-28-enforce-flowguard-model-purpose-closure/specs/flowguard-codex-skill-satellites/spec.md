## ADDED Requirements

### Requirement: Every model-changing FlowGuard skill invokes the native purpose loop
All seventeen FlowGuard skill entrypoints SHALL require the same FlowGuard-owned purpose lifecycle whenever the current task creates or materially changes a concrete model instance: declare one or more concrete failures before construction, freeze the declaration, build or change the model, bind native known-good and per-failure known-bad proof, and close only on current evidence. This is a fixed workflow and SHALL NOT be exposed as a selectable mode.

#### Scenario: Satellite creates a model
- **WHEN** any FlowGuard satellite route creates or materially changes a concrete model instance
- **THEN** its AI guidance requires the task-specific declaration before construction and current native proof before a protection claim

#### Scenario: Satellite performs read-only review
- **WHEN** a FlowGuard route only reads or reports existing evidence and does not create or materially change a model
- **THEN** it does not invent a model merely to trigger the lifecycle, while any model claim it consumes remains bound to current closure evidence

### Requirement: Skill wording preserves instance-specific purpose
FlowGuard skill guidance SHALL state that a reusable model or skill is not permanently assigned one failure class; the AI declares the current instance's one-or-many protected failures for the task.

#### Scenario: Prompt implies one permanent model purpose
- **WHEN** a source or installed FlowGuard skill says a model type can only prevent one fixed failure
- **THEN** skill contract and prompt-parity checks fail
