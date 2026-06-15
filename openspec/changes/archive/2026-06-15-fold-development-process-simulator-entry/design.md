## Context

FlowGuard currently exposes three useful but overlapping AI-facing surfaces for
development-process work:

- `flowguard-plan-detailing-compiler` turns rough plans into explicit steps,
  artifacts, evidence gates, rework branches, and claim boundaries.
- `flowguard-agent-workflow-rehearsal` rehearses selected/skipped Codex
  skills, tools, side effects, continue gates, and final evidence claims.
- `flowguard-development-process-flow` tracks staged edits, validation
  freshness, install/shadow/git sync, and done/release/archive/publish claims.

They already share one conceptual model: stateful development simulation with
ordered actions, evidence, failure branches, rework, and final claim limits.
The user-facing problem is not missing capability. The problem is that Codex
sees three similar peer entries, so a planning conversation can use one route
and a later execution can forget the detailed obligations produced by the
earlier route.

There is also concurrent work in `harden-self-model-runners` that updates
self-owned `.flowguard/*/run_checks.py` evidence entry points. This change
intentionally avoids those runner files and focuses on Codex route topology,
prompt guidance, route tests, and a small package helper.

## Goals / Non-Goals

**Goals:**

- Make `flowguard-development-process-flow` the single AI-facing front door
  for development-process simulation.
- Preserve PlanDetailing and AgentWorkflowRehearsal as real helper protocols,
  data models, projections, tests, and explicit named-skill fallbacks.
- Add a small simulator helper that selects one or more internal modes:
  `plan_detailing`, `agent_workflow`, and `execution_freshness`.
- Update prompt surfaces so rough-plan discussion, multi-skill orchestration,
  staged implementation, validation, install/sync, and release/publish work
  enter the same front door before mode selection.
- Update route tests to reject the old auto-routing behavior where rough-plan
  or multi-skill tasks select the old direct satellites as the first entry.
- Keep the current direct satellite directories installed and discoverable so
  explicit user requests, deep reference loading, and backwards-compatible
  standalone use still work.

**Non-Goals:**

- Do not delete `flowguard-plan-detailing-compiler` or
  `flowguard-agent-workflow-rehearsal`.
- Do not merge their full protocol text into one giant `SKILL.md`.
- Do not make every FlowGuard route pass through the development simulator.
  UI Flow, Model-Test Alignment, TestMesh, ModelMesh, StructureMesh, Model
  Miss, and other specialist routes remain direct owners for their risks.
- Do not publish a GitHub Release in this change unless separately requested.

## Decisions

1. **Use DevelopmentProcessFlow as the front door.**
   - `flowguard-development-process-flow` already owns lifecycle ordering,
     evidence freshness, install/shadow/git sync, and release claims.
   - Upgrading it into the front door avoids adding a fourth competing skill.
   - Alternative considered: create `flowguard-development-simulator` as a new
     direct skill. Rejected because it would add another route name and repeat
     the same discoverability problem.

2. **Add a tiny simulator helper instead of a monolithic merger.**
   - New public helpers classify the request and mode sequence.
   - Existing PlanDetailing, AgentWorkflowRehearsal, and
     DevelopmentProcessFlow reviews continue to own detailed evidence.
   - Alternative considered: move all rows into `development_process_flow.py`.
     Rejected because it would increase blast radius and duplicate mature
     tests.

3. **Keep delegated satellites visible but no longer ordinary first choices.**
   - Their `SKILL.md` files should say they are internal/delegated modes for
     the simulator hot path and direct only when the user explicitly names the
     skill or a caller has already selected the mode.
   - This preserves standalone use outside the repo while fixing automatic
     Codex routing.

4. **Make tests enforce topology, not just wording.**
   - The skill trigger model should expose `selected_skill` and
     `selected_mode`.
   - Rough-plan and multi-skill tasks should select
     `flowguard-development-process-flow` with the relevant mode, not the old
     direct satellites.
   - Skill-doc tests should verify that AGENTS/snippet route maps contain the
     single front-door wording and that the delegated skill prompts no longer
     advertise themselves as ordinary first entries.

5. **Version as a user-visible minor behavior change.**
   - The change affects AI-facing behavior and installed skill routing, not only
     internals.
   - Target version: `0.49.0` unless validation reveals that a narrower patch
     version is safer.

## Risks / Trade-offs

- Prompt ambiguity may persist if only one surface is updated -> Update
  repository skills, installed skills, AGENTS snippet, OpenSpec specs, route
  tests, API docs, and shadow workspace together.
- Breaking explicit old-skill usage would be disruptive -> Preserve direct use
  when the user explicitly names PlanDetailing or AgentWorkflowRehearsal.
- Front-door helper could become another heavy route -> Keep it small: classify
  mode sequence and hand off; do not duplicate detailed route internals.
- Concurrent `harden-self-model-runners` changes touch adjacent files -> Avoid
  runner scripts and inspect git status before committing. If exact file
  overlap is unavoidable, preserve peer hunks and report any staged boundary.
- Release confidence can be overclaimed from installed-skill sync alone -> Run
  focused tests, OpenSpec validation, package import/version checks, project
  audit, installed skill hash checks, and shadow workspace import checks before
  claiming completion.

## Migration Plan

1. Add OpenSpec specs and tasks for the single front-door behavior.
2. Add the small simulator helper and export it through the public route API.
3. Update route-selection examples/tests to use one skill plus modes.
4. Update prompt surfaces and docs.
5. Run focused tests, route checks, OpenSpec validation, and project audit.
6. Bump to `0.49.0`, sync editable install, installed skills, and shadow
   workspace.
7. Commit only this change's scope where possible; preserve unrelated
   peer-agent work and clearly report any remaining dirty worktree boundary.

## Open Questions

- Whether to archive the completed OpenSpec change immediately after validation
  depends on the state of concurrent peer-agent changes. The safer default is
  to leave the change active but complete unless the repository is otherwise
  clean enough for archive.
