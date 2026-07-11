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
| `v0.54.0` | `1.0` | Python standard library only | MIT |

English comes first. A Chinese mirror follows below.

## What FlowGuard Is

An AI-agent skill suite with executable check scripts, FlowGuard checks the risky part of a software change before an agent writes more code. The suite is powered by an executable check engine. Its primary agent surface is `.agents/skills/`: `SKILL.md` files, references, assets, and check scripts that tell an AI when and how to use FlowGuard.

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
3. Start from `.agents/skills/model-first-function-flow/SKILL.md`.
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

If you need the compatibility command wrapper for project records or template generation, run it from the repository with `python -m flowguard ...`. That wrapper executes checks and helpers; it is not the AI-agent skill install.

## Use It In Another Project

For a target project, first make the FlowGuard skill suite available to the AI agent that will work there. The agent needs `AGENTS.md` plus every FlowGuard `SKILL.md` under `.agents/skills/`.

Then, when executable project records are useful, run the compatibility check commands:

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
| `model-first-function-flow` | ordinary behavior or state modeling is enough |
| `flowguard-existing-model-preflight` | an existing modeled system should be checked before adding a new boundary |
| `flowguard-development-process-flow` | staged work, multi-skill setup, install, archive, publish, release, or done confidence depends on evidence freshness |
| `flowguard-agent-workflow-rehearsal` | DevelopmentProcessFlow delegates agent workflow rehearsal, skill order, and skipped-skill evidence |
| `flowguard-plan-detailing-compiler` | DevelopmentProcessFlow delegates rough-plan detailing into scoped rows |
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

The table is parity-checked against `.skillguard/flowguard-suite/suite-map.json`; a missing or extra route fails the documentation test.

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

| Layer | What passed | What it does not prove |
| --- | --- | --- |
| Prompt and contract structure | the skill prompt, generated contract, references, and SkillGuard static/depth rules agree | the route's executable check did not necessarily run |
| Native evidence receipt | the route-owned command ran against declared current inputs and produced a terminal, freshness-verifiable receipt | one route receipt does not close the other sixteen routes or the parent claim |
| Self-governance parent closure | the parent consumed current exact-pass receipts for all required members and checked inventory, freshness, and distribution boundaries | it still proves only the declared suite obligations, not future AI behavior or production correctness |

If a prompt, contract, native checker, model, test, or covered input changes, older evidence may become stale. A previous pass is not silently carried forward.

### Validation And Distribution

Model regressions use an explicit manifest and three tiers: `fast` for narrow development feedback, `focused` for a wider selected surface, and `full` for every required non-excluded model. Only a current, terminal full-tier pass can contribute to a release claim.

```powershell
python scripts/run_flowguard_model_regressions.py --audit-only --json
python scripts/run_flowguard_model_regressions.py --tier fast --output-dir .flowguard/evidence/model-regressions/fast-local
python scripts/run_flowguard_model_regressions.py --tier focused --model "ui_*" --shard 1/2 --jobs 1 --output-dir .flowguard/evidence/model-regressions/focused-1 --json
python scripts/run_flowguard_model_regressions.py --tier full --jobs 1 --timeout 900 --output-dir .flowguard/evidence/model-regressions/full-local --full
```

Default human output is concise. `--json` emits the canonical machine result, while `--full` expands human-readable child details; neither option upgrades the evidence scope. During a long foreground or background run, progress events show liveness only. Completion requires the final `report.json` and terminal child receipts in the selected output directory.

The skill installer manages the complete 17-member tree and records which files it owns:

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

Run `python -m flowguard --help` for the full compatibility command list.

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
3. 默认从 `.agents/skills/model-first-function-flow/SKILL.md` 开始。
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

如果你需要 project record 或模板生成的兼容命令，可以在仓库里运行 `python -m flowguard ...`。这个命令包装层用于执行检查和 helper，不是 AI-agent 技能安装本身。

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
| `model-first-function-flow` | 普通行为/状态建模就够了 |
| `flowguard-existing-model-preflight` | 已有 modeled system 需要先查现有边界，再决定是否新增 |
| `flowguard-development-process-flow` | staged work、multi-skill setup、install、archive、publish、release 或 done confidence 取决于证据新鲜度 |
| `flowguard-agent-workflow-rehearsal` | DevelopmentProcessFlow 委托 agent workflow rehearsal、技能顺序和 skipped-skill evidence |
| `flowguard-plan-detailing-compiler` | DevelopmentProcessFlow 委托把粗计划拆成有 scope 的 rows |
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

这张表会由测试和 `.skillguard/flowguard-suite/suite-map.json` 做一致性校验；少一项或多一项都会失败。Behavior Commitment Ledger 是正式的 17 项成员之一，不是隐藏 helper。

对于普通 UI，FlowGuard 只有两个概念组、三个执行值：`user_visible` 和
`user_on_demand` 属于用户内容，`internal` 不属于。未分类或内部内容不能
渲染；按需内容默认隐藏，必须有显式 reveal、键盘/焦点等价操作和返回路径。
这套约束同时覆盖 display、text、visible surface 和 observed surface；展开和
返回控件必须在来源状态可见、可用，hover 还要使用独立的键盘/焦点事件。用户
需要采用 task/state/recovery/safety 类型引用。旧界面里“已经显示”不代表允许
继续显示。只有与注册控件完全匹配、由范围内任务拥有且不夹带状态或元数据的
正常标签不用重复登记；可运行声明还要有 observed inventory 和逐内容结构化证据。
这里也不引入 audience/role/persona 或 admin/operator/developer/auditor 角色体系。

### 三层证据状态

FlowGuard 刻意把三种不同的“通过”分开：

| 层级 | 真正通过了什么 | 还没有证明什么 |
| --- | --- | --- |
| 提示词与合同结构 | 技能提示词、生成合同、引用和 SkillGuard 静态/深度规则一致 | 该路线的原生可执行检查不一定运行过 |
| 原生证据回执 | 路线 owner 的命令针对声明的当前输入运行，并产生可独立验证新鲜度的终态回执 | 一条路线的回执不能替代其他 16 条路线，也不能自动关闭父级声明 |
| 自治理父闭环 | 父级消费了所有必需成员的当前 exact-pass 回执，并核对 inventory、freshness 和分发边界 | 它仍只证明声明过的技能套件义务，不证明未来 AI 行为或生产系统整体正确 |

如果提示词、合同、原生检查器、模型、测试或被覆盖输入发生变化，旧证据可能立刻过期。以前绿过，不会被自动续期。

### 验证与分发

模型回归由显式清单管理，并分为三档：`fast` 给日常窄范围反馈，`focused` 检查更宽的选定范围，`full` 运行所有必需且未明确排除的模型。只有当前、全部终态且通过的 full-tier 结果，才能参与 release 声明。

```powershell
python scripts/run_flowguard_model_regressions.py --audit-only --json
python scripts/run_flowguard_model_regressions.py --tier fast --output-dir .flowguard/evidence/model-regressions/fast-local
python scripts/run_flowguard_model_regressions.py --tier focused --model "ui_*" --shard 1/2 --jobs 1 --output-dir .flowguard/evidence/model-regressions/focused-1 --json
python scripts/run_flowguard_model_regressions.py --tier full --jobs 1 --timeout 900 --output-dir .flowguard/evidence/model-regressions/full-local --full
```

默认的人类输出是精简摘要；`--json` 输出稳定的机器结果，`--full` 展开人类可读的子项详情，它们都不会改变证据范围。长任务在前台或后台运行时，progress event 只代表“还活着”，不代表完成。真正完成需要选定输出目录里的最终 `report.json` 和所有子任务终态回执。

技能安装器管理完整的 17 项文件树，并记录自己拥有的文件：

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

完整兼容命令列表可以运行：

```powershell
python -m flowguard --help
```

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
