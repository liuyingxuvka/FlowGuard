## 1. Simulator Helper And API Surface

- [x] 1.1 Add a compact `development_process_simulator` helper module with request, mode decision, report, finding, and review objects.
- [x] 1.2 Export simulator helpers through `flowguard.__init__`, `FLOWGUARD_ROUTE_API`, and `ROUTE_STARTER_API` without removing existing PlanDetailing or AgentWorkflow helper APIs.
- [x] 1.3 Add focused unit tests proving rough-plan, multi-skill, execution, and combined requests select `flowguard-development-process-flow` with the correct internal mode order.

## 2. Route Model And Regression Tests

- [x] 2.1 Update `examples/flowguard_skill_trigger/model.py` to represent one selected skill plus `selected_mode`/mode sequence for development-process simulation.
- [x] 2.2 Add correct scenarios for rough plan, multi-skill workflow, execution freshness, and full plan-to-release chains entering `flowguard-development-process-flow`.
- [x] 2.3 Add broken scenarios proving old automatic first-entry routing to `flowguard-plan-detailing-compiler` or `flowguard-agent-workflow-rehearsal` is rejected.
- [x] 2.4 Update `tests/test_flowguard_skill_trigger.py` expectations for the expanded scenario catalog.

## 3. Prompt And Skill Topology

- [x] 3.1 Update `.agents/skills/flowguard-development-process-flow/SKILL.md` and its protocol reference to describe the single front-door simulator and three internal modes.
- [x] 3.2 Update `.agents/skills/flowguard-plan-detailing-compiler/SKILL.md` and reference guidance so generic automatic routing goes through the simulator while explicit/delegated use remains supported.
- [x] 3.3 Update `.agents/skills/flowguard-agent-workflow-rehearsal/SKILL.md` and reference guidance so generic automatic routing goes through the simulator while explicit/delegated use remains supported.
- [x] 3.4 Update installed OpenAI agent metadata for the three skills so trigger descriptions align with the new topology.

## 4. Docs, Specs, And Prompt Tests

- [x] 4.1 Update `docs/agents_snippet.md`, `AGENTS.md` managed guidance, `docs/productized_helpers.md`, and related API docs for the one-front-door route table.
- [x] 4.2 Update current specs or delta-backed docs that describe PlanDetailing and AgentWorkflowRehearsal as peer first entries.
- [x] 4.3 Update `tests/test_skill_docs.py`, `tests/test_api_surface.py`, and any public-template tests so old three-peer hot-path wording fails.

## 5. Version, Installation, And Workspace Sync

- [x] 5.1 Bump FlowGuard package/version metadata, project adoption record, changelog/release notes, and docs version references to `0.49.0`.
- [x] 5.2 Sync repository-managed skills to `<codex-skills-dir>` and verify content hashes for the touched skills.
- [x] 5.3 Refresh editable local install and verify installed package version, import path, and simulator helper imports.
- [x] 5.4 Sync the shadow workspace `<shadow-workspace>` as a whole source set for touched package, docs, examples, tests, OpenSpec, and skills.

## 6. Validation And Closure

- [x] 6.1 Run OpenSpec strict validation for this change and all changes.
- [x] 6.2 Run focused FlowGuard route checks and unit tests for simulator, route trigger, skill docs, API surface, public templates, PlanDetailing, AgentWorkflowRehearsal, and DevelopmentProcessFlow.
- [x] 6.3 Run practical broad tests or record any blocked/peer-owned validation boundary.
- [x] 6.4 Run project audit, record FlowGuard adoption evidence, and perform KB postflight.
- [x] 6.5 Commit the completed change to local Git with a `v0.49.0` tag if the commit can be scoped without capturing unrelated peer-agent work; otherwise report the exact git boundary and leave peer work untouched.
