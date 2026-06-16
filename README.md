# FlowGuard

<!-- README HERO START -->
<p align="center">
  <img src="./assets/readme-hero/hero.png" alt="FlowGuard concept hero image" width="100%" />
</p>

<p align="center">
  <img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="120" />
</p>

<p align="center">
  <strong>A model-first guardrail for AI coding agents before small edits become large-project maintenance debt.</strong>
</p>
<!-- README HERO END -->

| Public release | Schema | Runtime | License |
| --- | --- | --- | --- |
| `v0.51.0` | `1.0` | Python standard library only | MIT |

English lead content comes first; a Chinese mirror follows below.

## Why FlowGuard Exists

AI coding agents are useful because they can move quickly through small edits. The failure mode appears when the project stops being small: the agent can keep adding code while the real workflow state is already wrong.

Common symptoms look familiar:

- a retry path runs twice and creates duplicate side effects;
- branches multiply until nobody knows which path still owns the state;
- tests pass, but they no longer prove the claim being made;
- a child fix is fresh, while the parent plan still trusts stale evidence;
- a UI has visible buttons, but the launch-to-terminal journey has no valid recovery path;
- a release, README, or "done" claim survives after later code, docs, tests, or peer writes invalidated it.

FlowGuard is built for that problem. It makes the risky transition explicit before the agent acts, runs a small executable state model, and turns hidden failure paths into counterexamples that can change the next engineering step.

It does not promise that software has no bugs. It helps prevent a specific maintenance disaster: AI agents continuing from an invalid state and piling more code, tests, or public claims on top of it.

## What FlowGuard Does

FlowGuard is a lightweight Python toolkit and AI-agent skill layer for model-first workflow checks. Any agent can use the method; Codex-compatible skills are provided as ready-to-install guidance, not as the boundary of the project.

The practical loop is:

```text
risky AI action -> explicit state model -> executable checks
-> counterexample trace -> revise plan, code, tests, UI, or claim
```

Instead of asking an agent to "be careful", FlowGuard asks the agent to name the state, inputs, outputs, side effects, ownership boundaries, and evidence gates that decide whether the next action is safe.

## The Core Model

Each function block is represented as:

```text
Input x State -> Set(Output x State)
```

That small shape is enough to expose many large-project problems:

- repeated inputs that should be idempotent;
- dead branches that return no legal output;
- multiple possible outputs that need explicit ownership;
- stale evidence after later artifact changes;
- remembered maintenance obligations that reopen when the same surface changes;
- parent/child model drift;
- invalid final claims after skipped or scoped validation.

FlowGuard explores finite traces inside the declared model and checks invariants, scenarios, progress properties, conformance expectations, evidence freshness, and closure boundaries. When a check fails, the important output is the counterexample path: the concrete state sequence that shows why the current plan should not continue unchanged.

## Start With Minimum Value

Most useful FlowGuard work should start compact, but the first model still
needs teeth:

```text
choose one risky boundary
-> name the protected error class
-> search public/local risk templates or record why none match
-> name Input, State, Output, side effects, completion evidence, and owners
-> write one invariant or scenario plus one known-bad case
-> run the check
-> inspect the counterexample
-> record template harvest closure: write, merge, link, or accepted not-harvestable
-> fix the model, plan, code, tests, UI, or claim
```

Only escalate when the risk boundary demands it: UI topology, code structure, test hierarchy, model/test alignment, parent/child model mesh, staged release evidence, architecture reduction, existing-model ownership, or model-miss repair.

## What You Can Design And Verify

| Work type | What FlowGuard helps design | What it checks |
| --- | --- | --- |
| Development process | staged route, legal next actions, validation gates, stale-evidence reset, peer-write invalidation, done and release readiness | skipped gates, stale validation, progress-only evidence, invalid completion claims |
| UI flow | persistent regions, contextual panels, visible controls, functional capability coverage, visible surface, user task coverage, human-operability, overlays, recovery paths, display ownership, duplicate-control rules | missing required UI functions, launch-to-terminal journeys, unavailable controls, missing disabled reasons, orphan primary controls, confusing affordance, missing recovery, duplicate actions, evidence-kind gaps |
| Code structure | module split, facade boundary, state owner, side-effect owner, config owner, validation owner | ownership leaks, dependency cycles, facade drift, config drift, missing parity evidence |
| Architecture reduction | observable contract, duplicate implementation candidates, safe target action | whether handlers, adapters, branches, modules, or validation layers can shrink without changing observable behavior |
| Test strategy | routine and release test layers, parent/child suites, timeout boundaries, stale and hidden evidence rules | skipped tests, release-only evidence, broad/slow direct checks, stale passes, wrong-provenance evidence |
| Model mesh and bug repair | parent/child boundaries, reattachment gates, sibling-impact review, same-class bad cases | child evidence freshness, parent consumption, analogous defect risks, same-class test evidence |
| Release and public claims | evidence ledger, claim-chain boundary, publish readiness | whether the public claim is supported by current model, code, test, mesh, freshness, and risk evidence |

This is the core product: FlowGuard turns a vague workflow, UI journey, refactor, test strategy, or release process into a small state machine with explicit failure traces. The counterexample is not just a bug report; it is design feedback that says which state, gate, owner, or evidence rule must change before work continues.

## What FlowGuard Is Not

FlowGuard is not an LLM wrapper, a prompt trick, a probability engine, a Monte Carlo simulator, or a replacement for ordinary tests.

It is a structural preflight layer. Tests still verify production code. Code review still matters. UI polish and browser/device behavior still need real UI review. FlowGuard sits earlier: it asks whether the agent's intended transition is coherent before the transition becomes code, tests, UI, or a public confidence claim.

## When To Use It

Use FlowGuard when order, state, ownership, side effects, UI availability, role handoff, or evidence freshness can change whether the plan is actually safe.

Good fits:

- AI-agent coding work with multiple stages or handoffs;
- retries, deduplication, cache refresh, ingestion, or repeated job processing;
- refactors where public entrypoints must remain compatible;
- UI flows where visible controls do not guarantee legal recovery paths;
- tests or release checks where old evidence can be mistaken for current proof;
- parent/child models where one green result should not automatically make the parent green.

Bad fits:

- one-line typo fixes;
- formatting-only edits;
- tasks where no state, side effect, ordering, or evidence boundary matters;
- claims that need statistical truth rather than structural workflow checks.

## Quick Start

```powershell
git clone https://github.com/liuyingxuvka/FlowGuard.git
cd FlowGuard
python -m pip install -e .
python -m flowguard schema-version
python -m flowguard self-review
```

Adopt FlowGuard into another project so future agents can find the repository, version record, and project rules:

```powershell
python -m flowguard project-adopt --root <target-project>
python -m flowguard project-audit --root <target-project>
python -m flowguard project-upgrade --root <target-project>
```

Useful template entry points:

```powershell
python -m flowguard project-template
python -m flowguard project-adoption-template
python -m flowguard risk-template-library-template
python -m flowguard risk-template-search "completion evidence"
python -m flowguard risk-template-harvest-review --disposition duplicate_linked --linked-template-id completion_requires_evidence
python -m flowguard plan-detailing-template
python -m flowguard model-test-alignment-template
python -m flowguard existing-model-preflight-template
python -m flowguard model-similarity-template
python -m flowguard risk-evidence-ledger-template
python -m flowguard maintenance-scan-template
python -m flowguard closure-contract-template
python -m flowguard code-structure-recommendation-template
python -m flowguard ui-flow-structure-template
python -m flowguard development-process-flow-template
python -m flowguard workflow-step-contracts-template
python -m flowguard test-mesh-template
python -m flowguard structure-mesh-template
python -m flowguard topology-hazard-template
```

Run focused examples:

```powershell
python examples/flowguard_product_boundary/run_review.py
python examples/hierarchical_model_mesh/run_review.py
python examples/risk_evidence_ledger/run_checks.py
python examples/job_matching/run_checks.py
```

## Minimal Python Sketch

```python
from dataclasses import dataclass, replace

from flowguard import FunctionResult, Invariant, Workflow
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite


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


class BrokenProcessJob(ProcessJob):
    name = "broken_process_job"

    def apply(self, input_obj: Input, state: State):
        return [
            FunctionResult(
                output="processed",
                new_state=replace(
                    state,
                    processed=state.processed + (input_obj.job_id,),
                    side_effects=state.side_effects + 1,
                ),
                label="duplicate_processing",
            )
        ]


workflow = Workflow((ProcessJob(),), name="retry_deduplication")
broken_workflow = Workflow((BrokenProcessJob(),), name="retry_deduplication_broken")
invariants = (
    Invariant(
        name="side_effect_once",
        description="The same job may not create duplicate side effects.",
        predicate=lambda state, trace: state.side_effects <= len(set(state.processed)),
    ),
)

report = run_formal_workflow_suite(
    "retry_deduplication",
    (
        FormalWorkflowCase(
            "correct_retry_deduplication",
            workflow,
            True,
            required_labels=("first_processing", "deduplicated_retry"),
        ),
        FormalWorkflowCase(
            "broken_duplicate_side_effect",
            broken_workflow,
            False,
            protected_error_class="duplicate_side_effect",
        ),
    ),
    initial_states=(State(),),
    external_inputs=(Input("A"),),
    invariants=invariants,
    max_sequence_length=2,
    protected_error_class="duplicate_side_effect",
)
print(report.format_text())
```

## Skill Routes

FlowGuard has one kernel and several satellite skills. Development-process work
uses one front door with internal modes; use the smallest route that owns the
actual risk:

| Skill route | Use it when |
| --- | --- |
| `model-first-function-flow` | ordinary behavior/state modeling, unclear route selection, or cross-route coordination |
| `flowguard-existing-model-preflight` | existing modeled-system work should first identify model ownership, reuse/extend decisions, and duplicate-boundary risk |
| `flowguard-development-process-flow` | rough plans, multi-skill/tool setup, staged development, archive, publish, release, or done confidence enter the development-process simulator; it may delegate to PlanDetailing or AgentWorkflowRehearsal |
| `flowguard-plan-detailing-compiler` | explicit or simulator-delegated `plan_detailing` mode needs scope, state, side effects, evidence, receipts, rework, and claim boundaries |
| `flowguard-ui-flow-structure` | UI controls, visible surface, required functional capabilities, task coverage, human-operability, launch-to-terminal journeys, overlays, recovery paths, information ownership, and runnable evidence kinds need modeling |
| `flowguard-code-structure-recommendation` | a function-flow model should derive module, facade, state-owner, side-effect, config, and validation boundaries |
| `flowguard-structure-mesh` | a script, package, command, public API, or refactor split needs facade compatibility and parity evidence |
| `flowguard-test-mesh` | validation is layered, slow, stale, skipped, release-only, or split across child suites |
| `flowguard-model-test-alignment` | model obligations, code contracts, code-boundary observations, and test evidence need direct comparison |
| `flowguard-model-mesh` | parent/child model evidence, sibling impact, or oversized model surfaces need mesh governance |
| `flowguard-model-topology-hazard-review` | a locally green model may still imply repeatable future-use hazards before broad confidence |
| `flowguard-architecture-reduction` | model-equivalent handlers, adapters, modules, branches, or validation layers may be safely contracted |
| `flowguard-model-miss-review` | runtime, tests, replay, logs, or manual validation failed after a FlowGuard model passed |

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
| `docs/concept.md` | short conceptual introduction |
| `docs/modeling_protocol.md` | core model-first protocol |
| `docs/api_surface.md` | public Python API overview |
| `docs/invariant_examples.md` | examples of useful invariants |
| `docs/development_process_flow.md` | staged development, validation freshness, archive, publish, and release gates |
| `docs/ui_flow_structure.md` | UI interaction and structure modeling |
| `docs/code_structure_recommendation.md` | model-derived code structure recommendations |
| `docs/structure_mesh.md` | refactor and module split governance |
| `docs/test_evidence_mesh.md` | layered validation and evidence freshness |
| `docs/model_test_alignment.md` | model obligation and test evidence alignment |
| `docs/model_mesh_protocol.md` | parent/child model mesh governance |
| `docs/model_topology_hazard_review.md` | topology-grounded future-use hazard review |
| `docs/model_similarity_consolidation.md` | model-to-model relation review and consolidation handoffs |
| `docs/flowguard_closure_contract.md` | closure contract for complete FlowGuard use |
| `docs/risk_evidence_ledger.md` | risk-to-model-to-code-to-evidence confidence boundary |
| `docs/runtime_gateway_adoption.md` | runtime gateway adoption levels and critical-state writer inventory |

## Repository Layout

```text
flowguard/     Core library, review helpers, templates, mesh routes, CLI
examples/      Small executable models and public self-reviews
docs/          Protocols, API notes, examples, and adoption guidance
tests/         Focused regression tests for the public helpers
assets/        README hero image and generation notes
```

## Public Boundary

This repository is designed to be useful as a public starter and reference implementation. It includes the library, examples, protocol docs, public templates, and AI-agent skill material, including Codex-compatible skills.

It does not include private project logs, personal predictive knowledge, credentials, customer data, or claims that every real system is covered by the model. A FlowGuard pass means the declared model obligations passed. It does not mean the whole project is correct.

## License

MIT. See `LICENSE`.

---

## 中文说明

FlowGuard 是给 AI 编程 agent 用的 model-first guardrail：在小改动逐渐变成大项目维护债之前，先把危险的状态转移建模并检查。

## 为什么需要 FlowGuard

AI 编程 agent 在小代码、小软件、小改动里很好用。真正危险的地方通常出现在项目变大以后：agent 还能继续写代码，但实际 workflow 的状态、证据、ownership 或发布结论已经错了。

常见症状包括：

- retry 路径跑了两次，产生重复 side effect；
- 分支越来越多，没人知道哪条路径还拥有真实 state；
- 测试通过了，但已经不再证明当前声明；
- 子模型刚修好，父级计划却还在信任旧证据；
- UI 有可见按钮，但从启动到终态的 journey 没有合法恢复路径；
- release、README 或 done 声明在后续代码、文档、测试或 peer 写入后仍然留着。

FlowGuard 就是为这个问题设计的。它在 agent 动手之前，把危险转移写成明确的小型状态模型，运行可执行检查，并把隐藏失败路径变成能改变下一步工程动作的 counterexample。

它不承诺软件没有 bug。它防的是一种更具体的维护灾难：AI agent 带着无效状态继续推进，把更多代码、测试或公开声明堆在错误计划上。

## FlowGuard 做什么

FlowGuard 是轻量 Python 工具包，也是通用 AI-agent skill layer。任何 agent 都可以用这套方法；Codex-compatible skills 只是现成接入方式，不是项目边界。

实际循环是：

```text
危险 AI 行动 -> 显式状态模型 -> 可执行检查
-> counterexample trace -> 修改计划、代码、测试、UI 或声明
```

它不是让 agent “小心一点”，而是要求 agent 说清楚 state、input、output、side effect、ownership boundary 和 evidence gate，因为这些才决定下一步是否安全。

## 核心模型

每个 function block 表示为：

```text
Input x State -> Set(Output x State)
```

这个小结构足以暴露很多大项目问题：

- 重复 input 是否应该幂等；
- 死分支是否没有合法 output；
- 多个可能 output 是否有明确 ownership；
- 后续 artifact 变化后证据是否过期；
- 记住的维护义务是否会在同一风险面被再次改动时自动重开；
- 父子模型证据是否漂移；
- final claim 是否在跳过验证或 scoped 验证后仍被接受。

FlowGuard 在声明的有限模型里探索 trace，并检查 invariant、scenario、progress、conformance、evidence freshness 和 closure boundary。失败时，最重要的输出是 counterexample path：一条具体状态序列，说明当前计划为什么不能原样继续。

## 从小开始

大多数 FlowGuard 使用入口可以很小，但模型本身仍要有牙齿：

```text
选择一个风险边界
-> 命名要防住的错误类型
-> 搜 public/local risk template；没有匹配就写清楚原因
-> 命名 Input、State、Output、side effect、完成证据和 owner
-> 写一个 invariant 或 scenario，并放入一个代表性 known-bad case
-> 运行检查
-> 证明这个 known-bad case 已经会被抓住
-> 关闭 template harvest：写入、合并、链接，或接受不可 harvest 的理由
-> 修模型、计划、代码、测试、UI 或声明
```

只有风险边界真的需要时，才升级到高级路线：UI 拓扑、代码结构、测试层级、model/test alignment、parent/child model mesh、分阶段发布证据、architecture reduction、existing-model ownership 或 model-miss repair。

## 它能设计并验证什么

| 工作类型 | FlowGuard 帮你设计什么 | 它检查什么 |
| --- | --- | --- |
| 开发流程 | staged route、合法 next action、validation gate、stale-evidence reset、peer-write invalidation、done/release readiness | skipped gate、旧验证、progress-only evidence、无效完成声明 |
| UI flow | 持久区域、上下文 panel、可见控件、可见表面、用户任务覆盖、人类可操作性、overlay、恢复路径、display ownership、重复控件规则 | launch-to-terminal journey、不可用控件、缺失 disabled reason、孤立主控件、混乱 affordance、缺失恢复、重复动作、evidence kind 缺口 |
| 代码结构 | module split、facade boundary、state owner、side-effect owner、config owner、validation owner | ownership leak、dependency cycle、facade drift、config drift、缺失 parity evidence |
| 架构缩减 | observable contract、重复实现 candidate、安全 target action | handler、adapter、branch、module 或 validation layer 能否在不改变可观察行为的前提下收缩 |
| 测试策略 | routine/release test layer、父子 suite、timeout 边界、旧证据和隐藏证据规则 | skipped test、release-only evidence、过宽/过慢直接检查、旧 pass、来源不对的 evidence |
| Model mesh 和 bug 修复 | 父子边界、reattachment gate、sibling-impact review、same-class bad case | child evidence freshness、parent consumption、analogous defect risk、same-class test evidence |
| 发布和公开声明 | evidence ledger、claim-chain boundary、publish readiness | 公开声明是否被当前 model、code、test、mesh、freshness 和 risk evidence 支撑 |

这才是 FlowGuard 的核心产品：把模糊的 workflow、UI journey、refactor、test strategy 或 release process 变成小型状态机，并给出明确失败路径。counterexample 不是单纯 bug report，而是设计反馈：它告诉你哪个 state、gate、owner 或 evidence rule 必须先改，工作才能继续。

## FlowGuard 不是什么

FlowGuard 不是 LLM wrapper，不是 prompt trick，不是概率引擎，不是 Monte Carlo simulator，也不是普通测试的替代品。

它是结构化预检层。测试仍然要验证真实代码，code review 仍然重要，UI polish 和浏览器/设备行为仍然需要真实 UI review。FlowGuard 更早一步：在转移变成代码、测试、UI 或公开信心声明之前，先检查这个转移是否自洽。

## 什么时候用

当顺序、状态、ownership、side effect、UI availability、role handoff 或 evidence freshness 会改变计划是否安全时，用 FlowGuard。

适合：

- 有多个阶段或 handoff 的 AI-agent coding work；
- retry、deduplication、cache refresh、ingestion 或重复 job processing；
- 公开入口必须兼容的 refactor；
- 可见控件不等于合法恢复路径的 UI flow；
- 旧 evidence 可能被误当作当前 proof 的测试或发布检查；
- 一个 child green 不应该自动让 parent green 的父子模型。

不适合：

- 一行 typo；
- 纯格式修改；
- 没有 state、side effect、顺序或 evidence boundary 的任务；
- 需要统计事实而不是结构化 workflow 检查的声明。

## 快速开始

```powershell
git clone https://github.com/liuyingxuvka/FlowGuard.git
cd FlowGuard
python -m pip install -e .
python -m flowguard schema-version
python -m flowguard self-review
```

把 FlowGuard 接入另一个项目，让后续 agent 能看到仓库地址、版本记录和项目规则：

```powershell
python -m flowguard project-adopt --root <target-project>
python -m flowguard project-audit --root <target-project>
python -m flowguard project-upgrade --root <target-project>
```

常用模板入口：

```powershell
python -m flowguard project-template
python -m flowguard project-adoption-template
python -m flowguard risk-template-library-template
python -m flowguard risk-template-search "completion evidence"
python -m flowguard risk-template-harvest-review --disposition duplicate_linked --linked-template-id completion_requires_evidence
python -m flowguard plan-detailing-template
python -m flowguard model-test-alignment-template
python -m flowguard existing-model-preflight-template
python -m flowguard model-similarity-template
python -m flowguard risk-evidence-ledger-template
python -m flowguard maintenance-scan-template
python -m flowguard closure-contract-template
python -m flowguard code-structure-recommendation-template
python -m flowguard ui-flow-structure-template
python -m flowguard development-process-flow-template
python -m flowguard workflow-step-contracts-template
python -m flowguard test-mesh-template
python -m flowguard structure-mesh-template
python -m flowguard topology-hazard-template
```

运行示例：

```powershell
python examples/flowguard_product_boundary/run_review.py
python examples/hierarchical_model_mesh/run_review.py
python examples/risk_evidence_ledger/run_checks.py
python examples/job_matching/run_checks.py
```

## Skill 架构

FlowGuard 有一个 kernel 和多个 satellite skill。开发流程类工作先走一个统一入口和内部模式；选择真正拥有当前风险的最小路线：

| Skill route | 适用场景 |
| --- | --- |
| `model-first-function-flow` | 普通行为/状态建模、路线不清楚或跨路线协调 |
| `flowguard-existing-model-preflight` | 已有模型系统里的工作要先找到 model owner、复用/扩展判断和重复 boundary 风险 |
| `flowguard-development-process-flow` | 粗计划、多技能/工具安排、staged development、archive、publish、release 或 done confidence 先进入 development-process simulator；需要时再委托 PlanDetailing 或 AgentWorkflowRehearsal |
| `flowguard-plan-detailing-compiler` | 显式调用或 simulator 委托的 `plan_detailing` 模式需要明确 scope、state、side effect、evidence、receipt、rework 和 claim boundary |
| `flowguard-ui-flow-structure` | UI control、可见表面、必需功能能力、任务覆盖、人类可操作性、launch-to-terminal journey、overlay、恢复路径、信息 ownership 和 runnable evidence kind 需要建模 |
| `flowguard-code-structure-recommendation` | function-flow 模型要推导 module、facade、state-owner、side-effect、config 和 validation boundary |
| `flowguard-structure-mesh` | 脚本、包、命令、公开 API 或 refactor 拆分需要 facade compatibility 和 parity evidence |
| `flowguard-test-mesh` | 验证分层、很慢、过期、被 skip、只在 release 跑，或分布在 child suite |
| `flowguard-model-test-alignment` | 需要直接对照 model obligation、code contract、code-boundary observation 和 test evidence |
| `flowguard-model-mesh` | parent/child model evidence、sibling impact 或过大 model surface 需要 mesh governance |
| `flowguard-model-topology-hazard-review` | 本地 green 模型在广泛信心前仍可能暗示可复发的未来使用风险 |
| `flowguard-architecture-reduction` | 模型等价的 handler、adapter、module、branch 或 validation layer 可能可以安全收缩 |
| `flowguard-model-miss-review` | runtime、test、replay、log 或人工验证在 FlowGuard 模型通过后仍然失败 |

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
| `docs/concept.md` | 简短概念介绍 |
| `docs/modeling_protocol.md` | 核心 model-first 协议 |
| `docs/api_surface.md` | 公开 Python API 概览 |
| `docs/invariant_examples.md` | 常用 invariant 示例 |
| `docs/development_process_flow.md` | staged development、validation freshness、archive、publish 和 release gate |
| `docs/ui_flow_structure.md` | UI interaction 和结构建模 |
| `docs/code_structure_recommendation.md` | 模型推导代码结构建议 |
| `docs/structure_mesh.md` | refactor 和 module split 治理 |
| `docs/test_evidence_mesh.md` | 分层验证和证据新鲜度 |
| `docs/model_test_alignment.md` | 模型义务和测试证据对齐 |
| `docs/model_mesh_protocol.md` | parent/child model mesh 治理 |
| `docs/model_topology_hazard_review.md` | 从模型拓扑推断未来使用风险的审查 |
| `docs/model_similarity_consolidation.md` | model-to-model 关系审查和 consolidation handoff |
| `docs/flowguard_closure_contract.md` | 完整 FlowGuard 使用的 closure contract |
| `docs/risk_evidence_ledger.md` | risk-to-model-to-code-to-evidence 信心边界 |
| `docs/runtime_gateway_adoption.md` | runtime gateway adoption level 和 critical-state writer inventory |

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

它不包含私有项目日志、个人 predictive knowledge、credential、客户数据，也不声称模型覆盖了所有真实系统。FlowGuard 通过只表示声明的模型义务通过，不表示整个项目已经正确。

## 许可证

MIT. See `LICENSE`.
