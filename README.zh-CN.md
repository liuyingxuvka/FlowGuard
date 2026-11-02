# FlowGuard

<p align="center">
  <img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" />
</p>

<p align="center"><strong>AI 辅助开发的“软件 DNA”：一棵随代码演进的模型树，包含代码归属、关键流程的可执行模型、测试和计划改动的目标。</strong></p>

[English](./README.md)

FlowGuard 用自己的地图和模型维护本仓库（`.flowguard/map.json`、`.flowguard/models/`）。模型和适用边界见[概念说明](docs/concept.md)。


## 它做什么

AI 擅长局部修改，但每开一个新会话都要重新弄清：软件由哪些部分组成、这件事归谁管、改这里会影响哪里？
FlowGuard 在项目里保存三样东西：

1. **地图** `.flowguard/map.json`：各个组件、它们的职责、拥有的状态、副作用、文件、入口、依赖、
   测试和模型。会话开始或恢复时先运行 `python -m flowguard status`，用
   `python -m flowguard where NAME` 查找代码、负责者和调用者。
2. **模型**：关键流程（重试、幂等、缓存、顺序、金额、权限、多步骤流程）的小型可执行模型，形式是
   `输入 x 状态 -> 一组(输出 x 状态)`。FlowGuard 在边界内穷举所有输入序列，给出反例，检查已知的坏版本
   一定会失败，并把模型轨迹放到真实代码上回放比对（一致性检查）。
3. **目标**（旧路线，保留到 v1.0.0）：一次旧模型改动计划中的地图和模型；正常改动不需要目标。

地图和模型是一棵树。根节点和组件节点从代码推出，始终生效；任务需要时才在组件下添加行为模型，测试挂在同样的节点上。
`python -m flowguard read --mermaid` 画出这棵树。

当前树保存在 `.flowguard/map.json` 和 `.flowguard/models/`。正常改动就是一起改代码和测试、跑项目的测试，
再用自己的话写一次提交；改动来自主人存下的需求时，加一行 `Request: R<n>`。

每次检查都会对照地图和代码。真正的问题（循环 import、层级违规、缺少模型锚点）是错误；只说明手写地图落后于代码的情况（文件没有负责者、描述过期、依赖没声明或没有证据）只是信息，永远不会让检查失败。
历史保存在 git 里。

## 五分钟上手

```bash
pip install -e .                                          # 引擎，只依赖 Python 标准库
# 或从 GitHub：python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git@v0.72.0"；PyPI 上名为 flowguard 的包是另一个项目
python scripts/install_skill.py --target ~/.claude/skills # 给 AI 安装技能（或 $CODEX_HOME/skills）

cd your-project
python -m flowguard status                              # 1. 开始或接着做：主人最近的话和未完成的工作
python -m flowguard req add owner-message.txt --id R1   # 2. 把主人的原话按字节原样存一次
python -m flowguard where place_order                   # 3. 找到代码、它的负责者和调用者
python -m pytest -q tests/test_orders.py                # 4. 代码和测试一起改；跑项目自己的测试
git add -A && git commit -m "Charge each order once" -m "Request: R1"   # 5. 用自己的话提交一次
```

这就是完整的流程，项目不需要地图、模型或目标。旧地图（`map scan`、`map check`、`map confirm`）、旧模型和
target 命令都是可选的，保留到 v1.0.0；[概念说明](docs/concept.md)介绍它们。

```powershell
python scripts/install_skill.py --target "$env:USERPROFILE\.claude\skills"
# Codex：先设置 CODEX_HOME；不要使用未设置的变量。
python scripts/install_skill.py --target "$env:CODEX_HOME\skills"
```

## 日常命令

| 什么时候 | 命令 | 作用 |
| --- | --- | --- |
| 会话开始或恢复 | `python -m flowguard status` | 项目的静态事实，以及什么会让 release 和 CI 失败 |
| 主人提出要求 | `python -m flowguard req add <file\|-> --id <id>` | 把主人自己的话原样存一次 |
| 旧的目标路线（保留到 v1.0.0） | `python -m flowguard target`（`start "<goal>"` \| `add <id>` \| `check` \| `promote` \| `drop`） | 计划旧模型的改动；正常改动不需要目标 |
| 旧的检查（保留到 v1.0.0） | `python -m flowguard change` | 校验地图和代码；只列出受影响的测试和模型 |
| 发布之前 | `python -m flowguard release` | 严格检查、架构错误、重跑全部模型、流程模型的完整检查 |
| 新模型或采用流程 | `python -m flowguard template --list` | 选择 `behaviour`、`validator`、`ui-journey`，或用 `adoption` 生成仓库规则 |

## 流程模型

流程模型是一次改动涉及的那部分设计，写成 `.flowguard/flow/<name>.py` 里的一台小机器：几个字段、改变它们的动作，
以及主人的要求所作的承诺（`from flowguard.flow import Model, need`，每个文件一个模型，以 `MODEL = m` 结尾）。
`check` 在每个能到达的状态里尝试每个动作，报告哪里会卡住、什么永远不会发生、哪种顺序会打破哪条承诺，每条都附最短路径
和背后的要求。写模型的一页说明是 [flowguard/flow/HOWTO.md](./flowguard/flow/HOWTO.md)，安装的包里也有。

| 命令 | 作用 |
| --- | --- |
| `python -m flowguard check` | 探索每个流程模型；第一行是结论；退出码 0 无问题，1 有冲突，2 模型错误，3 未知（搜索到上限），4 仍在运行 |
| `python -m flowguard check --full` | 另外故意把每个模型改坏，看它的检查能否抓到；有可互换对象的模型再不做改名约简地探索一遍 |
| `python -m flowguard show` | 把冲突画成流程图，没有冲突时画出相对 HEAD 的改动（`show MODEL`、`show C-...`、`--before REV`） |

`check` 最多等 `--wait` 秒（默认 90）就返回。还在运行（RUNNING）的工作会再保留 `--keep` 秒，用同一条命令接着做。
`--json` 只打印一行。冲突记在 `.flowguard/conflicts.json`（要提交）：`status` 显示未解决的冲突，`release` 运行
`check --full`。画图需要装了 Playwright 的 node；没有时 `show` 写出 Mermaid 文本。

## 找源码和文字原文

寻找源码或负责者需要多跳 grep 时，可按需使用静态查询（FlowGuard 0.71.1+）：

| 命令 | 查看内容 |
| --- | --- |
| `python -m flowguard where NAME` | 源码、负责者和调用方 |
| `python -m flowguard where` | 精简的模块概览 |
| `python -m flowguard where --flow` | 静态调用关系；加 NAME 可缩小范围 |
| `python -m flowguard where --arch` | 架构和有源码依据的建议 |
| `python -m flowguard where --text` | 文字与引用摘要 |
| `python -m flowguard where --keyflows` | 共享状态和文件写入位置 |

按需加 `--root DIR` 或 `--json`。文字查询可在 `--text` 后选 FILE、`source:<id>`、`group:<id>` 或 `"text:<literal phrase>"`，读取原文及可获得的 Git 来源。默认只给每个列表最相关的几行，写明省略了多少，并给出下一查的命令；`--all` 给出全部。字面搜索按不区分大小写的子串匹配。`--at REF` 同时读取该 Git 版本的文字和代码。

这些查询不运行应用、模型或测试；缺少执行记录时明确未知。字面匹配只是候选，不自动作语义判决，也不阻断改动；模型和独立规则测试仍负责验证行为。既有命令、64 个公开导出和地图格式保持兼容。

## 能做的事

下面这些用的是旧地图、旧模型和 target 命令：可选，保留到 v1.0.0，正常改动不需要。

| 原来的专项名 | 现在怎么做 |
| --- | --- |
| behavior-commitment | 给对外承诺唯一负责者、真实代码锚点和测试；建模备用路径。 |
| architecture-reduction | 在目标中删除或合并节点；保住公开承诺，检查无引用的代码。 |
| code-structure | 在目标中新增或拆分负责者；文件、状态、副作用和入口各有唯一归属。 |
| contract-exhaustion | 用 `validator` 节点检查有限的接受和拒绝用例。 |
| field-lifecycle | 在目标中描述改名或退役字段，检查新旧读取方。 |
| model-mesh | 用 `PARENT` 嵌套模型；子模型交接时按需用状态投影、有限的 `OUTPUTS` 和 `HANDOFF`。 |
| model-test | 用 `IMPLEMENTED_BY` 和 `TESTED_BY` 绑定规则，运行 `map models --tests`。 |
| test-mesh | 用 `release --shards N`；每个分片跑若干棵完整测试子树，每个收集到的测试恰好运行一次。 |
| ui-flow | 用 `ui-journey` 节点检查状态和旅程，再配合人工界面清单。 |

见[树的操作](.agents/skills/flowguard/references/routes.md)和
[模型配方](.agents/skills/flowguard/references/model_recipes.md)。

## 模型能抓住什么（真实例子）

`tests/fixtures/flowguard_map/order_placement.py`：客户端用同一个订单号重试，导致重复扣款。单元测试是绿的；
模型的一致性回放失败，给出两步反例 `Place(o1), Place(o1) -> charges=('o1','o1')`。为了让它通过而删掉不变量
也不行：“已知坏版本通过了：不变量抓不住它”。

## 它证明不了什么

模型只证明它声明的有限边界；地图描述的是当前这次提交；自动发现是启发式的。FlowGuard 不能代替测试、
代码评审和线上监控，也不会找出全局最优的架构。它维护一棵和代码、测试绑定的模型树。

## 仓库结构

- `flowguard/` 引擎、节点种类和计算出的面；`flowguard/map/` 地图、目标、自动发现和证明层；
  `flowguard/flow/` `check` 和 `show` 背后的流程模型引擎
- `.agents/skills/flowguard/` 给 AI 用的技能
- `.flowguard/` FlowGuard 自己的地图和模型（它用自己维护自己）
- `examples/` 可运行的教学模型；`docs/` 长篇说明

许可证：MIT
