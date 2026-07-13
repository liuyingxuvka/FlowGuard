## Context

The distribution installer already treats its target as a mixed root: it
copies only the selected FlowGuard member trees, preserves unrelated skill
directories, and writes
`.flowguard-skill-suite-ownership.json` with the exact installed member ids
and owned files. In contrast, `validate_skill_suite()` currently interprets
every immediate `SKILL.md` directory as a FlowGuard member. Project adoption
loads that validator directly, so valid co-location becomes an upgrade blocker.

The canonical owner is `flowguard/skill_suite.py`; project adoption,
readiness scripts, and distribution validation should consume its result
instead of maintaining separate allowlists.

## Goals / Non-Goals

**Goals:**

- Preserve the hard requirement for exactly seventeen canonical FlowGuard
  members and their required control files.
- Recognize unrelated co-located skills only when an official distribution
  ownership manifest proves an intentional FlowGuard installation boundary.
- Keep undeclared FlowGuard-like skills visible as failures.
- Make report counts and JSON distinguish suite members from co-located skills.
- Keep pure-root and missing/invalid-manifest behavior backward compatible.

**Non-Goals:**

- Validate, install, or approve the unrelated skills.
- Turn arbitrary user configuration into a suite allowlist.
- Replace distribution parity or deep SkillGuard contract validation.
- Modify a target SkillGuard repository.

## Decisions

### Use the existing distribution ownership manifest as the scope authority

Mixed-root relaxation applies only when the skill root contains an official
ownership manifest with the supported schema, exactly the canonical declared
member ids, and owned `<member>/SKILL.md` rows for every declared member.
Without that evidence, reverse discovery remains strictly unchanged.

This reuses the installer-owned boundary and avoids a new project option or a
second target-local configuration file.

### Reserve FlowGuard-identifying skill ids

Even with valid ownership evidence, an undeclared id equal to `flowguard`,
beginning with `flowguard-`, or beginning with
`model-first-function-flow` remains an `extra_discovered_member`. These
names can plausibly claim FlowGuard membership and must not escape reverse
discovery.

Other unowned ids are classified as co-located skills. This classification
does not validate or endorse them.

### Project the report into suite members plus co-located skills

`discovered_member_ids` remains the discovered FlowGuard-suite surface.
Allowed foreign ids are returned through an additive
`co_located_skill_ids` field. Missing declared members and reserved
undeclared members stay in the suite member count and findings.

### Keep classification centralized

`project_adoption.py` continues to call `validate_skill_suite()` without a
special-case filter. CLI compatibility scripts therefore inherit the same
boundary and cannot drift.

## Risks / Trade-offs

- **A foreign skill uses a FlowGuard-reserved name** → It is intentionally
  blocked and must be renamed; safety wins over permissiveness.
- **A hand-written ownership manifest attempts to relax validation** → Exact
  member-id parity and owned `SKILL.md` rows are required, while missing
  canonical files and reserved fake members are still checked independently.
- **Consumers assumed discovered count meant every directory** → The new
  additive co-located field preserves full visibility with clearer semantics;
  previously mixed roots were blocked and had no passing contract.
- **The manifest is stale after a suite membership change** → Exact declared
  set comparison disables mixed-root relaxation and returns to strict failure.

## Migration Plan

No target edit is required. Re-run the official installer so the existing
ownership manifest is present, then rerun project audit or upgrade with the
updated FlowGuard package. Removing the code change restores prior strict
all-directory behavior.

## Open Questions

None for this bounded fix.
