## Context

FlowGuard v0.53.1 and earlier prompts carried concise route-specific diagram meanings. Commit `1797169` replaced the skill entrypoints with uniform compact shells and unintentionally removed those meanings, while the LogicGuard cross-Guard installed-skill test continued to enforce them. The current source and global installation are byte-identical, so the defect is in the canonical prompts rather than in installation drift.

## Goals / Non-Goals

**Goals:**

- Restore the previously owned diagram semantics in the six affected compact prompts.
- Keep the kernel and every satellite within existing hot-path budgets.
- Make FlowGuard itself detect another semantic deletion before downstream tests do.
- Refresh generated SkillGuard contracts and whole-suite installed parity after the final prompt bytes are stable.

**Non-Goals:**

- No generic diagram router, fixed chart selection table, or LogicGuard-to-FlowGuard semantic conversion.
- No runtime model, Python API, schema, route ownership, or package-version change.
- No partial copy of selected prompt files into installed or vendored suites.

## Decisions

1. **Restore semantics at their existing owners.** The kernel keeps the cross-Guard non-flattening gate. DevelopmentProcessFlow, UI Flow Structure, Model-Test Alignment, Code Structure Recommendation, and ModelMesh each state what their own edges mean. A central router was rejected because it would duplicate route ownership and encourage generic diagrams.
2. **Keep the prompt shells compact.** Route meanings remain one concise line in `Hard Gates` or `Output Requirements`; deeper examples stay in route references. Existing line and character budgets remain unchanged.
3. **Add source-owned regression coverage.** `tests/test_skill_docs.py` checks the exact semantic anchors in canonical source prompts. The existing LogicGuard test remains the cross-Guard installed-surface check and is not weakened.
4. **Regenerate deterministic contracts after prompt bytes settle.** Because `SKILL.md` is a compiler input, the six skills' generated `.skillguard` records must be refreshed with the official compiler and checked for deterministic parity.
5. **Synchronize whole suites, not individual files.** The official FlowGuard suite installer refreshes the global Codex installation and each downstream vendored `.agents/skills` tree; parity and project audit must follow. The suite map is unchanged.

## Risks / Trade-offs

- **Prompt budget regression** → Use the shortest historical semantic anchors and run the existing budget tests.
- **Generated contract churn** → Accept only deterministic changes attributable to the six prompt inputs and run compiler check after write.
- **Concurrent mixed-root work** → Do not edit `flowguard/skill_suite.py`, `tests/test_skill_suite_inventory.py`, `tests/test_project_adoption.py`, or the mixed-root OpenSpec change; re-read status before validation.
- **Source passes while active AI stays stale** → Treat global and downstream installed suites as unsynchronized until the official installer and parity checks run.
- **Full static SkillGuard depth certification is already blocked outside this change** → The current installed SkillGuard expects `skillguard.contract_source.v2` depth bindings while all seventeen canonical FlowGuard members still use the repository-owned `flowguard.skill_contract_source.v1` compiler contract. Keep that deep migration visibly not passed and out of scope; use current source tests, deterministic compiler parity, canonical suite marker validation, and whole-suite content parity only for this prompt-restoration claim.

## Migration Plan

The global Codex installation and these downstream vendored suites must consume the same whole-suite snapshot: LogicGuard, PhysicsGuard, SkillGuard, SourceGuard, TraceGuard, and worldguard. Each currently differs from canonical source in exactly twelve files: `SKILL.md` and `.skillguard/work-contract.json` for the six affected skills; there are no missing, extra, or conflicting files.

For each destination, use the official whole-suite path rather than copying those twelve files individually:

```text
python <flowguard-root>/scripts/install_flowguard_skills.py install --source <flowguard-root> --target <repo-root>/.agents/skills --json
python <flowguard-root>/scripts/install_flowguard_skills.py check --source <flowguard-root> --target <repo-root>/.agents/skills --json
python <flowguard-root>/scripts/verify_skill_suite_markers.py --root <repo-root> --json
python -m flowguard project-audit --root <repo-root> --json
```

The suite map, FlowGuard package version, schema version, and AGENTS managed block do not change. Rollback, if needed, is a whole-suite reinstall from the last accepted canonical FlowGuard source revision, followed by the same parity and project-audit checks.
