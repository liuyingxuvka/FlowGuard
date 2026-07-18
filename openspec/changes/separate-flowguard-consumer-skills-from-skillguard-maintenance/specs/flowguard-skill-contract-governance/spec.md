## MODIFIED Requirements

### Requirement: Standard Skill Entrypoint Contract
Every FlowGuard consumer skill SHALL contain the exact entrypoint sections `Purpose`, `Entrypoint Scope`, `Local Material Routing`, `Entrypoint Acceptance Map`, `Use When`, `Do Not Use When`, `Required Workflow`, `Hard Gates`, and `Output Requirements`. The sections MUST state route-specific behavior rather than an interchangeable generic template and MUST NOT contain SkillGuard maintenance, runtime, contract, receipt, or router instructions.

#### Scenario: Required consumer section is absent
- **WHEN** any suite member omits one required consumer entrypoint section
- **THEN** static consumer skill validation fails for that member

#### Scenario: Author section is present
- **WHEN** any consumer member contains `SkillGuard Maintenance`, `SkillGuard Runtime Rules`, contract-trio instructions, receipt consumption, or router onboarding
- **THEN** static consumer skill validation and distribution activation fail

#### Scenario: Unrelated skills share a generic contract
- **WHEN** two unrelated skills expose identical route ids, workflow stages, obligations, and checks
- **THEN** depth validation fails with a generic-contract or parallel-route-risk finding

### Requirement: Target-Specific Contract Source
Every maintained FlowGuard skill SHALL own an author-side `.skillguard/contract-source.json` in the canonical maintainer source containing its source requirements, native route ids, phase bindings, workflow stages, native check bindings, acceptance obligations, skill-specific checks, test-gap plan, closure blockers, layout profiles, and non-parallel-route proof. The contract source and generated controls MUST NOT enter the consumer distribution.

#### Scenario: Maintainer source lacks a contract
- **WHEN** a maintained FlowGuard member has no author contract source or required maintainer control files
- **THEN** author-side suite certification fails as a missing-control-root blocker

#### Scenario: Native check binding is absent
- **WHEN** an author contract source declares an acceptance obligation without a native check or explicit test-gap disposition
- **THEN** author contract compilation fails and no release is certified

#### Scenario: Consumer contains contract source
- **WHEN** a staged or installed consumer member contains `.skillguard/contract-source.json` or generated SkillGuard controls
- **THEN** consumer installed-layout validation fails

### Requirement: Deterministic Deep Contract Generation
The author-side contract compiler SHALL deterministically generate the sole current SkillGuard compiled contract, check manifest, and contract hash from the consumer prompt projection, author contract source, route registry, and compiler schema. Check mode MUST fail when tracked author generated files are stale or manually altered. Generated controls SHALL remain in maintainer source and SHALL NOT be consumer files.

#### Scenario: Consumer prompt changes without author regeneration
- **WHEN** a consumer `SKILL.md` projection changes and the generated author contract hash still reflects the prior input
- **THEN** author contract check fails with a stale-generated-contract finding

#### Scenario: Compiler runs twice
- **WHEN** unchanged author inputs and consumer prompt projection are compiled twice
- **THEN** the generated author bytes and contract hash are identical

#### Scenario: Consumer install is inspected
- **WHEN** deterministic author generation has passed and the graduated skill is installed
- **THEN** the consumer tree contains no compiled SkillGuard contract or manifest

### Requirement: Native Integrated Ownership
Every FlowGuard author contract SHALL declare `native-integrated` and evidence that SkillGuard supervises the FlowGuard-owned route/check surface without creating a duplicate execution owner. Consumer domain work SHALL invoke only FlowGuard-owned routes and checks.

#### Scenario: Author contract declares a parallel execution path
- **WHEN** an author contract assigns SkillGuard ownership of a native FlowGuard workflow stage
- **THEN** depth validation fails with a parallel-route-risk finding

#### Scenario: Consumer invokes SkillGuard
- **WHEN** a consumer prompt or native FlowGuard runtime imports or invokes SkillGuard
- **THEN** consumer-independence validation fails

### Requirement: Seventeen Skill Deep Certification
Author release governance SHALL require static skill, contract, and depth validation to pass independently for all seventeen canonical suite members. Consumer readiness SHALL additionally require all seventeen clean consumer projections to pass with zero SkillGuard author-control findings.

#### Scenario: Sixteen author members pass and one is hollow
- **WHEN** sixteen author members pass but one member lacks required deep evidence
- **THEN** author certification fails and reports `16/17`, not a partial suite pass

#### Scenario: Author certification passes but one consumer is contaminated
- **WHEN** all author checks pass but one consumer member contains SkillGuard control material
- **THEN** distribution readiness fails and no partial consumer suite is activated
