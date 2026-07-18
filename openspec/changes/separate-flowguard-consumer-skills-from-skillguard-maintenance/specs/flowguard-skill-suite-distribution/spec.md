## ADDED Requirements

### Requirement: Distribution is a clean consumer projection
FlowGuard SHALL construct its public 17-skill distribution from explicit target-owned paths and SHALL validate the staged projection before atomic activation.

#### Scenario: Author source contains SkillGuard controls
- **WHEN** a public distribution is built from the maintained FlowGuard source tree
- **THEN** the staged result SHALL omit every author-control path while retaining all target-owned prompt, reference, asset, script, and native runtime files

#### Scenario: Staged consumer validation fails
- **WHEN** reference closure, prohibited-path scanning, native checks, or inventory parity fails
- **THEN** the active installation SHALL remain unchanged and failure evidence SHALL be retained

## MODIFIED Requirements

### Requirement: Strategy guidance remains current across maintained skill projections
The maintainer-source projection SHALL synchronize and parity-check the current conditional DevelopmentProcessFlow skill, core protocol, conditional optimization and failure-triage references, OpenAI prompt, contract source, compiled contract, and check manifest after process-optimization maintenance under one FlowGuard maintenance unit. The consumer-distribution projection SHALL synchronize only target-owned guidance and referenced content and SHALL contain no SkillGuard contract, prompt, receipt, router, alias, wrapper, or fallback success path.

#### Scenario: Installed consumer protocol is stale
- **WHEN** the installed DPF material lacks the current activation gate, diagnostic-boundary/execution-mode contract, or inactive output boundary
- **THEN** consumer distribution parity fails rather than accepting older six-policy or fallback guidance

#### Scenario: Author policy survives in consumer projection
- **WHEN** a consumer prompt, generated AGENTS block, template, or installed skill still authorizes SkillGuard maintenance, contracts, receipts, or the former six-policy/Pareto path
- **THEN** suite distribution is blocked even if the maintainer-source skill is current

### Requirement: Managed skills declare V1 authority lifecycle
Every maintained FlowGuard V2 contract source SHALL declare whether former V1 author-runtime surfaces are migration evidence or formally retired. The maintainer-source projection SHALL preserve that decision, while the generated consumer distribution SHALL exclude all V1 and V2 SkillGuard control surfaces.

#### Scenario: V2 exists but retirement evidence is incomplete
- **WHEN** an author skill has a V2 contract trio and former V1 migration surfaces but lacks official calibration and retirement receipts
- **THEN** maintainer validation SHALL resolve it as `v2-migration`, V2 SHALL be the only author-runtime authority, and consumer distribution SHALL remain free of both forms

#### Scenario: Retired V1 author surface remains
- **WHEN** an author skill claims `v2-only` but a former V1 work contract, underscore check manifest, or V1 run record remains
- **THEN** maintainer runtime-authority validation SHALL block

#### Scenario: Consumer carries a contract surface
- **WHEN** any consumer FlowGuard skill contains V1 or V2 SkillGuard contract material
- **THEN** installed-layout validation SHALL block regardless of the author retirement state
