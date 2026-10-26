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
   测试和模型。新会话用几千 token 读完整张地图，就知道该看哪里。
2. **模型**：关键流程（重试、幂等、缓存、顺序、金额、权限、多步骤流程）的小型可执行模型，形式是
   `输入 x 状态 -> 一组(输出 x 状态)`。FlowGuard 在边界内穷举所有输入序列，给出反例，检查已知的坏版本
   一定会失败，并把模型轨迹放到真实代码上回放比对（一致性检查）。
3. **目标**：一次行为或结构改动计划中的地图和模型；先实现并检查计划，再提升为当前模型。

地图和模型是一棵树。根节点和组件节点从代码推出，始终生效；任务需要时才在组件下添加行为模型，测试挂在同样的节点上。
`python -m flowguard read --mermaid` 画出这棵树。

当前树保存在 `.flowguard/map.json` 和 `.flowguard/models/`；计划中的改动保存在 `.flowguard/target/`，一次只有一个目标。
行为或结构要变时，先写目标，再让代码和测试符合目标。
`target check` 没有 ERROR 或 TO-DO 后，用 `target promote` 替换当前树并删除目标目录。

地图和代码互相校验：每个源文件恰好属于一个组件；入口、流程步骤和模型文件必须真实存在；每个真实的 import 都必须声明；确认组件时会记下它文件的指纹，代码一改就自动标成“过期”，直到有人重新读过并确认。
历史保存在 git 里。

## 五分钟上手

```bash
pip install -e .                                          # 引擎，只依赖 Python 标准库
# 或从 GitHub：python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git@<tag>"；PyPI 上名为 flowguard 的包是另一个项目
python scripts/install_skill.py --target ~/.claude/skills # 给 AI 安装技能（或 $CODEX_HOME/skills）

cd your-project
python -m flowguard map scan              # 1. 草拟组件，按 import 猜测试（默认最多 40 个组件）
python -m flowguard map discover          # 单独查看路由、命令、副作用和状态写入者
python -m flowguard map digest all        # 2. 接口摘要，签名、赋值和文档；大小随项目变化
#   编辑 .flowguard/map.json：合并/拆分组件，写 summary、职责、层级……
python -m flowguard map deps --write      # 3. 从真实 import 生成依赖
python -m flowguard map check             # 4. 修到 0 个错误
python -m flowguard map confirm all       # 5. 地图成为当前版本
python -m flowguard map lint              # 6. 架构审查
```

```powershell
python scripts/install_skill.py --target "$env:USERPROFILE\.claude\skills"
# Codex：先设置 CODEX_HOME；不要使用未设置的变量。
python scripts/install_skill.py --target "$env:CODEX_HOME\skills"
```

## 日常命令

| 什么时候 | 命令 | 作用 |
| --- | --- | --- |
| 会话开始 | `python -m flowguard read` / `read --find 关键词` | 读地图；加代码前先找已有的负责者 |
| 改行为或结构 | `python -m flowguard target`（`start "<goal>"` \| `add <id>` \| `check` \| `promote` \| `drop`） | 先写目标模型，再让代码追上它，最后替换当前模型 |
| 改完代码 | `python -m flowguard change` | 校验地图和代码；只列出受影响的测试和模型 |
| 发布之前 | `python -m flowguard release` | 严格检查、架构错误、重跑全部模型 |
| 新模型或采用流程 | `python -m flowguard template --list` | 选择 `behaviour`、`validator`、`ui-journey`，或用 `adoption` 生成仓库规则 |

## 能做的事

| 原来的专项名 | 现在怎么做 |
| --- | --- |
| behavior-commitment | 给对外承诺唯一负责者、真实代码锚点和测试；建模备用路径。 |
| architecture-reduction | 在目标中删除或合并节点；保住公开承诺，检查无引用的代码。 |
| code-structure | 在目标中新增或拆分负责者；文件、状态、副作用和入口各有唯一归属。 |
| contract-exhaustion | 用 `validator` 节点检查有限的接受和拒绝用例。 |
| field-lifecycle | 在目标中描述改名或退役字段，检查新旧读取方。 |
| model-mesh | 用 `PARENT` 嵌套模型；子模型交接时按需用状态投影或 `flowguard.closure`。 |
| model-test | 用 `IMPLEMENTED_BY` 和 `TESTED_BY` 绑定规则，运行 `map models --tests`。 |
| topology-hazard | 从 `map models` 读取计算出的 `hazard:` 观察。 |
| test-mesh | 用 `release --shards N`；每个分片跑若干棵完整测试子树，每个收集到的测试恰好运行一次。 |
| ui-flow | 用 `ui-journey` 节点检查状态和旅程，再配合人工界面清单。 |

见[树的操作](.agents/skills/flowguard/references/tree_operations.md)和
[模型配方](.agents/skills/flowguard/references/model_recipes.md)。

## 模型能抓住什么（真实例子）

`tests/fixtures/flowguard_map/order_placement.py`：客户端用同一个订单号重试，导致重复扣款。单元测试是绿的；
模型的一致性回放失败，给出两步反例 `Place(o1), Place(o1) -> charges=('o1','o1')`。为了让它通过而删掉不变量
也不行：“已知坏版本通过了：不变量抓不住它”。

## 它证明不了什么

模型只证明它声明的有限边界；地图描述的是当前这次提交；自动发现是启发式的。FlowGuard 不能代替测试、
代码评审和线上监控，也不会找出全局最优的架构。它维护一棵和代码、测试绑定的模型树。

## 仓库结构

- `flowguard/` 引擎、节点种类和计算出的面；`flowguard/map/` 地图、目标、自动发现和证明层
- `.agents/skills/flowguard/` 给 AI 用的技能
- `.flowguard/` FlowGuard 自己的地图和模型（它用自己维护自己）
- `examples/` 可运行的教学模型；`docs/` 长篇说明

许可证：MIT
