## Context

The package and project manifest report 0.53.1, while the managed `AGENTS.md` block still records 0.53.0. `project-audit` checks markers and package/manifest compatibility but does not compare the managed block with the current generator. The generator itself lacks newer BCL/PPA/path-sensitive rules, so running upgrade can remove valid policy. Separately, readiness discovery starts from directories that already contain `.skillguard/checks`, and the suite marker script hard-codes sixteen skills; the seventeenth skill, Behavior Commitment Ledger, is omitted precisely because its control root is absent.

This is the root change for the upgrade chain. Later changes consume its suite inventory and safe adoption checks.

## Goals / Non-Goals

**Goals:**

- Establish one machine-readable suite inventory for exactly one kernel and sixteen satellites.
- Reconcile inventory, actual `SKILL.md` directories, route metadata, and control-root presence in both directions.
- Make managed adoption text a generated semantic contract with dry-run, diff, and audit support.
- Prevent project upgrade from weakening or deleting newer rules.
- Produce stable JSON diagnostics and deterministic error codes for omissions, extras, duplicates, version mismatch, and semantic drift.

**Non-Goals:**

- Rewrite skill prompts or SkillGuard contracts.
- Resolve route topology or owner ambiguity.
- Implement evidence receipts, regression scheduling, installation, or publication.
- Archive historical OpenSpec changes.

## Decisions

### 1. Canonical suite inventory is explicit but validated against discovery

Add `.skillguard/flowguard-suite/suite-map.json` with schema version, suite id, kernel id, ordered member records, route role, expected entry files, and control-root expectation. Add `flowguard/skill_suite.py` to load it and discover every directory containing `SKILL.md` under the configured skill root. Validation is a set equality check plus uniqueness and required-file checks.

An explicit inventory is chosen over deriving membership only from existing controls because absence is a first-class failure. Discovery remains mandatory so the manifest cannot silently omit a new directory. Alternatives rejected: hard-coded Python lists and scanning `.skillguard/checks`.

### 2. Managed adoption text is compared semantically

Refactor `build_flowguard_agents_block()` into a data-driven template whose required clauses have stable rule ids. Audit normalizes line endings and insignificant whitespace, then compares rule ids and normalized text against the current generated block. It also compares package version, manifest version, and rendered adoption version.

Byte equality alone is rejected because formatting-only differences would create noise; marker-only checks are rejected because they miss policy loss.

### 3. Upgrade is preview-first

Add `--dry-run` to project-upgrade. Dry-run computes the proposed manifest, managed-block semantic diff, suite inventory findings, affected artifacts, and required revalidation without writing. A normal upgrade refuses to write if the proposed block would lose a required current rule or if the installed engine is older than the project record.

The CLI returns canonical JSON under `--json`; human output is a projection of the same result.

### 4. Legacy scripts become thin adapters

`scripts/verify_skill_suite_markers.py` and the suite portion of `scripts/verify_guard_simulation_readiness.py` call `flowguard.skill_suite` rather than maintaining independent inventories. Existing command names remain during this change, but their success is governed by the canonical result.

### 5. Adoption logs record the actual decision

Project audit/upgrade records inventory hash, generated-block semantic hash, versions, dry-run/write mode, findings, skipped steps, and next actions in the existing adoption logs. Logging does not substitute for validation.

## Risks / Trade-offs

- **[Risk] Existing local projects contain intentionally customized text inside the managed block.** → Treat the managed block as generated ownership; dry-run shows replacement and users must move custom text outside the markers.
- **[Risk] A strict inventory temporarily makes the current repository fail.** → Expected and intentional; the initial inventory lists all seventeen members and diagnostics identify missing controls without hiding them.
- **[Risk] Semantic normalization hides meaningful wording changes.** → Compare stable rule ids plus normalized content and maintain golden tests for the complete rule set.
- **[Risk] Other scripts still carry private lists.** → Add a repository search test that rejects suite member literals outside the canonical inventory and approved fixtures.

## Migration Plan

1. Add the canonical inventory and loader with positive and known-bad tests.
2. Update managed-block generation and golden semantics without running project-upgrade.
3. Add audit comparison and dry-run output; prove dry-run is non-mutating.
4. Convert legacy suite/readiness scripts to adapters.
5. Run dry-run against the repository and inspect the semantic diff.
6. Only after tests prove no rule loss, run the real upgrade and refresh adoption logs.

Rollback reverts this change as one unit. Do not restore parallel hard-coded membership lists.

## Open Questions

- None for implementation. The required suite cardinality is seventeen for this change; later additions must update the inventory and pass reverse discovery in the same commit.
