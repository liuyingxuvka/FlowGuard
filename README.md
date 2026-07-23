# FlowGuard

<!-- README HERO START -->
<p align="center">
  <img src="./assets/readme-hero/hero.png" alt="FlowGuard concept hero image" width="100%" />
</p>

<p align="center">
  <img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="120" />
</p>

<p align="center">
  <strong>An AI-agent skill suite powered by an executable check engine.</strong>
</p>
<!-- README HERO END -->

| Public release | Schema | Runtime | License |
| --- | --- | --- | --- |
| `v0.61.0` | `1.0` | Python standard library only | MIT |

English comes first. A Chinese mirror follows below.

## What FlowGuard Is

An AI-agent skill suite with executable check scripts, FlowGuard checks the risky part of a software change before an agent writes more code. The suite is powered by an executable check engine. In this author repository, its primary agent surface is `.agents/skills/`: start with `.agents/skills/flowguard/SKILL.md`, then use its sibling `SKILL.md` files, references, assets, and check scripts to select the right route. An ordinary target project uses the single clean consumer projection under `$CODEX_HOME/skills/`; it does not vendor a second local FlowGuard suite or suite map. The installed package ships one deterministic clean-consumer authority, and project audit or upgrade compares that authority directly with the global projection and its ownership manifest.

It asks the agent to turn the danger zone into a finite state model, run that model, and inspect counterexample traces. That makes problems such as duplicate side effects, stale test evidence, broken UI recovery paths, or unsupported "done" claims visible before they become maintenance debt.

It does not call an LLM API. It is not a prompt trick. It is not a replacement for tests. It is a model-first preflight layer for work where order, state, retries, side effects, UI paths, validation evidence, or release confidence matter. The executable Python code is the check-script engine used by the skills; it is not the skill installation itself.

## The Problem

AI coding agents are good at local edits. That is useful, but it creates a common failure mode: the nearby code looks fixed while the whole workflow is already wrong.

For example:

1. You ask an agent to fix retry handling.
2. The agent changes the function near the bug.
3. The visible test passes.
4. The same job is processed again later.
5. A side effect happens twice because the workflow never modeled the repeated input.

FlowGuard is built for that kind of problem. Instead of telling the agent to "be careful", it asks the agent to name the state, inputs, outputs, side effects, owners, and evidence gates that decide whether the next step is safe.

## How It Works

The core shape is:

```text
Input x State -> Set(Output x State)
```

In plain language:

- `Input` is the event coming in, such as a job, retry, UI click, file payload, or release action.
- `State` is what the system remembers before the event.
- `Output` is what the step says happened.
- The new `State` is what the system remembers after the step.
- `Set(...)` means one input may have several legal branches, and the model must say what they are.

When that finite meaning must cross a process, tool, or repository boundary,
FlowGuard can project it into the current `flowguard.portable_model.v1` JSON
IR. The portable checker validates the exact schema and content identity,
executes the explicit nondeterministic transition relation, checks safety and
temporal obligations, and verifies explicit parent/child refinement plus
assume/guarantee composition. It does not serialize arbitrary Python or act as
an application's database, UI, deletion, people, relationship, or project
workflow layer.

```powershell
python -m flowguard portable-model-validate path/to/model.json --json
python -m flowguard portable-model-check path/to/model.json --json
python -m flowguard portable-model-refinement --parent parent.json --child child.json --binding binding.json --json
python -m flowguard portable-system-check --system system.json --request request.json --component component-a.json --component component-b.json --json
```

For a declared finite subsystem, `flowguard.portable_system.v1` keeps the
system definition, the verification request, and the exact derived slice as
three distinct identities. The system checker validates every referenced
component, compiles the declared dependency/step graph into one bounded joint
model, and makes at most one canonical system-level checker invocation. A
counterexample is mapped back to component transitions and optional code
targets. Missing, stale, or omitted dependencies, clean truncation, and
truncated temporal claims block rather than being reported as passes. This is
evidence about the declared bounded slice only; it does not discover unknown
components or prove arbitrary software outside that slice.

The practical loop is:

```text
risky AI action
-> small executable model
-> invariants, scenarios, and freshness checks
-> counterexample trace
-> revise the plan, code, tests, UI, or claim
```

The important output is often the counterexample: a concrete sequence of states that shows why the current plan should not continue unchanged.

## What It Helps Catch

| Situation | What can go wrong | What FlowGuard makes visible |
| --- | --- | --- |
| Retry or repeated job processing | the same input creates a second side effect | a repeated-input trace and an idempotency invariant |
| Cache or refresh logic | old state is reused after it should be invalid | state fields and freshness rules that need to change |
| UI workflows | buttons exist, but the user cannot recover, cancel, or reach a terminal state | launch-to-terminal journeys, visible controls, disabled reasons, and recovery paths |
| UI product language | each page uses different title sizes, controls, navigation, feedback, or recovery for the same job | one product-scope UI Flow Structure comparison across typography, components, navigation, interaction, feedback, recovery, and transitions |
| Repeated functional paths | downloading or submitting the same kind of result quietly grows a different handler per page, API, command, alias, or wrapper | one stable exact intent, one active behavior commitment, one selected current path, and evidence that extra surfaces delegate |
| Refactors | a new module split loses the real state or side-effect owner | facade boundaries, state owners, side-effect owners, and parity evidence |
| Tests and releases | an old passing test is treated as proof after code, docs, models, or fixtures changed | evidence freshness and minimum revalidation requirements |
| Feature or behavior inventory | AI fixes one local path while missing, duplicating, or inventing external behavior | a Behavior Commitment Ledger: source surfaces, commitments, one primary owner model, dependencies, evidence, and PPA handoff for path-sensitive behavior |
| Model-code-test binding | a model, a code contract, and a test all exist, but they do not prove the same behavior | binding rows that connect obligations, owner code, source audit, runtime evidence, bad-case replay, and open gaps |
| Parent and child models | one local green check is treated as whole-system confidence | child evidence, parent reattachment, sibling impact, and scoped confidence |
| Public claims | a README, release note, or "done" message says more than current evidence supports | the claim boundary and the missing proof |

FlowGuard can help design the workflow before code exists, and it can help check whether later evidence still supports a claim. The claim is always bounded: a FlowGuard pass means the declared model obligations passed. It does not mean the entire production system is correct.

## Quick Start

Clone or open the repository, then make the FlowGuard skills visible to your AI agent:

```powershell
git clone https://github.com/liuyingxuvka/FlowGuard.git
cd FlowGuard
```

For AI agents, complete setup means:

1. Read `AGENTS.md`.
2. Load or copy every skill under `.agents/skills/` according to the host agent's skill mechanism.
3. Start from `.agents/skills/flowguard/SKILL.md`.
4. Keep the sibling FlowGuard skills available so the kernel can route to them.
5. Run executable check scripts only when current evidence is needed.

Run a small check script that compares a correct model with broken variants:

```powershell
python examples/job_matching/run_checks.py
```

The example should report:

- the correct model is `OK`;
- the broken duplicate-record model has invariant violations;
- the broken repeated-scoring model has invariant violations;
- the report includes counterexample traces showing the repeated input path.

That example is intentionally abstract. It does not search real jobs or call an AI model. It exists to show the FlowGuard pattern: repeated inputs, state writes, invariants, and counterexamples.

If you need command-line project records or template generation, run `python -m flowguard ...` from the repository. The command executes checks and helpers; it is not the AI-agent skill install.

## Use It In Another Project

For a target project, first make the FlowGuard skill suite available to the AI agent that will work there. The agent needs `AGENTS.md` plus every FlowGuard `SKILL.md` under `.agents/skills/`.

Then, when executable project records are useful, run the current project commands:

```powershell
python -m flowguard project-adopt --root <target-project>
python -m flowguard project-audit --root <target-project>
python -m flowguard project-upgrade --root <target-project>
```

Then start small:

```text
choose one risky boundary
-> name the error class you want to prevent
-> describe Input, State, Output, side effects, owners, and completion evidence
-> add one invariant or scenario
-> add one known-bad case
-> run the check
-> inspect the counterexample
-> revise the plan, code, tests, UI, or claim
```

Escalate only when the risk needs it. A retry bug may need a small model. A release claim, UI flow, refactor split, or parent/child model chain may need a stronger route.

For broad feature, release, UI/API/CLI, skill, workflow, or project-confidence
claims, start with the Behavior Commitment Ledger. It registers external
behavior promises, maps them to source surfaces, assigns exactly one primary
owner model, and sends `path_sensitive=true` rows to Primary Path Authority so
the work does not accumulate hidden fallback paths.

Surface shape is not behavior identity. When a page control, API, CLI, alias,
adapter, wrapper, or compatibility facade has the same actor, preconditions,
terminal result, failure boundary, material state writes, and side effects, it
maps to the same stable business intent and active commitment. Primary Path
Authority keeps one current selected path, while extra surfaces delegate. UI
Flow Structure then checks that repeated pages use one semantic typography and
interaction language without exposing the internal intent, commitment, path,
audit, or evidence ids to ordinary users. Content admission remains exactly
`user_visible`, `user_on_demand`, or `internal`.

Behavior ownership is a separate question from UI visibility and from
`commitment_kind`. Every registered production commitment belongs to exactly
one execution plane:

- `product_runtime`: what the application promises to users or external systems;
- `agent_operation`: how the current AI agent operates tools to complete work;
- `development_process`: how development, validation, installation, archive,
  publish, and release work is governed.

Existing Model Preflight queries the requested plane first, then shows typed
related-plane context separately. A product target can be invoked or validated
by an AI action without transferring ownership to that action. The lookup is a
small, explainable recall aid; it does not force every ordinary action to run a
model and cannot guarantee that a future AI will obey the retrieved guidance.
Inspect a decision with the existing BCL/preflight-owned read-only command:

```powershell
python -m flowguard behavior-commitment-query "start the UI test and check the port bridge" --root . --plane agent_operation --term port_bridge --json
```

## Minimal Model Sketch

The full runnable version is in [`examples/job_matching`](./examples/job_matching). The idea is small:

```python
@dataclass(frozen=True)
class State:
    processed: tuple[str, ...] = ()
    side_effects: int = 0


@dataclass(frozen=True)
class Input:
    job_id: str


class ProcessJob:
    accepted_input_type = Input
    reads = ("processed", "side_effects")
    writes = ("processed", "side_effects")

    def apply(self, input_obj: Input, state: State):
        if input_obj.job_id in state.processed:
            return [FunctionResult("already_processed", state, label="deduplicated_retry")]
        return [
            FunctionResult(
                "processed",
                replace(
                    state,
                    processed=state.processed + (input_obj.job_id,),
                    side_effects=state.side_effects + 1,
                ),
                label="first_processing",
            )
        ]
```

The model is useful only when it also includes a bad case and a rule worth checking, such as "the same job may not create duplicate side effects."

## When To Use It

Use FlowGuard when the next action depends on workflow state, not just on local code text.

Good fits:

- AI-agent coding work with multiple stages, handoffs, or validation gates;
- retries, deduplication, cache refresh, queues, ingestion, and repeated jobs;
- UI flows where visible controls do not prove recovery paths or internal
  status/audit/diagnostic content has reached the ordinary user surface;
- refactors where public entrypoints and side effects must stay compatible;
- test or release processes where old evidence can be mistaken for current proof;
- parent/child model chains where local evidence must be reattached before broad confidence.

Bad fits:

- one-line typo fixes;
- formatting-only changes;
- tasks with no meaningful state, side effect, order, or evidence boundary;
- claims that need statistical truth, business truth, or production telemetry rather than structural workflow checks.

## Advanced Agent Workflows

You can skip this section if you are only trying the first example.

FlowGuard has one model-first kernel and route-specific skills. These are the skills an AI agent should load as the FlowGuard suite:

<!-- FLOWGUARD SKILL TABLE EN START -->
| Skill | Use it when |
| --- | --- |
| `flowguard` | ordinary behavior or state modeling is enough, or several FlowGuard routes need coordination |
| `flowguard-existing-model-preflight` | an existing modeled system should be checked before adding a new boundary |
| `flowguard-development-process-flow` | staged work, multi-skill setup, evidence freshness, or several outcome-equivalent routes need a lower-rework process choice; it owns internal `plan_detailing_compiler` and `agent_workflow_rehearsal` routes |
| `flowguard-behavior-commitment-ledger` | broad behavior promises need source coverage, one primary owner model, and Primary Path Authority handoff for path-sensitive behavior |
| `flowguard-field-lifecycle-mesh` | fields, schemas, modes, prompt/config keys, old-field disposition, or UI-boundary candidate-field handoff need ownership |
| `flowguard-contract-exhaustion-mesh` | finite bad-case generation, same-class families, payloads, or transition cases need canonical coverage |
| `flowguard-ui-flow-structure` | UI candidate content admission, controls, visible surface, on-demand details, journeys, recovery, and implementation evidence need modeling |
| `flowguard-code-structure-recommendation` | a functional model should drive module, facade, owner, side-effect, config, or validation boundaries |
| `flowguard-structure-mesh` | a large script, package, command, or public API split needs compatibility and parity evidence |
| `flowguard-test-mesh` | validation is slow, layered, stale, skipped, release-only, or split across child suites |
| `flowguard-model-test-alignment` | model obligations, code contracts, and test evidence need direct comparison |
| `flowguard-model-mesh` | parent/child model evidence, sibling impact, or oversized model surfaces need mesh governance |
| `flowguard-model-topology-hazard-review` | a locally green model may still imply future-use hazards |
| `flowguard-architecture-reduction` | duplicated handlers, adapters, modules, branches, or validation layers may be contracted without changing behavior |
| `flowguard-model-miss-review` | runtime, tests, replay, logs, or manual checks failed after a FlowGuard model passed |
<!-- FLOWGUARD SKILL TABLE EN END -->

Process optimization is conditional, not a mandatory six-way strategy menu. When it is useful, FlowGuard first proves that candidate routes preserve the same outcome, evidence, safety, side effects, dependencies, and execution ownership; it then chooses a diagnostic boundary and sequential or isolation-proven parallel execution. This can support collecting enough related failures before one root-cause repair, but hard blockers still stop invalid downstream work and every affected obligation is revalidated.

The table is parity-checked against `.skillguard/flowguard-suite/suite-map.json`; a missing or extra route fails the documentation test.

### Current, Target, And Experiment Models

FlowGuard now keeps three different things separate:

- the **observed implementation model** describes the software that actually
  exists now;
- a **normative target model** describes a proposed replacement;
- a **counterfactual experiment model** explores an alternative without
  changing what counts as current.

Names such as `current`, a prompt statement, a file discovery hit, or a passing
candidate check do not grant authority. One content-addressed project snapshot,
selected by the single head in `.flowguard/project.toml`, is the observed
authority. Its finite coverage inventory joins model instances, behavior
commitments, external surfaces, fields/state/effects, code contracts, and
tests/evidence. Missing authority or unresolved required coverage blocks broad
current-model claims.

A target or experiment replaces the observed system only as one accepted
`ModelRevisionSet`: the exact base, candidate, changed relations, affected
sibling closure, prediction/replay evidence, and current owner receipts must
match. Immutable records are written first and the single pointer is changed
last under a shared compare-and-swap lock. Rollback restores or compensates
real implementation effects and revalidates the old snapshot before moving the
pointer; irreversible effects require forward repair.

```powershell
python -m flowguard model-system-bootstrap --root . --snapshot-id <id> --evidence-fingerprint <sha256>
python -m flowguard model-system-audit --root . --json
python -m flowguard model-revision-activate --root . --candidate-snapshot <snapshot.json> --revision-set <revision.json> --receipt-id <id>
python -m flowguard model-revision-rollback --root . --contract <rollback.json> --completed-evidence-fingerprint <sha256> --result exact --receipt-id <id> --reason <reason>
```

These commands extend the existing model, preflight, ModelMesh, commitment,
field-lifecycle, test, and development-process routes. They do not introduce a
second product workflow or make OpenSpec part of FlowGuard.

For ordinary UI, FlowGuard uses two conceptual groups and three executable
values: `user_visible` and `user_on_demand` are user content; `internal` is not.
Unclassified/internal content cannot render. On-demand content is hidden by
default across every mapping target and needs visible/enabled reveal and return
controls, content-specific feedback, and a distinct keyboard/focus event for
hover. User needs use typed task/state/recovery/safety references. Observing
content in an existing UI does not grant permission to keep it. Only the exact
normal label of a registered, in-scope task-owned control with no extra state or
metadata avoids a duplicate row. Runnable claims use an observed inventory and
structured per-content evidence. This model does not introduce audience/role/
persona or admin/operator/developer/auditor classes.

### Three Evidence Layers

FlowGuard deliberately keeps three different meanings of “green” separate:

All fifteen bundled skills use `skillguard.contract_source.v2`, belong to the
single `unit:flowguard-suite` author maintenance unit, and bind existing
FlowGuard-owned routes and checks. Contract compilation proves deterministic
prompt/model/check mapping; it is not an execution-depth receipt and does not
create a SkillGuard-owned domain route.

| Layer | What passed | What it does not prove |
| --- | --- | --- |
| Prompt and contract structure | the skill prompt, generated contract, references, and SkillGuard static/depth rules agree | the route's executable check did not necessarily run |
| Native evidence receipt | the route-owned command ran against declared current inputs and produced a terminal, freshness-verifiable receipt | one route receipt does not close the other fourteen public skills or the parent claim |
| Self-governance parent closure | the parent consumed current exact-pass receipts for all required members and checked inventory, freshness, and distribution boundaries | it still proves only the declared suite obligations, not future AI behavior or production correctness |

If a prompt, contract, native checker, model, test, or covered input changes, older evidence may become stale. A previous pass is not silently carried forward.

### Validation And Distribution

Model regressions use an explicit manifest and three tiers: `fast` for narrow development feedback, `focused` for a wider selected surface, and `full` for every required non-excluded model. Only a current, terminal full-tier pass can contribute to a release claim.

For normal use, the package exposes one simulator front door. It audits the
same manifest and delegates each selected id to that model's own native runner;
it does not merge domain models or reinterpret their results:

```powershell
python -m flowguard simulator --root . --list
python -m flowguard simulator --root . --model architecture_reduction
python -m flowguard simulator --root . --model "ui_*" --tier focused --json
python -m flowguard simulator --root . --all --tier full --jobs 1 --timeout 900
```

The checked-in `.flowguard/**/model.py` and native `run_checks.py` files are
executable model source. `.flowguard/evidence/`, extra local worktrees,
`build/`, `dist/`, caches, and release receipts are generated or environment
state; their size is not the model size and none of them is part of the clean
installed AI-agent skill projection.

```powershell
python scripts/run_flowguard_model_regressions.py --audit-only --json
python scripts/run_flowguard_model_regressions.py --tier fast --output-dir .flowguard/evidence/model-regressions/fast-local
python scripts/run_flowguard_model_regressions.py --tier focused --model "ui_*" --shard 1/2 --jobs 1 --output-dir .flowguard/evidence/model-regressions/focused-1 --json
python scripts/run_flowguard_model_regressions.py --tier full --jobs 1 --timeout 900 --output-dir .flowguard/evidence/model-regressions/full-local --full
```

Default human output is concise. `--json` emits the canonical machine result, while `--full` expands human-readable child details; neither option upgrades the evidence scope. Complete stdout/stderr are retained once as deterministic gzip objects with logical and storage hashes. Child and parent JSON keep bounded diagnostics and references rather than nested full payload copies. During a long foreground or background run, progress events show liveness only. Completion requires the final `report.json`, `evidence-run.json`, current-head binding, and terminal child receipts in the selected output directory.

Persistent evidence cleanup is always explicit:

```powershell
python -m flowguard evidence-audit --root .flowguard/evidence --json
python -m flowguard evidence-gc-plan --root .flowguard/evidence --keep 2 --preserve skill-suite --output .flowguard/evidence-gc-plan.json --json
python -m flowguard evidence-gc-apply --root .flowguard/evidence --plan .flowguard/evidence-gc-plan.json --json
python -m flowguard evidence-gc-restore --root .flowguard/evidence --quarantine-id <id> --json
python -m flowguard evidence-gc-purge --root .flowguard/evidence --quarantine-id <id> --json
```

Audit and planning do not modify evidence. Apply revalidates the frozen plan
and moves only unreachable runs into quarantine. Restore is available before
purge; purge accepts only one exact quarantine after current and pinned runs
still validate. Store plans outside the retained evidence root, repeat
`--preserve` for exact externally bound legacy roots, and require zero
unclassified bytes before cleanup. Ordinary validation never invokes
persistent cleanup.

The skill installer manages the complete 15-member tree and records which files it owns:

```powershell
python scripts/install_flowguard_skills.py install --source . --codex-home $env:CODEX_HOME --dry-run --json
python scripts/install_flowguard_skills.py install --source . --codex-home $env:CODEX_HOME --json
python scripts/install_flowguard_skills.py check --source . --codex-home $env:CODEX_HOME --json
python scripts/install_flowguard_skills.py parity --source . --formal .agents/skills --shadow $env:FLOWGUARD_SHADOW\.agents\skills --installed $env:CODEX_HOME\skills --json
python scripts/install_flowguard_skills.py uninstall --codex-home $env:CODEX_HOME --dry-run --json
python scripts/install_flowguard_skills.py uninstall --codex-home $env:CODEX_HOME --json
```

`check` and `parity` are read-only, so they do not accept `--dry-run`. Uninstall removes only unchanged installer-owned files and preserves modified or unowned files as conflicts. Current receipts live under `.flowguard/evidence/skill-suite`; model-run artifacts live in the chosen regression `--output-dir`. Environment-local receipts are explicitly excluded from the distributed skill tree and must be regenerated where claims are made.

See [`docs/validation_and_distribution.md`](./docs/validation_and_distribution.md) for the command contract, exit/status meanings, background-monitoring boundary, evidence locations, and safe install lifecycle.

Useful check and template commands:

```powershell
python -m flowguard project-template
python -m flowguard risk-intent-template
python -m flowguard risk-template-library-template
python -m flowguard development-process-flow-template
python -m flowguard ui-flow-structure-template
python -m flowguard code-structure-recommendation-template
python -m flowguard model-test-alignment-template
python -m flowguard test-mesh-template
python -m flowguard structure-mesh-template
python -m flowguard closure-contract-template
python -m flowguard topology-hazard-template
python -m flowguard risk-template-search "completion evidence"
```

Run `python -m flowguard --help` for the full current command list.

FlowGuard v0.61.0 is source-only: the immutable Git tag is the release
authority. A release must not contain a wheel, source distribution, or GitHub
Release asset.

## Relationship To The Guard Family

| Project | Focus |
| --- | --- |
| FlowGuard | stateful behavior, process flow, evidence freshness, parent/child model confidence |
| LogicGuard | claims, evidence, warrants, assumptions, rebuttals, scope, and overclaiming in written reasoning |
| PhysicsGuard | low-fidelity residual checks and model-building blueprints for physical simulation debugging |
| FlowPilot | long-running project orchestration and route control for AI-agent software work |

## Documentation Map

| File | Purpose |
| --- | --- |
| [`docs/concept.md`](./docs/concept.md) | short conceptual introduction |
| [`docs/modeling_protocol.md`](./docs/modeling_protocol.md) | core model-first protocol |
| [`docs/api_surface.md`](./docs/api_surface.md) | public Python API overview |
| [`docs/invariant_examples.md`](./docs/invariant_examples.md) | examples of useful invariants |
| [`docs/development_process_flow.md`](./docs/development_process_flow.md) | staged development, validation freshness, archive, publish, and release gates |
| [`docs/ui_flow_structure.md`](./docs/ui_flow_structure.md) | UI interaction and structure modeling |
| [`docs/code_structure_recommendation.md`](./docs/code_structure_recommendation.md) | model-derived code structure recommendations |
| [`docs/structure_mesh.md`](./docs/structure_mesh.md) | refactor and module split governance |
| [`docs/test_evidence_mesh.md`](./docs/test_evidence_mesh.md) | layered validation and evidence freshness |
| [`docs/model_test_alignment.md`](./docs/model_test_alignment.md) | model obligation and test evidence alignment |
| [`docs/model_mesh_protocol.md`](./docs/model_mesh_protocol.md) | parent/child model mesh governance |
| [`docs/model_topology_hazard_review.md`](./docs/model_topology_hazard_review.md) | topology-grounded future-use hazard review |
| [`docs/model_similarity_consolidation.md`](./docs/model_similarity_consolidation.md) | model-to-model relation review and consolidation handoffs |
| [`docs/flowguard_closure_contract.md`](./docs/flowguard_closure_contract.md) | closure contract for complete FlowGuard use |
| [`docs/risk_evidence_ledger.md`](./docs/risk_evidence_ledger.md) | risk-to-model-to-code-to-evidence confidence boundary |
| [`docs/runtime_gateway_adoption.md`](./docs/runtime_gateway_adoption.md) | runtime gateway adoption levels and critical-state writer inventory |
| [`docs/validation_and_distribution.md`](./docs/validation_and_distribution.md) | tiered validation, evidence layers, background progress, and skill distribution lifecycle |

## Repository Layout

```text
flowguard/     Core library, review helpers, templates, mesh routes, CLI
examples/      Small executable models and public self-reviews
docs/          Protocols, API notes, examples, and adoption guidance
tests/         Focused regression tests for public helpers
assets/        README hero image and generation notes
```

## Public Boundary

This repository is a public starter and reference implementation. It includes the FlowGuard skill suite, executable check scripts/check engine code, examples, protocol docs, public templates, and AI-agent skill material, including Codex-compatible skills.

It does not include private project logs, credentials, customer data, or a claim that every real system is fully covered. FlowGuard checks the model and evidence you declare. Real software still needs tests, code review, UI review, production-facing validation, and human judgment where those are relevant.

## License

MIT. See [`LICENSE`](./LICENSE).

---

## 中文说明

FlowGuard 是一套由可执行检查引擎驱动的 AI-agent 技能套件，同时附带可执行检查脚本。它的主要 agent surface 是 `.agents/skills/`：里面的 `SKILL.md`、references、assets 和检查脚本会告诉 AI 什么时候该用 FlowGuard、该走哪个子技能、怎么拿到当前证据。

它的核心不是让 agent “小心一点”，而是让 agent 把危险路径写成一个小型可执行状态模型。模型跑起来以后，可以提前暴露重复副作用、过期证据、缺失恢复路径、或者 `done` / `release` 声明已经不成立这类问题。

FlowGuard 不调用 LLM API，不是 prompt trick，也不是普通测试的替代品。它更像一个结构化预检层：当顺序、状态、重试、副作用、UI 路径、验证证据或发布信心会影响结果时，先把这些关系说清楚、跑一遍、看反例。仓库里的 Python 代码是技能使用的检查脚本/检查引擎，不是 AI-agent 技能安装本身。

## 为什么需要它

AI 编程 agent 很擅长局部修改。问题是，局部代码看起来修好了，不代表整个 workflow 真的安全。

一个常见例子：

1. 你让 agent 修 retry 逻辑。
2. agent 改了 bug 附近的函数。
3. 眼前的测试通过了。
4. 后面同一个 job 又被处理了一次。
5. 因为 workflow 没有建模重复输入，某个副作用又发生了一次。

FlowGuard 就是为这种情况设计的。它要求 agent 在动手前说清楚：输入是什么，系统现在记住了什么，这一步会输出什么，会改哪些状态，会产生什么副作用，谁拥有这个边界，哪些证据才算当前有效。

## 它怎么工作

核心模型是：

```text
Input x State -> Set(Output x State)
```

翻成人话：

- `Input` 是进来的事件，比如一个 job、一次 retry、一次 UI 点击、一个文件 payload 或一次 release 动作。
- `State` 是系统在这一步之前记住的东西。
- `Output` 是这一步说自己做了什么。
- 新的 `State` 是这一步之后系统记住的东西。
- `Set(...)` 表示同一个输入可能有多个合法分支，不能只写 happy path。

当这套有限状态语义需要跨进程、工具或仓库传递时，FlowGuard 可以把它
投影成当前唯一的 `flowguard.portable_model.v1` JSON IR。便携检查器会校验
严格 schema 与内容身份、执行显式的非确定性 transition、检查 safety 与
temporal obligation，并通过显式映射检查 parent/child refinement 和
assume/guarantee composition。它不会序列化任意 Python，也不承担未来软件的
数据库、UI、删除、人员关系或项目事务功能。

```powershell
python -m flowguard portable-model-validate path/to/model.json --json
python -m flowguard portable-model-check path/to/model.json --json
python -m flowguard portable-model-refinement --parent parent.json --child child.json --binding binding.json --json
python -m flowguard portable-system-check --system system.json --request request.json --component component-a.json --component component-b.json --json
```

对于一个明确声明的有限子系统，`flowguard.portable_system.v1` 会把系统定义、
验证请求和精确推导出的系统切片保留为三个不同身份。系统检查器先验证所有被
引用的组件，再把声明的依赖与步骤图编译为一个有界联合模型，系统级规范检查
最多调用一次。若出现反例，会映射回组件迁移和可选代码位置。依赖缺失、过期或
被遗漏，以及没有发现错误但探索被截断、时间性质被截断，都会报告为阻塞，而
不是通过。这份证据只覆盖声明的有界切片，不会自动发现未知组件，也不证明切片
之外的任意软件。

实际工作循环是：

```text
危险 AI 行动
-> 小型可执行模型
-> invariant、scenario 和证据新鲜度检查
-> counterexample trace
-> 修改计划、代码、测试、UI 或声明
```

最有价值的结果通常是 counterexample：一条具体的状态序列，告诉你为什么当前计划不能原样继续。

## 它能帮你抓什么问题

| 场景 | 可能坏在哪里 | FlowGuard 让什么变清楚 |
| --- | --- | --- |
| retry 或重复 job | 同一个输入产生第二次副作用 | 重复输入 trace 和幂等 invariant |
| cache 或 refresh | 旧状态在应该失效后仍被使用 | 哪些 state 字段和 freshness 规则需要改变 |
| UI workflow | 按钮存在，但用户不能恢复、取消或到达终态 | 从启动到终态的 journey、可见控件、禁用原因和恢复路径 |
| refactor | 新模块拆分后，真实 state owner 或 side-effect owner 丢失 | facade 边界、state owner、side-effect owner 和 parity evidence |
| 测试和发布 | 旧测试通过被误当作当前证明 | evidence freshness 和最低 revalidation 要求 |
| 模型-代码-测试绑定 | 模型、代码契约、测试都存在，但没有证明同一个行为 | binding row 把 obligation、owner code、source audit、runtime evidence、坏例 replay 和 open gap 连成一行 |
| 父子模型 | 一个局部 green 被误当作整体可信 | child evidence、parent reattachment、sibling impact 和 scoped confidence |
| 公开声明 | README、release note 或 done 说得比证据更多 | claim boundary 和缺失 proof |

FlowGuard 可以在代码还没写之前帮助设计 workflow，也可以在后面检查证据是否还能支持当前声明。但它的结论永远有边界：FlowGuard 通过，只表示你声明的模型义务通过，不表示整个生产系统已经正确。

## 快速开始

克隆或打开仓库，然后先让 AI agent 能看到 FlowGuard 技能：

```powershell
git clone https://github.com/liuyingxuvka/FlowGuard.git
cd FlowGuard
```

对 AI agent 来说，完整 setup 的意思是：

1. 读取 `AGENTS.md`。
2. 按照宿主 AI 工具的技能机制，加载或复制 `.agents/skills/` 下的全部技能。
3. 默认从 `.agents/skills/flowguard/SKILL.md` 开始。
4. 保持所有 FlowGuard sibling skills 可见，这样 kernel 才能自动路由。
5. 只有需要当前可执行证据时，才运行检查脚本。

然后运行一个小检查脚本：

```powershell
python examples/job_matching/run_checks.py
```

这个例子会对比一个正确模型和两个坏模型。你应该能看到：

- 正确模型是 `OK`；
- broken duplicate-record model 有 invariant violation；
- broken repeated-scoring model 有 invariant violation；
- 输出里有 counterexample trace，展示重复输入怎么走到错误状态。

这个例子是抽象的。它不搜索真实岗位，也不调用 AI 模型。它只用来展示 FlowGuard 的基本方式：重复输入、状态写入、invariant 和反例。

如果你需要 project record 或模板生成命令，可以在仓库里运行 `python -m flowguard ...`。这个命令用于执行检查和 helper，不是 AI-agent 技能安装本身。

## 接入到另一个项目

如果要让另一个项目支持 FlowGuard，第一步是让那个项目里的 AI agent 能看到 FlowGuard 技能套件。也就是让它能读取 `AGENTS.md` 和 `.agents/skills/` 下的所有 FlowGuard `SKILL.md`。

然后，在需要可执行项目记录时，再运行兼容检查命令：

```powershell
python -m flowguard project-adopt --root <target-project>
python -m flowguard project-audit --root <target-project>
python -m flowguard project-upgrade --root <target-project>
```

然后从一个小风险边界开始：

```text
选择一个危险边界
-> 命名你要防住的错误类型
-> 描述 Input、State、Output、副作用、owner 和完成证据
-> 写一个 invariant 或 scenario
-> 放入一个 known-bad case
-> 运行检查
-> 看 counterexample
-> 修改计划、代码、测试、UI 或声明
```

只有风险真的需要时才升级到高级路线。一个 retry bug 可能只需要小模型；release claim、UI flow、refactor split 或 parent/child model chain 才可能需要更强的路线。

## 最小模型长什么样

完整可运行版本在 [`examples/job_matching`](./examples/job_matching)。基本思路是：

```python
@dataclass(frozen=True)
class State:
    processed: tuple[str, ...] = ()
    side_effects: int = 0


@dataclass(frozen=True)
class Input:
    job_id: str


class ProcessJob:
    accepted_input_type = Input
    reads = ("processed", "side_effects")
    writes = ("processed", "side_effects")

    def apply(self, input_obj: Input, state: State):
        if input_obj.job_id in state.processed:
            return [FunctionResult("already_processed", state, label="deduplicated_retry")]
        return [
            FunctionResult(
                "processed",
                replace(
                    state,
                    processed=state.processed + (input_obj.job_id,),
                    side_effects=state.side_effects + 1,
                ),
                label="first_processing",
            )
        ]
```

这个模型只有在同时写了坏例子和检查规则时才有价值。比如规则可以是：“同一个 job 不应该产生重复副作用。”

## 什么时候用

当下一步是否安全取决于 workflow state，而不只是取决于局部代码文本时，用 FlowGuard。

适合：

- 有多个阶段、handoff 或 validation gate 的 AI-agent coding work；
- retry、deduplication、cache refresh、queue、ingestion 和重复 job；
- 可见控件不等于合法恢复路径，或内部 status/audit/diagnostic 内容已经跑到普通用户表面的 UI flow；
- 公开入口和 side effect 必须保持兼容的 refactor；
- 旧 evidence 可能被误当作当前 proof 的测试或发布流程；
- child green 需要重新接回 parent 才能支持 broad confidence 的父子模型。

不适合：

- 一行 typo；
- 纯格式修改；
- 没有 meaningful state、side effect、顺序或 evidence boundary 的任务；
- 需要统计事实、业务事实或生产 telemetry，而不是结构化 workflow 检查的声明。

## 高级 Agent 工作流

如果你只是想跑第一个例子，可以先跳过这一节。

FlowGuard 有一个 model-first kernel 和多条 route-specific 技能。AI agent 应该把下面这些一起当作 FlowGuard 技能套件来加载：

<!-- FLOWGUARD SKILL TABLE ZH START -->
| Skill | 什么时候用 |
| --- | --- |
| `flowguard` | 普通行为/状态建模就够了，或需要协调多条 FlowGuard 路线 |
| `flowguard-existing-model-preflight` | 已有 modeled system 需要先查现有边界，再决定是否新增 |
| `flowguard-development-process-flow` | staged work、multi-skill setup、证据新鲜度，或多条结果等价路线需要选择返工更少的流程；它内部拥有 `plan_detailing_compiler` 与 `agent_workflow_rehearsal` 两条路线 |
| `flowguard-behavior-commitment-ledger` | 广泛行为承诺需要源覆盖、唯一主 owner model，以及 path-sensitive 行为的 Primary Path Authority 交接 |
| `flowguard-field-lifecycle-mesh` | field、schema、mode、prompt/config key、old-field disposition 或 UI 边界候选字段交接需要 ownership |
| `flowguard-contract-exhaustion-mesh` | 有限坏例、same-class family、payload 或 transition case 需要 canonical coverage |
| `flowguard-ui-flow-structure` | UI 候选内容准入、控件、可见表面、按需详情、journey、恢复路径和实现证据需要建模 |
| `flowguard-code-structure-recommendation` | function model 要推导 module、facade、owner、side-effect、config 或 validation boundary |
| `flowguard-structure-mesh` | 大脚本、包、命令或 public API 拆分需要兼容性和 parity evidence |
| `flowguard-test-mesh` | 验证很慢、分层、过期、被 skip、release-only，或分散在 child suite |
| `flowguard-model-test-alignment` | model obligation、code contract 和 test evidence 需要直接对齐 |
| `flowguard-model-mesh` | parent/child model evidence、sibling impact 或 oversized model surface 需要治理 |
| `flowguard-model-topology-hazard-review` | 本地 green 模型仍可能有未来复发风险 |
| `flowguard-architecture-reduction` | 重复 handler、adapter、module、branch 或 validation layer 可能可以安全收缩 |
| `flowguard-model-miss-review` | runtime、test、replay、log 或人工检查在 FlowGuard 通过后仍然失败 |
<!-- FLOWGUARD SKILL TABLE ZH END -->

流程优化是按条件启用的能力，不是每个任务都要做一次“六选一”。确实需要时，FlowGuard 先确认候选路线在结果、证据、安全、副作用、依赖关系和执行责任上等价，再选择诊断范围以及顺序执行或隔离已证明的并行执行。这样既能在合适时先收集足够的相关问题再做一次根因修复，也会在硬阻断出现时及时停下，并在修复后重验所有受影响责任。

这张表会由测试和 `.skillguard/flowguard-suite/suite-map.json` 做一致性校验；少一项或多一项都会失败。Behavior Commitment Ledger 是正式的 15 项成员之一，不是隐藏 helper。

### 当前模型、目标模型和实验模型

FlowGuard 现在明确分开三件事：

- **现状模型**只描述软件现在真实是什么样；
- **目标模型**描述准备替换成什么样；
- **实验模型**可以试另一种方案，但不会因此变成“当前事实”。

文件名叫 `current`、提示词说“这是当前模型”、扫描到了某个模型，或者候选模型
自己检查通过，都不算取得权威。项目只有一个由 `.flowguard/project.toml` 指向的
内容寻址快照是现状权威。这个快照会把模型实例、行为承诺、外部入口、字段/状态/
副作用、代码契约、测试/证据六类有限清单连起来。当前权威缺失或必需覆盖有缺口
时，FlowGuard 会明确阻断“现状模型完整可信”的说法。

目标或实验要真正替代现状，必须作为一个完整的 `ModelRevisionSet` 一次通过：
基础版本、候选版本、关系变化、受影响的兄弟模型、预测/回放证据和当前负责人
回执都必须精确匹配。系统先写不可变记录，最后才在共享的版本比较锁内切换唯一
指针。回退也不是只把指针拨回去；代码、数据、配置和副作用必须先恢复或补偿，
旧快照重新验证后才能恢复权威。不可逆副作用只能向前修复，不能伪称已经回滚。

```powershell
python -m flowguard model-system-bootstrap --root . --snapshot-id <id> --evidence-fingerprint <sha256>
python -m flowguard model-system-audit --root . --json
python -m flowguard model-revision-activate --root . --candidate-snapshot <snapshot.json> --revision-set <revision.json> --receipt-id <id>
python -m flowguard model-revision-rollback --root . --contract <rollback.json> --completed-evidence-fingerprint <sha256> --result exact --receipt-id <id> --reason <reason>
```

这些入口升级的是原来的建模、预检、ModelMesh、行为承诺、字段生命周期、测试和
开发流程；没有另造第二套产品流程，也没有把 OpenSpec 塞进 FlowGuard。

对于普通 UI，FlowGuard 只有两个概念组、三个执行值：`user_visible` 和
`user_on_demand` 属于用户内容，`internal` 不属于。未分类或内部内容不能
渲染；按需内容默认隐藏，必须有显式 reveal、键盘/焦点等价操作和返回路径。
这套约束同时覆盖 display、text、visible surface 和 observed surface；展开和
返回控件必须在来源状态可见、可用，hover 还要使用独立的键盘/焦点事件。用户
需要采用 task/state/recovery/safety 类型引用。旧界面里“已经显示”不代表允许
继续显示。只有与注册控件完全匹配、由范围内任务拥有且不夹带状态或元数据的
正常标签不用重复登记；可运行声明还要有 observed inventory 和逐内容结构化证据。
这里也不引入 audience/role/persona 或 admin/operator/developer/auditor 角色体系。

完整产品的 UI 还会按同一套语义语言检查字体层级、组件、导航、交互、反馈、
恢复和转场：同样职责的页面标题、次级页面标题、弹窗标题、胶囊标签、正文和
状态文字尽量复用同一 token、字号层级和字重；有平台、原生控件、无障碍或安全
差异时，可以记录“只改变呈现”的有证据例外，但不能借例外改变用户目的、行为
承诺、主路径、显示类别或外部结果。页面、API、CLI、别名和包装层如果做的是同
一件事，也共用一个稳定业务目的、一个 active commitment 和一条已验证主路径；
这些内部 id 只用于模型和审计，不显示给普通用户。

行为属于谁，是另一条独立的分类，不能拿 UI 显示类别或 `commitment_kind` 代替。
每条正式承诺只属于一个层面：`product_runtime` 表示软件对用户或外部系统的
行为，`agent_operation` 表示当前 AI 怎样使用工具完成操作，
`development_process` 表示开发、验证、安装、归档和发布怎样治理。预检先在
主要层面查找，再把有类型关系的其他层面单独列作目标、治理或证据上下文；关联
不会转移负责人。这个查询只是轻量、可解释的提醒，不会强迫每个普通动作都跑
模型，也不能保证未来的 AI 一定遵守。可用现有 BCL/预检名下的只读命令查看命中：

```powershell
python -m flowguard behavior-commitment-query "启动 UI 测试并检查端口桥接" --root . --plane agent_operation --term port_bridge --json
```

### 三层证据状态

FlowGuard 刻意把三种不同的“通过”分开：

内置的 15 个技能现在全部使用 `skillguard.contract_source.v2`，共同属于唯一的
`unit:flowguard-suite` 作者维护单元，并绑定既有 FlowGuard owner、模型路线和检查。
合约编译只证明提示词、模型与检查的确定性映射；它不是实际执行深度回执，
也不会新增一条由 SkillGuard 控制的业务路线。

| 层级 | 真正通过了什么 | 还没有证明什么 |
| --- | --- | --- |
| 提示词与合同结构 | 技能提示词、生成合同、引用和 SkillGuard 静态/深度规则一致 | 该路线的原生可执行检查不一定运行过 |
| 原生证据回执 | 路线 owner 的命令针对声明的当前输入运行，并产生可独立验证新鲜度的终态回执 | 一条路线的回执不能替代其他 14 个公开技能，也不能自动关闭父级声明 |
| 自治理父闭环 | 父级消费了所有必需成员的当前 exact-pass 回执，并核对 inventory、freshness 和分发边界 | 它仍只证明声明过的技能套件义务，不证明未来 AI 行为或生产系统整体正确 |

如果提示词、合同、原生检查器、模型、测试或被覆盖输入发生变化，旧证据可能立刻过期。以前绿过，不会被自动续期。

### 验证与分发

模型回归由显式清单管理，并分为三档：`fast` 给日常窄范围反馈，`focused` 检查更宽的选定范围，`full` 运行所有必需且未明确排除的模型。只有当前、全部终态且通过的 full-tier 结果，才能参与 release 声明。

普通使用统一从一个模拟器入口进入。它先审计同一份 manifest，再把每个选中的
模型交给该模型自己的原生 runner；它不会把不同领域模型揉成一个文件，也不会
替模型重新解释通过或失败：

```powershell
python -m flowguard simulator --root . --list
python -m flowguard simulator --root . --model architecture_reduction
python -m flowguard simulator --root . --model "ui_*" --tier focused --json
python -m flowguard simulator --root . --all --tier full --jobs 1 --timeout 900
```

仓库里的 `.flowguard/**/model.py` 和原生 `run_checks.py` 才是可执行模型源码。
`.flowguard/evidence/`、额外本地 worktree、`build/`、`dist/`、缓存和发布回执
属于生成状态或环境状态；它们的体积不等于模型体积，也不会进入干净的 AI-agent
技能安装投影。

```powershell
python scripts/run_flowguard_model_regressions.py --audit-only --json
python scripts/run_flowguard_model_regressions.py --tier fast --output-dir .flowguard/evidence/model-regressions/fast-local
python scripts/run_flowguard_model_regressions.py --tier focused --model "ui_*" --shard 1/2 --jobs 1 --output-dir .flowguard/evidence/model-regressions/focused-1 --json
python scripts/run_flowguard_model_regressions.py --tier full --jobs 1 --timeout 900 --output-dir .flowguard/evidence/model-regressions/full-local --full
```

默认的人类输出是精简摘要；`--json` 输出稳定的机器结果，`--full` 展开人类可读的子项详情，它们都不会改变证据范围。完整 stdout/stderr 只保留一次，使用确定性的 gzip object，并分别记录逻辑内容 hash/大小和存储 hash/大小；child/parent JSON 只保留有限诊断与引用，不再嵌套复制完整 payload。长任务在前台或后台运行时，progress event 只代表“还活着”，不代表完成。真正完成需要选定输出目录里的最终 `report.json`、`evidence-run.json`、current-head 绑定和所有子任务终态回执。

持久证据的清理必须显式执行：

```powershell
python -m flowguard evidence-audit --root .flowguard/evidence --json
python -m flowguard evidence-gc-plan --root .flowguard/evidence --keep 2 --preserve skill-suite --output .flowguard/evidence-gc-plan.json --json
python -m flowguard evidence-gc-apply --root .flowguard/evidence --plan .flowguard/evidence-gc-plan.json --json
python -m flowguard evidence-gc-restore --root .flowguard/evidence --quarantine-id <id> --json
python -m flowguard evidence-gc-purge --root .flowguard/evidence --quarantine-id <id> --json
```

audit 和 plan 不修改证据。apply 会重新核对冻结计划，只把仍然不可达的 run
移动到 quarantine；purge 前可以 restore。purge 只能处理一个精确 quarantine，
而且必须再次确认 current 和 pin 仍有效。plan 应写在持久 evidence root 之外；仍被
其他流程绑定的 legacy 根应逐个传入 `--preserve`，存在未分类字节时不得清理。普通
验证绝不会自动触发持久清理。

技能安装器管理完整的 15 项文件树，并记录自己拥有的文件：

```powershell
python scripts/install_flowguard_skills.py install --source . --codex-home $env:CODEX_HOME --dry-run --json
python scripts/install_flowguard_skills.py install --source . --codex-home $env:CODEX_HOME --json
python scripts/install_flowguard_skills.py check --source . --codex-home $env:CODEX_HOME --json
python scripts/install_flowguard_skills.py parity --source . --formal .agents/skills --shadow $env:FLOWGUARD_SHADOW\.agents\skills --installed $env:CODEX_HOME\skills --json
python scripts/install_flowguard_skills.py uninstall --codex-home $env:CODEX_HOME --dry-run --json
python scripts/install_flowguard_skills.py uninstall --codex-home $env:CODEX_HOME --json
```

`check` 和 `parity` 本身只读，因此不接受 `--dry-run`。卸载只删除未被用户改动、且有 installer ownership 记录的文件；修改过或不归安装器拥有的文件会保留并报告 conflict。当前技能回执放在 `.flowguard/evidence/skill-suite`，模型运行产物放在回归命令指定的 `--output-dir`。环境本地回执会被明确排除在技能分发树之外，需要在提出声明的环境中重新生成。

更完整的命令契约、状态/退出码、后台监控边界、证据目录和安全安装生命周期，见 [`docs/validation_and_distribution.md`](./docs/validation_and_distribution.md)。

常用检查和模板命令：

```powershell
python -m flowguard project-template
python -m flowguard risk-intent-template
python -m flowguard risk-template-library-template
python -m flowguard development-process-flow-template
python -m flowguard ui-flow-structure-template
python -m flowguard code-structure-recommendation-template
python -m flowguard model-test-alignment-template
python -m flowguard test-mesh-template
python -m flowguard structure-mesh-template
python -m flowguard closure-contract-template
python -m flowguard topology-hazard-template
python -m flowguard risk-template-search "completion evidence"
```

完整的当前命令列表可以运行：

```powershell
python -m flowguard --help
```

FlowGuard v0.61.0 只发布源码：不可变 Git tag 是唯一发布权威，release
中不得包含 wheel、source distribution 或 GitHub Release asset。

## Guard Family 关系

| 项目 | 关注点 |
| --- | --- |
| FlowGuard | stateful behavior、process flow、evidence freshness、parent/child model confidence |
| LogicGuard | 写作推理里的 claim、evidence、warrant、assumption、rebuttal、scope 和 overclaiming |
| PhysicsGuard | 物理仿真调试中的低保真 residual check 和模型构建蓝图 |
| FlowPilot | 长周期 AI-agent 软件工作的项目编排和路线控制 |

## 文档入口

| 文件 | 作用 |
| --- | --- |
| [`docs/concept.md`](./docs/concept.md) | 简短概念介绍 |
| [`docs/modeling_protocol.md`](./docs/modeling_protocol.md) | 核心 model-first 协议 |
| [`docs/api_surface.md`](./docs/api_surface.md) | 公开 Python API 概览 |
| [`docs/invariant_examples.md`](./docs/invariant_examples.md) | 常用 invariant 示例 |
| [`docs/development_process_flow.md`](./docs/development_process_flow.md) | staged development、validation freshness、archive、publish 和 release gate |
| [`docs/ui_flow_structure.md`](./docs/ui_flow_structure.md) | UI interaction 和结构建模 |
| [`docs/code_structure_recommendation.md`](./docs/code_structure_recommendation.md) | 模型推导代码结构建议 |
| [`docs/structure_mesh.md`](./docs/structure_mesh.md) | refactor 和 module split 治理 |
| [`docs/test_evidence_mesh.md`](./docs/test_evidence_mesh.md) | 分层验证和证据新鲜度 |
| [`docs/model_test_alignment.md`](./docs/model_test_alignment.md) | 模型义务和测试证据对齐 |
| [`docs/model_mesh_protocol.md`](./docs/model_mesh_protocol.md) | parent/child model mesh 治理 |
| [`docs/model_topology_hazard_review.md`](./docs/model_topology_hazard_review.md) | 从模型拓扑推断未来使用风险的审查 |
| [`docs/model_similarity_consolidation.md`](./docs/model_similarity_consolidation.md) | model-to-model 关系审查和 consolidation handoff |
| [`docs/flowguard_closure_contract.md`](./docs/flowguard_closure_contract.md) | 完整 FlowGuard 使用的 closure contract |
| [`docs/risk_evidence_ledger.md`](./docs/risk_evidence_ledger.md) | risk-to-model-to-code-to-evidence 信心边界 |
| [`docs/runtime_gateway_adoption.md`](./docs/runtime_gateway_adoption.md) | runtime gateway adoption level 和 critical-state writer inventory |
| [`docs/validation_and_distribution.md`](./docs/validation_and_distribution.md) | 分层验证、三层证据、后台进度和技能分发生命周期 |

## 仓库结构

```text
flowguard/     核心库、review helpers、templates、mesh routes、CLI
examples/      小型可执行模型和公开 self-review
docs/          协议、API 说明、示例和 adoption guidance
tests/         针对公开 helper 的回归测试
assets/        README hero image 和生成说明
```

## 公开边界

这个仓库适合作为公开 starter 和 reference implementation。它包含库代码、示例、协议文档、公开模板和通用 AI-agent skill material，其中也包括 Codex-compatible skills。

它不包含私有项目日志、credential、客户数据，也不声称模型覆盖了所有真实系统。FlowGuard 检查的是你声明的模型和证据。真实软件仍然需要测试、code review、UI review、production-facing validation，以及必要的人类判断。

## 许可证

MIT. See [`LICENSE`](./LICENSE).
