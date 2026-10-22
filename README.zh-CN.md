# FlowGuard

<p align="center">
  <img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" />
</p>

<p align="center"><strong>AI 辅助开发的“软件 DNA”：一张随代码演进、并和代码互相校验的软件地图，加上关键流程的可执行模型，以及 10 个查找架构缺陷和行为缺陷的专项检查。</strong></p>

[English](./README.md)

FlowGuard 用自己的地图和模型维护本仓库（`.flowguard/map.json`、`.flowguard/models/`）。实测结果和保留边界见[修复与验收报告](docs/flowguard_0_70_2_fix_report.md)。


## 它做什么

AI 擅长局部修改，但每开一个新会话都要重新弄清：软件由哪些部分组成、这件事归谁管、改这里会影响哪里？
FlowGuard 在项目里保存三样东西：

1. **地图** `.flowguard/map.json`：各个组件、它们的职责、拥有的状态、副作用、文件、入口、依赖、
   测试和模型。新会话用几千 token 读完整张地图，就知道该看哪里。
2. **模型**：关键流程（重试、幂等、缓存、顺序、金额、权限、多步骤流程）的小型可执行模型，形式是
   `输入 x 状态 -> 一组(输出 x 状态)`。FlowGuard 在边界内穷举所有输入序列，给出反例，检查已知的坏版本
   一定会失败，并把模型轨迹放到真实代码上回放比对（一致性检查）。
3. **专项检查**：10 个有针对性的检查，任务需要时由 AI 选用（见下表）。

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
| 改完代码 | `python -m flowguard change` | 校验地图和代码；只列出受影响的测试和模型 |
| 发布之前 | `python -m flowguard release` | 严格检查、架构错误、重跑全部模型 |
| 新的专项模型 | `python -m flowguard template --list` | 每个专项检查一个起步合约模型（model-mesh、topology-hazard、model-test 另写运行脚本） |

## 10 个专项检查

| 专项 | 能抓住什么 |
| --- | --- |
| behavior-commitment | 对外承诺没有唯一负责者和测试；偷偷走备用路径 |
| architecture-reduction | 不安全地合并或删除重复代码 |
| code-structure | 模块划分或拆分让某个状态、副作用或公开入口没有唯一负责者 |
| contract-exhaustion | 有限边界里没人测过的坏用例和组合 |
| field-lifecycle | 改名或替换的字段没有负责者、读取方或迁移 |
| model-mesh | 多个模型拼不起来（负责者、重新挂接、没人消费的输出） |
| model-test | 规则、代码契约和测试对不上 |
| topology-hazard | 全绿模型里潜藏的上线隐患（共享写者、可重复的副作用） |
| test-mesh | 结果不可信的大规模测试运行 |
| ui-flow | 按钮没有事件、流程没有终点、内容该藏的露了 |

每个专项都有一份简短说明：`.agents/skills/flowguard/references/domains/<名字>/protocol.md`。

## 模型能抓住什么（真实例子）

`tests/fixtures/flowguard_map/order_placement.py`：客户端用同一个订单号重试，导致重复扣款。单元测试是绿的；
模型的一致性回放失败，给出两步反例 `Place(o1), Place(o1) -> charges=('o1','o1')`。为了让它通过而删掉不变量
也不行：“已知坏版本通过了：不变量抓不住它”。

## 它证明不了什么

模型只证明它声明的有限边界；地图描述的是当前这次提交；自动发现是启发式的。FlowGuard 不能代替测试、
代码评审和线上监控，也不会找出全局最优的架构。它让自己的结论保持最新、可审查、并和代码绑定。

## 仓库结构

- `flowguard/` 引擎和各专项；`flowguard/map/` 地图、自动发现和证明层
- `.agents/skills/flowguard/` 给 AI 用的技能
- `.flowguard/` FlowGuard 自己的地图和模型（它用自己维护自己）
- `examples/` 可运行的教学模型；`docs/` 长篇说明

许可证：MIT
