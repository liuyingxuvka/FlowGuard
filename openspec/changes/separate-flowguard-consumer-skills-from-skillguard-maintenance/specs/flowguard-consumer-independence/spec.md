## ADDED Requirements

### Requirement: Independent consumer skills
Every graduated FlowGuard consumer skill SHALL install and perform its domain work without SkillGuard, SkillGuard Global Router, author contracts, or author receipts.

#### Scenario: Clean consumer environment
- **WHEN** the 17-skill FlowGuard distribution is installed into an empty `CODEX_HOME`
- **THEN** every FlowGuard skill SHALL be loadable and its representative native checks SHALL run without installing or invoking SkillGuard

#### Scenario: Consumer skill is invoked
- **WHEN** an ordinary project invokes a FlowGuard skill
- **THEN** the skill SHALL NOT require or create `.skillguard`, consume an author receipt, or route through SkillGuard

### Requirement: Consumer prohibition scan
The consumer builder and installed-layout validator MUST reject SkillGuard author-control material in any FlowGuard consumer skill.

#### Scenario: Hidden contract is present
- **WHEN** a staged consumer skill contains `.skillguard/**`
- **THEN** distribution activation SHALL block and report the exact prohibited paths

#### Scenario: Prompt contains maintenance dependency
- **WHEN** a consumer prompt references a SkillGuard command, contract trio, receipt, router onboarding, or managed marker
- **THEN** prompt and distribution validation SHALL block

### Requirement: Ordinary project zero-write behavior
FlowGuard project use and adoption MUST NOT cause SkillGuard files, prompts, processes, or project records to appear.

#### Scenario: Empty project is adopted
- **WHEN** `project-adopt` runs in an ordinary project
- **THEN** it SHALL write only FlowGuard-owned project records and SHALL leave `.skillguard` and SkillGuard prompt markers absent

#### Scenario: FlowGuard check runs
- **WHEN** a native FlowGuard scenario or model check runs in an ordinary project
- **THEN** the process tree and resulting project tree SHALL contain no SkillGuard execution or state

### Requirement: Safe legacy control withdrawal
An upgrade SHALL remove a retired installed SkillGuard control file only when the previous FlowGuard installer owns the exact path and its current content hash is unchanged.

#### Scenario: Installer-owned file is unchanged
- **WHEN** an old FlowGuard installation owns a `.skillguard` file and its hash matches the prior manifest
- **THEN** upgrade SHALL remove that file through the staged transaction

#### Scenario: Legacy file was modified locally
- **WHEN** a retired file is unowned or its current hash differs
- **THEN** upgrade SHALL preserve it, report a conflict, and make no independent consumer-readiness claim until resolved
