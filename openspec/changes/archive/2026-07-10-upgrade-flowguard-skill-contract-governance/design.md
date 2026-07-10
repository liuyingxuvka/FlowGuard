## Context

The suite contains seventeen skill directories. Sixteen have legacy control roots whose contracts share a generic four-route shape and omit current SkillGuard depth fields; Behavior Commitment Ledger has no control root. Current installed-copy `check-skill` also reports missing standard entrypoint sections and layout-specific references. The kernel is already near its line budget, so appending boilerplate would make routing worse.

This change consumes the suite inventory and typed route ownership from the first two changes. It prepares the native contracts later consumed by evidence receipts.

## Goals / Non-Goals

**Goals:**

- Make all seventeen prompts statically clear, route-specific, compact, and layout-neutral.
- Make `SKILL.md`, `agents/openai.yaml`, route registry, and SkillGuard contract source agree.
- Generate current deep contracts deterministically for every skill.
- Preserve FlowGuard as the native execution owner and SkillGuard as its contract gate.
- Replace cloned shallow checks with shared, evidence-aware contract checks and skill-specific manifests.

**Non-Goals:**

- Create a second FlowGuard control plane inside SkillGuard.
- Implement runtime receipt storage or parent self-governance.
- Change route ownership decided by the topology change.
- Install or publish the finished suite.

## Decisions

### 1. Common information architecture, route-specific content

Every `SKILL.md` uses ten exact headings required by SkillGuard. The text under each heading is generated/curated from the skill's actual route role, inputs, native checks, evidence, blockers, handoffs, and claim boundary. Shared wording is limited to truly shared safety rules.

Detailed protocol inventories move into directly linked references. The kernel route table becomes a generated/checkable route index so the kernel target remains at or below 120 lines; satellites target at most 60 lines and 3000 characters unless an explicit test-backed exception is recorded.

### 2. Contract source is the editable semantic input

Each skill receives `.skillguard/contract-source.json` with target-specific source requirements, native route ids, phase bindings, workflow stages, native checks, acceptance obligations, skill-specific checks, test-gap plan, closure blockers, layout profiles, and non-parallel-route proof. A compiler writes `work-contract.json`, `check_manifest.json`, and contract hashes deterministically.

Generated files are never the primary edit surface. A check mode fails if regeneration would change tracked output.

### 3. Integration mode remains native-integrated

All seventeen contracts declare `native-integrated`, `run_record_required=false`, and explicit proof that SkillGuard invokes or inspects the FlowGuard-owned route rather than duplicating it. SkillGuard can block a claim but cannot manufacture FlowGuard evidence or run a parallel alternative workflow.

### 4. Prompt metadata is parity-checked

Add kernel `agents/openai.yaml`; align all satellite defaults. Each default prompt states precise trigger, route role, primary hard gate, non-owned work, required output fields, and claim boundary. Tests compare stable route ids and roles across YAML, `SKILL.md`, contract source, and registry.

### 5. Migrate in a pilot and four bounded batches

First convert one representative satellite and make static, contract, and depth checks pass. Then convert: process control; evidence/behavior; structure/ownership; UI. Shared checker changes land before bulk migration so failures are meaningful.

## Risks / Trade-offs

- **[Risk] Standard headings become empty boilerplate.** → Contract-source parity tests require target-specific route ids, obligations, and checks; duplicate semantic fingerprints across unrelated skills fail.
- **[Risk] Prompt compression removes essential safety detail.** → Move detail to direct references and test that every hard gate remains represented by an obligation.
- **[Risk] Generated JSON creates noisy diffs.** → Stable sorting, normalized newlines, and a single compiler version make output deterministic.
- **[Risk] Installed layout cannot resolve repository-relative links.** → Contract source declares source and installed layout profiles; checks resolve every direct reference in both temporary layouts.

## Migration Plan

1. Define contract-source schema, compiler, shared checks, and known-bad fixtures.
2. Convert one pilot skill and validate source plus temporary installed layout.
3. Add kernel metadata and refactor the kernel route index within budget.
4. Convert the remaining skills in four batches, running all three SkillGuard checks after each batch.
5. Remove cloned check implementations once all manifests use the shared checker.
6. Produce a 17/17 certification report; any hollow/risk/legacy result blocks completion.

Rollback is batch-granular. The compiler and shared checker may remain only if no skill is left with both old and new successful contracts.

## Open Questions

- None. Individual wording remains an implementation judgment, but the required headings, route parity, size budgets, and acceptance behavior are fixed.
