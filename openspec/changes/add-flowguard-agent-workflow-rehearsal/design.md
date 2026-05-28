## Context

FlowGuard already has peer satellite skills for specific evidence routes such
as DevelopmentProcessFlow, Model-Test Alignment, ModelMesh, TestMesh,
StructureMesh, UI flow, model-miss repair, architecture reduction, and existing
model preflight. Codex sessions can also expose many non-FlowGuard skills and
plugins on the same machine, such as OpenSpec, LogicGuard, document tools,
browser tools, GitHub, release helpers, and user-created skills.

The missing behavior is not another task executor. It is a portable rehearsal
gate that lets an AI agent inspect the skills available in the current
machine/session, declare the workflow it intends to use, and simulate whether
the sequence, skipped skills, validation plan, side effects, continue gates,
rework gates, and final confidence claim are coherent before execution.

## Goals / Non-Goals

**Goals:**
- Add `flowguard-agent-workflow-rehearsal` as a FlowGuard peer satellite skill
  that Codex can invoke directly.
- Take a fresh `SkillInventorySnapshot` at the start of every rehearsal
  invocation. Cached snapshots may be retained for comparison, but never count
  as current evidence.
- Rehearse a structured `AgentWorkflowPlan` against the current skill
  inventory and return `pass`, `needs_revision`, `scoped`, or `blocked`.
- Detect missing relevant skills, wrong ordering, unsupported skipped skills,
  weak/missing validation guidance, unsafe side effects, missing rework gates,
  stale/cached inventory use, and overbroad completion claims.
- Keep the implementation portable across machines by deriving available
  skills from the current session, repository `.agents/skills`, installed
  Codex skills, and plugin metadata when available.

**Non-Goals:**
- Do not auto-run the planned workflow or call every recommended skill.
- Do not install, delete, or update skills.
- Do not hardcode this developer machine's skill list as the expected inventory.
- Do not turn `model-first-function-flow` into a global skill orchestrator.
- Do not treat the rehearsal result as proof that downstream work is complete.

## Decisions

### One FlowGuard satellite, not two public layers

Add one directly invokable satellite named
`flowguard-agent-workflow-rehearsal`. FlowGuard owns the rehearsal model and
hard gates, but the inventory can include non-FlowGuard skills. This keeps the
user-facing mental model simple while preserving FlowGuard's evidence
discipline.

Alternative considered: a generic non-FlowGuard `agent-workflow-rehearsal`
skill plus a separate FlowGuard-specific rehearsal layer. That would be harder
for agents to trigger consistently and would split one user-facing rehearsal
decision into two public steps.

### Fresh snapshot on every invocation

Every call starts by building a lightweight current `SkillInventorySnapshot`.
The snapshot records skill name, description, trigger clues, source, side-effect
flags, validation/test guidance status, and whether deeper skill-body reading
is needed.

Alternative considered: cache snapshots and refresh only when skill files or
prompts change. That adds stale-cache reasoning before the rehearsal can even
start and is easier for AI agents to misuse.

### Progressive disclosure for skill bodies

The inventory pass reads metadata first. The reviewer only deep-reads full
`SKILL.md` bodies for candidate skills likely to affect the task. This keeps
the skill portable and context-efficient even on machines with many skills.

### Structured plan and explicit gates

The package helper reviews an `AgentWorkflowPlan`, not only raw prose. It
models selected skills, skipped candidate skills, ordered steps, side effects,
validation claims, continue gates, and rework gates. A plan that lacks a
rework gate for a meaningful validation failure is not equivalent to a safe
plan.

### Weak validation guidance becomes scoped or blocked

If a candidate skill has weak, missing, manual-only, or external-only
validation guidance, the rehearsal must require a compensating smoke test,
artifact check, manual check, dry run, or scoped completion claim. The existence
of a skill is not enough to support broad done/release confidence.

## Risks / Trade-offs

- [Risk] The skill could over-trigger for tiny tasks. → Mitigation: global
  prompt and model scenarios allow trivial read-only, formatting-only, direct
  command, and obvious single-skill tasks to skip with a reason.
- [Risk] The skill could become a universal executor. → Mitigation: the
  satellite only rehearses and reports; owning skills still execute their own
  workflows.
- [Risk] Inventory scanning could load too much context. → Mitigation:
  lightweight snapshot first, deep-read only candidate skills.
- [Risk] A machine exposes skill metadata differently. → Mitigation: model
  inventory source as data and allow partial inventories to produce scoped
  findings rather than hardcoded failures.
- [Risk] Prompt changes could claim behavior before installed skills are
  synchronized. → Mitigation: implement and validate repository skill first,
  then sync the installed skill, then update global prompt guidance.

## Migration Plan

1. Add OpenSpec specs, tasks, and executable model evidence.
2. Implement package helper and example model.
3. Add the Codex satellite skill and update repository prompt snippets.
4. Run focused model and skill docs tests.
5. Sync the skill into the local installed Codex skills directory.
6. Verify installed import/skill surfaces and shadow workspace behavior.
7. Only then update global guidance that makes Codex select the skill by
   default for non-trivial multi-skill planning.

Rollback is straightforward: remove the new satellite skill from routing
guidance and installed skills; the existing FlowGuard satellites remain
unchanged.

## Open Questions

- None for the first version. Automatic execution and long-term inventory
  caching are intentionally out of scope.
