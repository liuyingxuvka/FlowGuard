# FlowGuard

<!-- README HERO START -->
<p align="center">
  <img src="./assets/readme-hero/hero.png" alt="FlowGuard concept hero image" width="100%" />
</p>

<p align="center">
  <img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="120" />
</p>

<p align="center">
  <strong>Executable finite-state models for designing and checking AI-agent workflows, UI flows, and development processes.</strong>
</p>
<!-- README HERO END -->

| Public release | Schema | Runtime | License |
| --- | --- | --- | --- |
| `v0.18.5` | `1.0` | Python standard library only | MIT |

English lead content comes first; a Chinese mirror follows below.

## What FlowGuard Is

FlowGuard is a small Python library and Codex-ready workflow method for turning risky stateful behavior into an executable finite-state model before action. It is the workflow/state guard in the Guard family: use it when order, state, ownership, side effects, UI availability, role handoff, or evidence freshness can change whether a plan is actually safe.

It models a function block as:

```text
Input x State -> Set(Output x State)
```

That model is then checked for reachable traces, invariant failures, loops, stuck states, stale evidence, missing handoffs, conformance gaps, parent/child evidence drift, and counterexample paths that should change the next engineering step.

FlowGuard is not an LLM wrapper, a probability engine, a Monte Carlo simulator, or a replacement for tests. It is a structural preflight layer: make the risky transition explicit, run the small model, inspect the counterexample, then change the plan or code with less hidden state.

## What You Can Design And Verify

FlowGuard is useful at the design stage. You name the states, inputs, outputs, ownership boundaries, side effects, and gates; the model then gives you both a design shape and the checks that decide whether that shape is currently safe.

| Work type | Model-first design output | What keeps it trustworthy | Boundary |
| --- | --- | --- | --- |
| Development process | Staged route, legal next actions, validation gates, stale-evidence reset, peer-write invalidation, archive/release readiness, and done criteria | DevelopmentProcessFlow reviews scenario failures, skipped gates, freshness gaps, and invalid completion claims before the process is treated as usable | A green local step is not global green after later edits, peer writes, or route mutation |
| UI interface | Persistent regions, contextual panels, local actions, overlays, recovery paths, button availability, display ownership, duplicate-control rules, and text hierarchy | UI Flow Structure checks launch-to-terminal journeys, visible control availability, recovery paths, duplicate functions, warning/error escalation, and implementation click-through evidence | It models interaction structure; visual polish, accessibility details, and browser/device behavior still need ordinary UI review |
| Code structure | Module split, facade boundary, state owner, side-effect owner, config owner, validation owner, and public-entrypoint compatibility plan | Code Structure Recommendation and StructureMesh look for ownership leaks, dependency cycles, facade drift, config drift, and missing parity evidence | It recommends a safer split; it does not replace implementation tests or code review |
| Test strategy | Routine/release test layers, parent/child suites, timeout boundaries, stale/hidden evidence rules, and revalidation triggers | TestMesh and model-test alignment compare model obligations with actual tests, hidden skips, stale passes, timeout boundaries, and release-only checks | Tests only support the modeled obligations they actually cover |
| Model mesh or bug repair | Parent/child split, evidence contract, reattachment gate, sibling impact review, model-miss class, and same-class bad case | ModelMesh requires parents to consume fresh child evidence; model-miss review adds same-class bad cases before closure | Child evidence does not improve parent confidence until the parent contract consumes it |

This is the core product: FlowGuard turns a vague workflow, UI journey, refactor, test strategy, or release process into a small state machine with explicit failure traces. The counterexample is not just a bug report; it is design feedback that says which state, gate, owner, or evidence rule must change before work continues.

## Why It Is Worth Trying

- It turns fuzzy workflow, UI, code-structure, test, or release decisions into small executable models before the agent writes code, tests, or public claims.
- It derives development routes, interface topology, module ownership, validation hierarchy, and release gates from the model, then checks those decisions with traces.
- It shows the exact failure path: skipped review, stale child evidence, invalid button state, facade drift, missing revalidation, or a parent that trusted a child too early.
- It is intentionally small: many useful models are just a few states, inputs, invariants, and transition functions.
- It keeps evidence honest across parent and child models, so a repaired child or later file edit does not leave stale green status behind.
- It runs on the Python standard library and fits into ordinary repository workflows without becoming a heavy platform.

## The Logic Contract

FlowGuard is useful when these preconditions hold:

| Layer | Requirement |
| --- | --- |
| Risk boundary | There is a workflow, implementation path, UI path, test hierarchy, model mesh, or release decision where order and state matter |
| State vocabulary | The relevant states, inputs, outputs, ownership boundaries, and side effects can be named at useful abstraction level |
| Expected behavior | At least one invariant, scenario expectation, conformance trace, or freshness rule can be stated |
| Actionability | A counterexample would change what the agent, engineer, or reviewer does next |

The postconditions FlowGuard aims to create:

| Output | Meaning |
| --- | --- |
| Reviewed model | A small executable representation of the risky part of the work |
| Counterexample trace | A concrete path showing how the plan can fail |
| Passing evidence | A bounded claim that the modeled scenarios, invariants, and evidence rules currently pass |
| Scoped confidence | A decision boundary that says what is green, what is still unknown, and what must be revalidated after later edits |

The core rule is simple: local green is not global green unless the parent contract has consumed fresh child evidence.

## Why It Exists

AI-agent projects often fail at the same point: the local edit looks correct, but the surrounding workflow is not modeled. Retries duplicate side effects. Cache state drifts. A refactor preserves the public entrypoint but breaks ownership. A UI journey has visible controls but no valid recovery path. A child model is repaired, but the parent still trusts stale evidence. A release README says "done" after code, tests, docs, or peer writes have already invalidated the proof.

FlowGuard gives those weak spots a small executable shape before the action becomes expensive.

## What It Checks

| Route | Purpose |
| --- | --- |
| Scenario and invariant review | Checks expected traces, hard rules, repeated inputs, dead branches, and bad terminal states |
| Conformance replay | Compares representative abstract traces with implementation behavior when code exists |
| Loop and progress review | Finds non-progressing cycles, stuck states, and weak completion evidence |
| Model-test alignment | Compares model obligations, external code contracts, and ordinary test evidence |
| ModelMesh | Splits oversized models into parent/child evidence, propagates child boundary changes upward, reviews affected sibling models, and uses mesh closure models for whole-flow parent confidence |
| Child model reattachment | Requires a parent mesh to consume the repaired child evidence id and verify input, output, state, side-effect, and exported-contract handoffs |
| Mesh closure model | Models parent/child handoff tokens so child outputs, joins, exits, and out-of-scope branches must be consumed before `mesh_green_can_continue` |
| TestMesh | Reviews parent/child validation layers, stale evidence, hidden skips, timeouts, and routine-vs-release gates |
| StructureMesh | Reviews large refactor splits, facade compatibility, dependency cycles, config drift, and parity evidence |
| Code Structure Recommendation | Derives module, facade, state-owner, side-effect, config, and validation boundaries before code is written |
| UI Flow Structure | Models UI states, controls, visible buttons, events, failures, recovery paths, launch-to-terminal app journeys, implementation click-through evidence, overlays, duplicate controls, and display ownership before deriving interface topology |
| UI Text Hierarchy Blueprint | Reviews visible and assistive UI text by state, region, role, semantic key, owner, priority, duplication rationale, and warning/error escalation |
| DevelopmentProcessFlow | Checks staged development flow, lifecycle ordering, artifact overwrite, validation freshness, minimum revalidation, archive readiness, and release confidence |
| Model-Miss Review | After a runtime failure, classifies what the model missed and adds a generalized same-class bad case before closure |

For non-trivial FlowGuard work, skill guidance now defaults to a user-facing
Mermaid model snapshot during the work once the route or model shape is stable
enough to explain. The agent first chooses the FlowGuard diagram semantics:
behavior/state, development process, UI state, model-test coverage, code
structure, or mesh. The diagram can show major states, branches, gates,
evidence, skipped/not-run gaps, and claim boundaries, and it should be updated
when the model boundary materially changes. Tiny or user-suppressed tasks may
stay concise. Diagrams are explanation only; executable checks remain the
source of validation.

## Typical Workflow

1. Choose the smallest boundary where state, ordering, or evidence freshness matters.
2. Name the inputs, states, outputs, side effects, and ownership handoffs.
3. Model the transition as `Input x State -> Set(Output x State)`.
4. Add invariants, scenario expectations, or parent/child contracts.
5. Run the review and inspect counterexamples.
6. Revise the model, plan, tests, or implementation.
7. Record what was checked, what remains out of scope, and when the evidence becomes stale.

## Quick Start

```powershell
git clone https://github.com/liuyingxuvka/FlowGuard.git
cd FlowGuard
python -m pip install -e .
python -m flowguard schema-version
python -m flowguard self-review
```

Useful template entry points:

```powershell
python -m flowguard project-template
python -m flowguard model-test-alignment-template
python -m flowguard code-structure-recommendation-template
python -m flowguard ui-flow-structure-template
python -m flowguard development-process-flow-template
python -m flowguard test-mesh-template
python -m flowguard structure-mesh-template
```

Run focused examples:

```powershell
python examples/flowguard_product_boundary/run_review.py
python examples/hierarchical_model_mesh/run_review.py
python examples/job_matching/run_checks.py
```

## Minimal Python Sketch

```python
from dataclasses import dataclass, replace

from flowguard import Explorer, FunctionResult, Invariant, Workflow


@dataclass(frozen=True)
class State:
    processed: tuple[str, ...] = ()
    side_effects: int = 0


@dataclass(frozen=True)
class Input:
    job_id: str
    retry: bool = False


class ProcessJob:
    name = "process_job"
    accepted_input_type = Input
    reads = ("processed", "side_effects")
    writes = ("processed", "side_effects")
    input_description = "job request"
    output_description = "job status"
    idempotency = "same job id creates at most one side effect"

    def apply(self, input_obj: Input, state: State):
        if input_obj.job_id in state.processed:
            return [
                FunctionResult(
                    output="already_processed",
                    new_state=state,
                    label="deduplicated_retry",
                )
            ]
        return [
            FunctionResult(
                output="processed",
                new_state=replace(
                    state,
                    processed=state.processed + (input_obj.job_id,),
                    side_effects=state.side_effects + 1,
                ),
                label="first_processing",
            )
        ]


workflow = Workflow((ProcessJob(),), name="retry_deduplication")

report = Explorer(
    workflow=workflow,
    initial_states=(State(),),
    external_inputs=(Input("A"),),
    invariants=(
        Invariant(
            name="side_effect_once",
            description="The same job may not create duplicate side effects.",
            predicate=lambda state, trace: state.side_effects <= len(set(state.processed)),
        ),
    ),
    max_sequence_length=2,
    progress_steps=0,
).explore()
print(report.format_text())
```

## Skill Architecture

FlowGuard has one kernel and several peer satellite skills. Clear staged-development, UI, structure, test, mesh, alignment, or model-miss work should route directly to the matching satellite; `model-first-function-flow` remains the kernel for ordinary behavior/state modeling, unclear route selection, and cross-route coordination:

| Skill route | Use it when |
| --- | --- |
| `model-first-function-flow` | Ordinary behavior/state modeling, unclear FlowGuard route selection, cross-route coordination, or core model work before a narrower route is known |
| `flowguard-model-test-alignment` | Model obligations and test evidence need a direct comparison |
| `flowguard-model-mesh` | A project has multiple local models, child evidence, or oversized model surfaces |
| `flowguard-test-mesh` | Test evidence is layered, slow, stale, skipped, release-only, or split across child suites |
| `flowguard-structure-mesh` | A script, package, command, public API, or refactor split needs compatibility governance |
| `flowguard-code-structure-recommendation` | A function-flow model should derive module and ownership boundaries before code |
| `flowguard-ui-flow-structure` | UI controls, visible buttons, states, events, launch-to-terminal journeys, implementation click-through evidence, overlays, recovery actions, and information ownership need modeling before visual design |
| `flowguard-development-process-flow` | Non-trivial staged development or modification needs validation, or done/archive/publish/release confidence depends on validation freshness |
| `flowguard-model-miss-review` | Real runtime evidence failed after a FlowGuard model passed |

## Relationship To The Guard Family

FlowGuard is the state and workflow guard.

| Project | Focus |
| --- | --- |
| FlowGuard | Stateful behavior, process flow, evidence freshness, parent/child model confidence |
| LogicGuard | Claims, evidence, warrants, assumptions, rebuttals, scope, and overclaiming in written reasoning |
| PhysicsGuard | Low-fidelity residual checks and model-building blueprints for physical simulation debugging |
| FlowPilot | Long-running project orchestration and route control for AI-agent software work |

## Documentation Map

| File | Purpose |
| --- | --- |
| `docs/modeling_protocol.md` | Core model-first protocol |
| `docs/model_test_alignment.md` | Model obligation and test evidence alignment |
| `docs/model_mesh_protocol.md` | Parent/child model mesh governance |
| `docs/hierarchical_model_mesh.md` | Hierarchical model examples and child evidence |
| `docs/test_evidence_mesh.md` | Layered validation and evidence freshness |
| `docs/structure_mesh.md` | Refactor and module split governance |
| `docs/code_structure_recommendation.md` | Model-derived code structure recommendations |
| `docs/ui_flow_structure.md` | UI interaction and structure modeling |
| `docs/development_process_flow.md` | Staged development lifecycle, validation freshness, archive, publish, and release gates |
| `docs/api_surface.md` | Public Python API overview |

## Repository Layout

```text
flowguard/     Core library, review helpers, templates, mesh routes, CLI
examples/      Small executable models and public self-reviews
docs/          Protocols, API notes, examples, and adoption guidance
tests/         Focused regression tests for the public helpers
assets/        README hero image and generation notes
```

## Public Boundary

This repository is designed to be useful as a public starter and reference implementation. It includes the library, examples, protocol docs, public templates, and Codex skill material.

It does not include private project logs, personal predictive knowledge, credentials, customer data, or claims that every real system is covered by the model. A FlowGuard pass means the declared model obligations passed. It does not mean the whole project is correct.

## License

MIT. See `LICENSE`.

---

## 中文说明

FlowGuard 是一个在危险转移变成代码、UI、测试或发布结论之前，先用有限状态模型设计并验证流程的预检系统。

## FlowGuard 是什么

FlowGuard 是一个小型 Python 库，也是一套可以配合 Codex 使用的工作方法。它把有风险的有状态行为先写成可执行的有限状态模型，再从模型推导开发流程、UI 交互结构、代码 ownership、测试层级或发布 gate。它是 Guard family 里的 workflow/state guard：当顺序、状态、ownership、副作用或证据新鲜度会改变计划是否安全时，就应该先用它。

它把一个函数块表示成：

```text
Input x State -> Set(Output x State)
```

然后检查可达路径、invariant 失败、循环、卡住状态、旧证据、缺失 handoff、实现不一致、父子模型证据漂移，以及应该改变下一步工程动作的 counterexample。

FlowGuard 不是 LLM wrapper，不调用模型 API，不做概率估计，也不是测试替代品。它是结构化预检层：先把危险的状态转移说清楚，跑小模型，看 counterexample，再决定计划或代码怎么改。

## 它能设计并验证什么

FlowGuard 的价值在动手之前就开始。你先命名 state、input、output、ownership boundary、side effect 和 gate；模型同时给出设计形状，以及判断这个形状当前是否安全的检查。

| 工作类型 | 模型先行的设计输出 | 什么让它可信 | 边界 |
| --- | --- | --- | --- |
| 开发流程 | staged route、合法 next action、验证 gate、stale-evidence reset、peer-write invalidation、release/archive readiness、done criteria | DevelopmentProcessFlow 在流程被当作可用前检查 scenario failure、skipped gate、freshness gap 和无效完成声明 | 后续编辑、peer write 或 route mutation 之后，局部 green 不等于整体 green |
| UI 界面 | 持久区域、上下文 panel、本地动作、overlay、恢复路径、按钮 availability、display ownership、重复控件规则、文本层级 | UI Flow Structure 检查 launch-to-terminal journey、可见控件 availability、恢复路径、重复功能、warning/error escalation 和真实点击证据 | 它建模 interaction structure；视觉打磨、无障碍细节和浏览器/设备行为仍要普通 UI review |
| 代码结构 | module split、facade boundary、state owner、side-effect owner、config owner、validation owner、公开入口兼容计划 | Code Structure Recommendation 和 StructureMesh 检查 ownership leak、dependency cycle、facade drift、config drift 和缺失 parity evidence | 它建议更安全的拆分，不替代实现测试和 code review |
| 测试策略 | routine/release test layers、父子测试套件、timeout 边界、旧/隐藏证据规则、revalidation trigger | TestMesh 和 model-test alignment 对照模型义务、真实测试、hidden skip、stale pass、timeout 边界和 release-only check | 测试只支持它实际覆盖到的模型义务 |
| Model mesh 或 bug 修复 | 父子拆分、evidence contract、reattachment gate、sibling impact review、model-miss 类型、同类坏 case | ModelMesh 要求父级消费新鲜 child evidence；model-miss review 在关闭前补同类坏 case | child evidence 不会自动提高父级信心，必须被父级 contract 消费 |

这才是 FlowGuard 的核心产品：把模糊的 workflow、UI journey、refactor、test strategy 或 release process 变成小型状态机，并给出明确失败路径。counterexample 是设计反馈：它告诉你哪个 state、gate、owner 或 evidence rule 必须先改，工作才能继续。

## 为什么值得一试

- 它把模糊的 workflow、UI、代码结构、测试或发布决策先变成小型可执行模型，再让 agent 写代码、测试或公开声明。
- 它能从模型推导开发路线、界面拓扑、模块 ownership、验证层级和 release gate，然后用 trace 检查这些决策。
- 它会给出具体失败路径：跳过 review、旧 child evidence、错误按钮状态、facade drift、缺失 revalidation，或者父级过早信任子级。
- 它刻意保持小：很多有用模型只需要少量 state、input、invariant 和 transition function。
- 它会维护父子模型之间的证据新鲜度，避免 child 修过或文件后来又改过之后，父级还拿旧 green status 当证据。
- 它只依赖 Python 标准库，可以嵌入普通仓库工作流，而不是变成重平台。

## 逻辑契约

FlowGuard 适合在这些前置条件成立时使用：

| 层级 | 要求 |
| --- | --- |
| 风险边界 | 存在 workflow、实现路径、UI 路径、测试层级、model mesh 或发布决策，且顺序和状态会影响结果 |
| 状态词汇 | 相关 state、input、output、ownership boundary 和 side effect 能被抽象命名 |
| 预期行为 | 至少能写出一个 invariant、scenario expectation、conformance trace 或 freshness rule |
| 可行动性 | 如果模型给出反例，下一步行动会因此改变 |

它要交付的后置条件是：

| 输出 | 含义 |
| --- | --- |
| 已审查模型 | 对风险边界的小型可执行表示 |
| 反例路径 | 一条具体路径，说明计划如何失败 |
| 通过证据 | 一个有边界的结论：当前声明的场景、invariant 和证据规则通过 |
| 范围化信心 | 明确哪些是 green，哪些仍未知，以及后续编辑后需要重新验证什么 |

核心规则是：局部变绿不等于整体变绿，除非父级 contract 已经消费了新鲜的子级证据。

## 为什么需要它

AI-agent 项目经常不是坏在局部代码，而是坏在外围 workflow 没有建模。retry 产生重复 side effect，cache 状态漂移，refactor 保留了入口但破坏了 ownership，UI journey 有可见控件但没有有效恢复路径，子模型修好了但父模型还拿着旧证据，README 或 release note 在后续代码、测试、文档或 peer 写入之后仍然说自己已经 done。

FlowGuard 给这些薄弱点一个小而可执行的结构。

## 它检查什么

| 路线 | 作用 |
| --- | --- |
| Scenario 和 invariant review | 检查预期路径、硬规则、重复输入、死分支和坏终态 |
| Conformance replay | 当代码已存在时，把抽象路径和真实实现行为对齐 |
| Loop 和 progress review | 找不前进的循环、卡住状态和弱完成证据 |
| Model-test alignment | 对照模型义务、外部代码 contract 和普通测试证据 |
| ModelMesh | 把过大的模型拆成父子证据，向上同步 child boundary 变化，检查 sibling，并用 closure model 支撑父级全流程信心 |
| Child model reattachment | `v0.17.0` 要求父级 mesh 消费修复后的 child evidence id，并验证 input、output、state、side-effect 和导出 contract handoff |
| Mesh closure model | 把父子模型之间的 handoff token 建成小模型，确保 child output、join、exit 和 out-of-scope 分支都被消费后才允许 `mesh_green_can_continue` |
| TestMesh | 检查父子验证层、旧证据、隐藏 skip、timeout，以及 routine/release gate |
| StructureMesh | 检查大 refactor 拆分、facade 兼容、依赖环、配置漂移和 parity 证据 |
| Code Structure Recommendation | 在写代码前，从模型推导 module、facade、state owner、side effect、config 和验证边界 |
| UI Flow Structure | 在视觉设计前，建模 UI 状态、可见按钮、控件、事件、从启动到终态的 app journey、真实界面点击验收证据、失败、恢复、overlay、重复控件和信息显示 ownership |
| UI Text Hierarchy Blueprint | 按 state、region、role、semantic key、owner、priority、重复理由和 warning/error escalation 审查 UI 文案层级 |
| DevelopmentProcessFlow | 检查分阶段开发流程、生命周期顺序、artifact 覆盖、验证新鲜度、最小重验证、archive readiness 和 release confidence |
| Model-Miss Review | 当运行时失败发生在 FlowGuard 通过之后，分类模型漏了什么，并补一个同类坏 case |

对于非平凡的 FlowGuard 工作，skill guidance 现在默认在工作过程中给用户
展示 Mermaid 模型快照，只要路线或模型形状已经稳定到足以解释。图可以展示
主要状态、分支、gate、证据、skipped/not-run 缺口和结论边界；当模型边界发生
实质变化时应该更新。很小的任务或用户明确不想看图时可以保持简洁。图只是
解释层；真正的验证仍然来自可执行检查。

## 典型流程

1. 选最小的风险边界，通常是状态、顺序或证据新鲜度会影响结果的地方。
2. 命名 input、state、output、side effect 和 ownership handoff。
3. 把转移写成 `Input x State -> Set(Output x State)`。
4. 加 invariant、scenario expectation 或父子 contract。
5. 跑 review，看 counterexample。
6. 修改模型、计划、测试或实现。
7. 记录检查过什么、哪些不在范围内，以及证据什么时候会变旧。

## 快速开始

```powershell
git clone https://github.com/liuyingxuvka/FlowGuard.git
cd FlowGuard
python -m pip install -e .
python -m flowguard schema-version
python -m flowguard self-review
```

常用模板入口：

```powershell
python -m flowguard project-template
python -m flowguard model-test-alignment-template
python -m flowguard code-structure-recommendation-template
python -m flowguard ui-flow-structure-template
python -m flowguard development-process-flow-template
python -m flowguard test-mesh-template
python -m flowguard structure-mesh-template
```

运行示例：

```powershell
python examples/flowguard_product_boundary/run_review.py
python examples/hierarchical_model_mesh/run_review.py
python examples/job_matching/run_checks.py
```

## Skill 架构

FlowGuard 有一个 kernel 和多个同级 satellite skill。明确属于分阶段开发、UI、结构、测试、mesh、alignment 或 model-miss 的工作，应直接进入对应 satellite；`model-first-function-flow` 保留为普通行为/状态建模、路线不清楚、跨路线协调或先做核心模型时的 kernel：

| Skill route | 适用场景 |
| --- | --- |
| `model-first-function-flow` | 普通行为/状态建模、FlowGuard 路线不清楚、跨路线协调，或在更窄路线明确前先做核心模型 |
| `flowguard-model-test-alignment` | 需要对照模型义务和测试证据 |
| `flowguard-model-mesh` | 项目有多个本地模型、子证据或过大的模型表面 |
| `flowguard-test-mesh` | 测试证据分层、很慢、过期、被 skip、只在 release 跑，或分布在子套件 |
| `flowguard-structure-mesh` | 脚本、包、命令、公开 API 或 refactor 拆分需要兼容性治理 |
| `flowguard-code-structure-recommendation` | 写代码前，需要让 function-flow 模型推导 module 和 ownership boundary |
| `flowguard-ui-flow-structure` | UI control、可见按钮、state、event、启动到终态 journey、真实界面点击验收证据、overlay、恢复动作和信息 ownership 需要先建模 |
| `flowguard-development-process-flow` | 非平凡的分阶段开发或修改需要验证，或 done、archive、publish、release 信心取决于验证证据是否新鲜 |
| `flowguard-model-miss-review` | FlowGuard 模型通过后，真实运行证据仍然失败 |

## Guard Family 关系

FlowGuard 是状态和工作流 guard。

| 项目 | 关注点 |
| --- | --- |
| FlowGuard | 状态行为、过程流、证据新鲜度、父子模型信心 |
| LogicGuard | 写作推理中的 claim、evidence、warrant、assumption、rebuttal、scope 和 overclaiming |
| PhysicsGuard | 物理仿真调试中的低保真 residual 检查和候选模型构建蓝图 |
| FlowPilot | 长周期 AI-agent 软件工作的项目编排和路线控制 |

## 文档入口

| 文件 | 作用 |
| --- | --- |
| `docs/modeling_protocol.md` | 核心 model-first 协议 |
| `docs/model_test_alignment.md` | 模型义务和测试证据对齐 |
| `docs/model_mesh_protocol.md` | 父子模型 mesh 治理 |
| `docs/hierarchical_model_mesh.md` | 层级模型示例和子证据 |
| `docs/test_evidence_mesh.md` | 分层验证和证据新鲜度 |
| `docs/structure_mesh.md` | refactor 和模块拆分治理 |
| `docs/code_structure_recommendation.md` | 模型推导代码结构建议 |
| `docs/ui_flow_structure.md` | UI interaction 和结构建模 |
| `docs/development_process_flow.md` | 分阶段开发生命周期、验证新鲜度、archive、publish 和 release gate |
| `docs/api_surface.md` | 公开 Python API 概览 |

## 仓库结构

```text
flowguard/     核心库、review helpers、templates、mesh routes、CLI
examples/      小型可执行模型和公开 self-review
docs/          协议、API 说明、示例和 adoption guidance
tests/         针对公开 helper 的回归测试
assets/        README hero image 和生成说明
```

## 公开边界

这个仓库适合作为公开 starter 和 reference implementation。它包含库代码、示例、协议文档、公开模板和 Codex skill 材料。

它不包含私有项目日志、个人 predictive knowledge、credential、客户数据，也不声称模型覆盖了所有真实系统。FlowGuard 通过只表示声明的模型义务通过，不表示整个项目已经正确。

## 许可证

MIT. See `LICENSE`.
