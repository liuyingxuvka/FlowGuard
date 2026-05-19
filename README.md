# FlowGuard

<!-- README HERO START -->
<p align="center">
  <img src="./assets/readme-hero/hero.png" alt="FlowGuard concept hero image" width="100%" />
</p>

<p align="center">
  <strong>A finite-state preflight system for risky AI-agent workflows, code changes, and process decisions.</strong>
</p>
<!-- README HERO END -->

| Public release | Schema | Runtime | License |
| --- | --- | --- | --- |
| `v0.17.1` | `1.0` | Python standard library only | MIT |

English lead content comes first; a Chinese mirror follows below.

## What FlowGuard Is

FlowGuard is a small Python library and Codex-ready workflow method for turning risky behavior into an executable finite-state model before action.

It models a function block as:

```text
Input x State -> Set(Output x State)
```

That model is then checked for reachable traces, invariant failures, loops, stale evidence, missing handoffs, conformance gaps, and parent/child evidence drift.

FlowGuard is not an LLM wrapper, a probability engine, a Monte Carlo simulator, or a replacement for tests. It is a structural preflight layer: make the risky transition explicit, run the small model, inspect the counterexample, then change the plan or code with less hidden state.

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

AI-agent projects often fail at the same point: the local edit looks correct, but the surrounding workflow is not modeled. Retries duplicate side effects. Cache state drifts. A refactor preserves the public entrypoint but breaks ownership. A child model is repaired, but the parent still trusts stale evidence. A release README says "done" after code, tests, docs, or peer writes have already invalidated the proof.

FlowGuard gives those weak spots a small executable shape before the action becomes expensive.

## What It Checks

| Route | Purpose |
| --- | --- |
| Scenario and invariant review | Checks expected traces, hard rules, repeated inputs, dead branches, and bad terminal states |
| Conformance replay | Compares representative abstract traces with implementation behavior when code exists |
| Loop and progress review | Finds non-progressing cycles, stuck states, and weak completion evidence |
| Model-test alignment | Compares model obligations, external code contracts, and ordinary test evidence |
| ModelMesh | Splits oversized models into parent/child evidence, propagates child boundary changes upward, and reviews affected sibling models before parent confidence |
| Child model reattachment | Requires a parent mesh to consume the repaired child evidence id and verify input, output, state, side-effect, and exported-contract handoffs |
| TestMesh | Reviews parent/child validation layers, stale evidence, hidden skips, timeouts, and routine-vs-release gates |
| StructureMesh | Reviews large refactor splits, facade compatibility, dependency cycles, config drift, and parity evidence |
| Code Structure Recommendation | Derives module, facade, state-owner, side-effect, config, and validation boundaries before code is written |
| UI Flow Structure | Models UI states, controls, events, failures, recovery paths, overlays, duplicate controls, and display ownership before deriving interface topology |
| UI Text Hierarchy Blueprint | Reviews visible and assistive UI text by state, region, role, semantic key, owner, priority, duplication rationale, and warning/error escalation |
| DevelopmentProcessFlow | Checks lifecycle ordering, artifact overwrite, validation freshness, minimum revalidation, archive readiness, and release confidence |
| Model-Miss Review | After a runtime failure, classifies what the model missed and adds a generalized same-class bad case before closure |

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

FlowGuard has one kernel idea and several focused satellites. The kernel asks whether model-first reasoning applies, then routes the work to a narrower model when needed:

| Skill route | Use it when |
| --- | --- |
| `model-first-function-flow` | A task touches behavior, state, retries, idempotency, caching, queues, side effects, or module boundaries |
| `flowguard-model-test-alignment` | Model obligations and test evidence need a direct comparison |
| `flowguard-model-mesh` | A project has multiple local models, child evidence, or oversized model surfaces |
| `flowguard-test-mesh` | Test evidence is layered, slow, stale, skipped, release-only, or split across child suites |
| `flowguard-structure-mesh` | A script, package, command, public API, or refactor split needs compatibility governance |
| `flowguard-code-structure-recommendation` | A function-flow model should derive module and ownership boundaries before code |
| `flowguard-ui-flow-structure` | UI controls, states, events, overlays, recovery actions, and information ownership need modeling before visual design |
| `flowguard-development-process-flow` | Done, archive, publish, or release confidence depends on validation freshness |
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
| `docs/development_process_flow.md` | Lifecycle, archive, publish, and release gates |
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

FlowGuard 是一个面向 AI agent 工作流、代码修改和过程决策的有限状态预检系统。

## FlowGuard 是什么

FlowGuard 是一个小型 Python 库，也是一套可以配合 Codex 使用的工作方法。它把有风险的行为先写成可执行的有限状态模型，再让 agent 或工程师动手。

它把一个函数块表示成：

```text
Input x State -> Set(Output x State)
```

然后检查可达路径、invariant 失败、循环、旧证据、缺失 handoff、实现不一致，以及父子模型证据漂移。

FlowGuard 不是 LLM wrapper，不调用模型 API，不做概率估计，也不是测试替代品。它是结构化预检层：先把危险的状态转移说清楚，跑小模型，看 counterexample，再决定计划或代码怎么改。

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

AI-agent 项目经常不是坏在局部代码，而是坏在外围 workflow 没有建模。retry 产生重复 side effect，cache 状态漂移，refactor 保留了入口但破坏了 ownership，子模型修好了但父模型还拿着旧证据，README 或 release note 在后续代码、测试、文档或 peer 写入之后仍然说自己已经 done。

FlowGuard 给这些薄弱点一个小而可执行的结构。

## 它检查什么

| 路线 | 作用 |
| --- | --- |
| Scenario 和 invariant review | 检查预期路径、硬规则、重复输入、死分支和坏终态 |
| Conformance replay | 当代码已存在时，把抽象路径和真实实现行为对齐 |
| Loop 和 progress review | 找不前进的循环、卡住状态和弱完成证据 |
| Model-test alignment | 对照模型义务、外部代码 contract 和普通测试证据 |
| ModelMesh | 把过大的模型拆成父子证据，并检查父级信心是否使用了当前子级输出 |
| Child model reattachment | `v0.17.0` 要求父级 mesh 消费修复后的 child evidence id，并验证 input、output、state、side-effect 和导出 contract handoff |
| TestMesh | 检查父子验证层、旧证据、隐藏 skip、timeout，以及 routine/release gate |
| StructureMesh | 检查大 refactor 拆分、facade 兼容、依赖环、配置漂移和 parity 证据 |
| Code Structure Recommendation | 在写代码前，从模型推导 module、facade、state owner、side effect、config 和验证边界 |
| UI Flow Structure | 在视觉设计前，建模 UI 状态、控件、事件、失败、恢复、overlay、重复控件和信息显示 ownership |
| UI Text Hierarchy Blueprint | 按 state、region、role、semantic key、owner、priority、重复理由和 warning/error escalation 审查 UI 文案层级 |
| DevelopmentProcessFlow | 检查生命周期顺序、artifact 覆盖、验证新鲜度、最小重验证、archive readiness 和 release confidence |
| Model-Miss Review | 当运行时失败发生在 FlowGuard 通过之后，分类模型漏了什么，并补一个同类坏 case |

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

FlowGuard 有一个 kernel 思路和多个 satellite route。Kernel 先判断是否需要 model-first，再把任务路由到更窄的模型：

| Skill route | 适用场景 |
| --- | --- |
| `model-first-function-flow` | 任务涉及行为、状态、retry、idempotency、cache、queue、side effect 或 module boundary |
| `flowguard-model-test-alignment` | 需要对照模型义务和测试证据 |
| `flowguard-model-mesh` | 项目有多个本地模型、子证据或过大的模型表面 |
| `flowguard-test-mesh` | 测试证据分层、很慢、过期、被 skip、只在 release 跑，或分布在子套件 |
| `flowguard-structure-mesh` | 脚本、包、命令、公开 API 或 refactor 拆分需要兼容性治理 |
| `flowguard-code-structure-recommendation` | 写代码前，需要让 function-flow 模型推导 module 和 ownership boundary |
| `flowguard-ui-flow-structure` | UI control、state、event、overlay、恢复动作和信息 ownership 需要先建模 |
| `flowguard-development-process-flow` | done、archive、publish 或 release 信心取决于验证证据是否新鲜 |
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
| `docs/development_process_flow.md` | 生命周期、archive、publish 和 release gate |
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

## License

MIT. See `LICENSE`.
