# FlowGuard

| Public release | Schema | Runtime | License |
| --- | --- | --- | --- |
| `v0.1.1` | `1.0` | Python standard library only | MIT |

Chinese comes first. The second half is a full English mirror.

FlowGuard is a lightweight Python framework for **model-first function-flow
engineering**. It helps AI coding agents and human engineers build an
executable abstract model before changing production code, then checks whether
the design can produce duplicate side effects, impossible branches, broken
idempotency, cache mismatches, stuck states, or implementation behavior that
drifts away from the model.

FlowGuard is not an LLM wrapper. It does not call model APIs. It does not
estimate probabilities. It does not run Monte Carlo. It enumerates finite,
deterministic behavior that you explicitly model.

---

## 中文说明

### FlowGuard 是什么

FlowGuard 是一个给 AI coding agent 和工程师使用的功能流建模层。

在写真实代码之前，你先把系统行为抽象成一组 function blocks。每个
function block 都表达成：

```text
F: Input x State -> Set(Output x State)
```

意思是：一个功能块接收输入和当前状态，产生一个或多个可能的输出和新
状态。如果一个功能块可能产生多个结果，FlowGuard 不会抽样，也不会算概率，
而是把这些结果全部列出来。

多个 function blocks 可以组合成 workflow：

```text
Workflow = F_C o F_B o F_A
```

因为每个功能块都可能分支，所以 workflow 会形成执行树或执行图。FlowGuard
会穷举有限范围内的路径，并检查每条路径是否违反 invariant、场景预期、状态
所有权、幂等性、终止性或真实实现一致性。

### 为什么需要它

AI coding agent 很容易在局部修 bug 时破坏全局流程，例如：

- 给同一个对象重复打分；
- 给同一个 item 追加两条记录；
- 忘记 deduplication；
- retry 时重复发送副作用；
- cache 和 source of truth 不一致；
- 一个模块修改了另一个模块拥有的状态；
- 下游函数无法消费上游输出；
- 记录已经产生，但决策没有产生；
- 同一个对象同时出现 apply 和 ignore；
- workflow 有出口，但没有进展保证；
- 真实代码看起来能跑，但偏离了抽象设计。

FlowGuard 的目标不是替代单元测试，而是在写生产代码前，把这些 workflow-level
和 side-effect-level 问题先暴露出来。

### 它现在能检查什么

| 能力 | FlowGuard 做什么 |
| --- | --- |
| Function-flow model | 用 `Input x State -> Set(Output x State)` 表达功能块 |
| Workflow exploration | 展开多分支 workflow，保留每条 trace |
| Invariant checking | 检查重复记录、重复处理、矛盾决策、缓存不一致等硬约束 |
| Repeated input | 明确探索 `[A]`、`[A, A]`、`[A, B, A]` 这类重复输入 |
| Scenario sandbox | 把人工预期 oracle 和实际观察结果并排比较 |
| Counterexample trace | 输出能解释问题的失败路径 |
| Trace export | 把 trace / report 导出为 JSON-compatible 结构 |
| Conformance replay | 把抽象 trace replay 到真实实现，通过 adapter 比较行为 |
| Loop / stuck review | 检查 stuck state、bottom SCC、unreachable success |
| Progress checks | 检查有 escape edge 但没有进展保证的循环 |
| Contract checks | 检查前置条件、后置条件、读写边界、禁止写入和 traceability |
| Codex Skill | 提供 `model-first-function-flow` Skill，让 Codex 在改代码前先建模 |

### 典型工作流

```text
feature or bugfix request
  -> define external inputs
  -> define finite abstract state
  -> define function blocks
  -> define possible outputs
  -> define invariants
  -> run workflow exploration
  -> run scenario review
  -> inspect counterexample traces
  -> implement or modify production code
  -> replay representative traces against real code
  -> update the model when the architecture changes
```

这套流程特别适合：

- 有状态 workflow；
- deduplication；
- idempotency；
- retry；
- cache；
- queue；
- human review loop；
- AI/LLM decision pipeline 的抽象输出建模；
- 模块边界和状态所有权；
- 真实代码和抽象模型之间的一致性检查。

### 快速开始

FlowGuard 当前发布的是源码安装版本，还没有 PyPI 包。

```powershell
git clone https://github.com/liuyingxuvka/FlowGuard.git
cd FlowGuard
python -m pip install -e .
python -m flowguard schema-version
```

运行测试：

```powershell
python -m unittest discover -s tests
```

如果 `flowguard.exe` 不在 `PATH` 中，优先使用：

```powershell
python -m flowguard schema-version
```

### 运行示例

Looping workflow 示例展示 stuck state、bottom SCC、unreachable success 和
progress 问题：

```powershell
python examples/looping_workflow/run_loop_review.py
```

更多可运行示例见 [examples/](examples/)。

### 最小代码示例

```python
from dataclasses import dataclass

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow, Explorer


@dataclass(frozen=True)
class State:
    records: tuple[str, ...] = ()


class RecordItem:
    name = "RecordItem"
    accepted_input_type = str
    reads = ("records",)
    writes = ("records",)
    input_description = "item id"
    output_description = "record status"
    idempotency = "same item is recorded once"

    def apply(self, input_obj, state):
        if input_obj in state.records:
            yield FunctionResult("already_exists", state, "record_already_exists")
            return
        yield FunctionResult(
            "added",
            State(records=state.records + (input_obj,)),
            "record_added",
        )


def no_duplicate_records():
    def check(state, trace):
        if len(state.records) != len(set(state.records)):
            return InvariantResult.fail("duplicate records")
        return InvariantResult.ok()

    return Invariant("no_duplicate_records", "records are unique", check)


workflow = Workflow((RecordItem(),))
report = Explorer(
    initial_states=(State(),),
    external_inputs=("item-1",),
    workflow=workflow,
    invariants=(no_duplicate_records(),),
    max_sequence_length=2,
).run()

print(report.format_text())
```

### 和 Codex 一起使用

仓库内置 Codex Skill：

```text
.agents/skills/model-first-function-flow/
```

在另一个项目中，你可以让 Codex 使用这个 Skill：

```text
Use the model-first-function-flow skill before changing this workflow.
```

也可以把下面规则复制到目标项目的 `AGENTS.md`：

```text
For non-trivial tasks involving behavior, workflows, state, module boundaries,
retries, deduplication, idempotency, caching, repeated inputs, or repeated bugs,
use the model-first-function-flow skill before editing production code.
```

完整规则见：[docs/agents_snippet.md](docs/agents_snippet.md)。

Skill 里包含：

- 建模协议；
- invariant 示例；
- 最小 model template；
- run checks template；
- toolchain preflight helper；
- lightweight run log template。

### 适合谁

FlowGuard 适合：

- 想让 AI coding agent 改代码前先证明功能流设计的人；
- 经常遇到重复 side effect、retry、cache、dedup、状态边界问题的工程团队；
- 想把架构讨论从自然语言提醒推进到可执行模型的人；
- 需要在真实实现前审查 workflow 行为的人。

FlowGuard 不适合：

- 想直接调用 LLM API 的 prompt tool；
- 想做随机 property-based testing 的工具；
- 想替代所有 unit tests、integration tests 或 formal verification；
- 想一键证明完整生产系统正确性；
- 不愿意手写抽象状态、function block 和 invariants 的项目。

### 公开仓库包含什么

| 路径 | 内容 |
| --- | --- |
| [flowguard/](flowguard/) | 核心 Python package |
| [.agents/skills/model-first-function-flow/](.agents/skills/model-first-function-flow/) | Codex Skill |
| [docs/](docs/) | 概念、建模协议、conformance、scenario、loop、progress、contract 文档 |
| [examples/](examples/) | Runnable public examples |
| [tests/](tests/) | 公开测试 |
| [ROADMAP.md](ROADMAP.md) | 后续路线图 |

### 公开仓库不包含什么

这个公开仓库刻意不包含本地维护系统：

- 本地维护记录；
- 实验过程记录；
- 机器特定路径或配置；
- 认证材料、访问令牌或其他敏感配置；
- 大型内部实验输出。

公开版保留的是最小可用产品面：核心库、文档、Skill、示例和测试。

### 文档入口

- [docs/concept.md](docs/concept.md): 世界观和数学模型。
- [docs/modeling_protocol.md](docs/modeling_protocol.md): 建模流程。
- [docs/invariant_examples.md](docs/invariant_examples.md): invariant 模式。
- [docs/scenario_sandbox.md](docs/scenario_sandbox.md): expected vs observed 场景审查。
- [docs/conformance_testing.md](docs/conformance_testing.md): 抽象 trace replay 到真实代码。
- [docs/loop_detection.md](docs/loop_detection.md): stuck state 和 bottom SCC。
- [docs/progress_properties.md](docs/progress_properties.md): progress 和 escape-edge cycle。
- [docs/contract_composition.md](docs/contract_composition.md): function contract 和 ownership。
- [docs/refinement.md](docs/refinement.md): real state 到 abstract state 的 projection。
- [docs/project_integration.md](docs/project_integration.md): 在其他项目中接入 FlowGuard。

### 当前限制

- 只做确定性的有限枚举。
- 不做随机测试。
- 不依赖 Hypothesis。
- 不做概率模型。
- 不做 Monte Carlo。
- 不声称完整形式化证明。
- 不替代单元测试。
- conformance replay 需要用户手写 adapter。
- 当前没有 PyPI 发布。
- 当前没有稳定完整 CLI，只保留轻量 `python -m flowguard` 入口。

### License

MIT. See [LICENSE](LICENSE).

---

## English

### What FlowGuard Is

FlowGuard is a function-flow modeling layer for AI coding agents and engineers.

Before editing real production code, you describe the system as a set of
function blocks. Each function block is modeled as:

```text
F: Input x State -> Set(Output x State)
```

A block receives an input and the current abstract state, then produces one or
more possible outputs and new states. If a block may produce several outcomes,
FlowGuard does not sample them and does not assign probabilities. It enumerates
the possible outcomes you modeled.

Function blocks compose into workflows:

```text
Workflow = F_C o F_B o F_A
```

Because every block may branch, a workflow becomes an execution tree or graph.
FlowGuard explores the finite paths you define and checks each path against
invariants, scenario expectations, ownership rules, idempotency rules,
termination expectations, and implementation conformance.

### Why It Exists

AI coding agents often fix a local bug while damaging the global workflow. For
example, an agent may accidentally:

- score the same object twice;
- append duplicate records for the same item;
- forget deduplication;
- retry a side effect twice;
- let cache drift from the source of truth;
- let the wrong module mutate state it does not own;
- produce an output the downstream block cannot consume;
- create a record without a final decision;
- assign both apply and ignore to the same object;
- create a workflow that has an exit but no progress guarantee;
- write production code that runs but no longer matches the abstract design.

FlowGuard is not a replacement for unit tests. It is a pre-production modeling
layer for exposing workflow-level and side-effect-level defects before the code
change lands.

### What It Checks Today

| Capability | What FlowGuard does |
| --- | --- |
| Function-flow model | Represents blocks as `Input x State -> Set(Output x State)` |
| Workflow exploration | Expands branching workflows and keeps every trace |
| Invariant checking | Detects duplicate records, repeated processing, contradictions, cache mismatch |
| Repeated input | Explores sequences such as `[A]`, `[A, A]`, and `[A, B, A]` |
| Scenario sandbox | Compares human oracle expectations with observed results |
| Counterexample trace | Emits a readable path explaining a failure |
| Trace export | Exports traces and reports as JSON-compatible structures |
| Conformance replay | Replays abstract traces against real code through an adapter |
| Loop / stuck review | Finds stuck states, bottom SCCs, and unreachable success |
| Progress checks | Flags cycles with escape edges but no progress guarantee |
| Contract checks | Checks preconditions, postconditions, read/write ownership, forbidden writes, traceability |
| Codex Skill | Provides a `model-first-function-flow` Skill for model-first coding work |

### Typical Workflow

```text
feature or bugfix request
  -> define external inputs
  -> define finite abstract state
  -> define function blocks
  -> define possible outputs
  -> define invariants
  -> run workflow exploration
  -> run scenario review
  -> inspect counterexample traces
  -> implement or modify production code
  -> replay representative traces against real code
  -> update the model when the architecture changes
```

FlowGuard is especially useful for:

- stateful workflows;
- deduplication;
- idempotency;
- retry;
- cache;
- queue;
- human review loops;
- abstract modeling of AI/LLM decision outputs;
- module boundaries and state ownership;
- checking whether real code still conforms to an abstract model.

### Quick Start

FlowGuard is currently source-install only. It is not published on PyPI yet.

```powershell
git clone https://github.com/liuyingxuvka/FlowGuard.git
cd FlowGuard
python -m pip install -e .
python -m flowguard schema-version
```

Run tests:

```powershell
python -m unittest discover -s tests
```

If `flowguard.exe` is not on `PATH`, prefer:

```powershell
python -m flowguard schema-version
```

### Run Examples

The looping workflow example shows stuck states, bottom SCCs, unreachable
success, and progress issues:

```powershell
python examples/looping_workflow/run_loop_review.py
```

For more runnable examples, see [examples/](examples/).

### Minimal Python Sketch

```python
from dataclasses import dataclass

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow, Explorer


@dataclass(frozen=True)
class State:
    records: tuple[str, ...] = ()


class RecordItem:
    name = "RecordItem"
    accepted_input_type = str
    reads = ("records",)
    writes = ("records",)
    input_description = "item id"
    output_description = "record status"
    idempotency = "same item is recorded once"

    def apply(self, input_obj, state):
        if input_obj in state.records:
            yield FunctionResult("already_exists", state, "record_already_exists")
            return
        yield FunctionResult(
            "added",
            State(records=state.records + (input_obj,)),
            "record_added",
        )


def no_duplicate_records():
    def check(state, trace):
        if len(state.records) != len(set(state.records)):
            return InvariantResult.fail("duplicate records")
        return InvariantResult.ok()

    return Invariant("no_duplicate_records", "records are unique", check)


workflow = Workflow((RecordItem(),))
report = Explorer(
    initial_states=(State(),),
    external_inputs=("item-1",),
    workflow=workflow,
    invariants=(no_duplicate_records(),),
    max_sequence_length=2,
).run()

print(report.format_text())
```

### Use With Codex

This repository includes a Codex Skill:

```text
.agents/skills/model-first-function-flow/
```

In another project, ask Codex:

```text
Use the model-first-function-flow skill before changing this workflow.
```

You can also copy this rule into the target project's `AGENTS.md`:

```text
For non-trivial tasks involving behavior, workflows, state, module boundaries,
retries, deduplication, idempotency, caching, repeated inputs, or repeated bugs,
use the model-first-function-flow skill before editing production code.
```

See the full rule in [docs/agents_snippet.md](docs/agents_snippet.md).

The Skill includes:

- modeling protocol;
- invariant examples;
- minimal model template;
- run checks template;
- toolchain preflight helper;
- lightweight run log template.

### Who It Is For

FlowGuard is for:

- people who want AI coding agents to model behavior before editing code;
- teams that often deal with duplicate side effects, retry, cache, dedup, or state ownership;
- engineers who want executable architecture checks instead of prose-only reminders;
- projects that need workflow review before implementation.

FlowGuard is not for:

- prompt tools that directly call LLM APIs;
- random property-based testing;
- replacing all unit tests, integration tests, or formal verification;
- proving an entire production system correct with one command;
- projects that are unwilling to write abstract state, function blocks, and invariants.

### What The Public Repository Includes

| Path | Content |
| --- | --- |
| [flowguard/](flowguard/) | Core Python package |
| [.agents/skills/model-first-function-flow/](.agents/skills/model-first-function-flow/) | Codex Skill |
| [docs/](docs/) | Concept, modeling, conformance, scenario, loop, progress, and contract docs |
| [examples/](examples/) | Runnable public examples |
| [tests/](tests/) | Public test suite |
| [ROADMAP.md](ROADMAP.md) | Roadmap |

### What The Public Repository Does Not Include

This public repository intentionally excludes the local maintenance system:

- local maintenance records;
- experiment process notes;
- machine-specific paths or configuration;
- authentication material, access tokens, or other sensitive configuration;
- large internal experiment outputs.

The public surface is the minimal usable product: core library, docs, Skill,
examples, and tests.

### Documentation Map

- [docs/concept.md](docs/concept.md): worldview and mathematical model.
- [docs/modeling_protocol.md](docs/modeling_protocol.md): modeling process.
- [docs/invariant_examples.md](docs/invariant_examples.md): invariant patterns.
- [docs/scenario_sandbox.md](docs/scenario_sandbox.md): expected-vs-observed scenario review.
- [docs/conformance_testing.md](docs/conformance_testing.md): replay abstract traces against real code.
- [docs/loop_detection.md](docs/loop_detection.md): stuck states and bottom SCCs.
- [docs/progress_properties.md](docs/progress_properties.md): progress and escape-edge cycles.
- [docs/contract_composition.md](docs/contract_composition.md): function contracts and ownership.
- [docs/refinement.md](docs/refinement.md): projection from real state to abstract state.
- [docs/project_integration.md](docs/project_integration.md): connect FlowGuard to another repository.

### Current Limits

- Deterministic finite exploration only.
- No random testing.
- No Hypothesis dependency.
- No probability model.
- No Monte Carlo.
- No complete formal proof claim.
- Not a replacement for unit tests.
- Conformance replay requires a user-written adapter.
- No PyPI release yet.
- No full stable CLI yet, only a lightweight `python -m flowguard` entry.

### License

MIT. See [LICENSE](LICENSE).
