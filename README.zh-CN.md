# FlowGuard

<p align="center"><img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" /></p>

[English](./README.md)

FlowGuard 给 AI 一份小而可执行的功能模型，连接实际代码和保存的主人原话。它检查普通例子容易漏掉的组合，跨会话保留未解决的冲突，让下一次修改能从已有认识出发。

## 五分钟开始

从本仓库安装；PyPI 上名为 flowguard 的包是另一个项目。

```bash
python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git@v1.4.0"
python scripts/install_skill.py --target ~/.codex/skills
cd your-project
python -m flowguard status
python -m flowguard req add owner-message.txt --id R1
python -m flowguard where place_order
# 修改行为时，先更新受影响的功能模型，再改实现。
python -m flowguard check
python -m pytest -q tests/test_orders.py
git add -A
git commit -m "Charge each order once" -m "Request: R1"
```

技能安装脚本在源码仓库里，目标目录填写所用 AI 的技能目录。没有模型也可以查源码、存原话。状态、动作、条件、设置或结局发生变化时，再为相关功能建模；安装包中的[模型指南](./flowguard/flow/HOWTO.md)包含可运行的例子和代码适配器。

## 一个模型，连接实际代码

在 `.flowguard/flow/` 中，用 `Model`、字段、动作和明确的承诺描述一个小功能。模型的预期行为应独立于实现。用 `Model.bind_adapter` 对照实际调用和结果；同一个原生记录器记录真实读取、调用和选定的 pytest 执行，没观察到的部分仍标为未知。

从已有 Python 代码起步，可用 `python -m flowguard draft pkg/orders.py:Order` 只读提取静态词汇，不执行项目。加 `--write` 仅首次创建模型和适配器 TODO；让 AI 按需求补完独立的预期行为、连接实际调用，再运行 `check`。草稿只是起点，不是检查结论；完成的作者文件不会被替换。

`check` 探索声明的有限状态空间，报告承诺冲突、死路和无法到达的目标，附上可得的最短路径及来源需求。`check --full` 还会故意改坏模型。通过只覆盖声明的模型及已观察的代码边界；省略的行为仍需要相关模型或测试。

主人原话原样保存在 `.flowguard/requests/`。未解决的冲突及其保留范围写入 `.flowguard/conflicts.json`，重启后仍可见。缩小模型不能悄悄抹去已有义务。实际代码修复需要当前原生对照和执行过的回归；真正替换需求时使用主人原话。`show` 直接绘制已保存的证据，不重跑应用。

## 日常命令

| 命令 | 用途 |
| --- | --- |
| `python -m flowguard status` | 刷新已改模型，显示未完成工作、来源原话和待决问题。 |
| `python -m flowguard where NAME` | 不导入项目代码，查定义、调用者、模型覆盖和需求链接。 |
| `python -m flowguard draft pkg/orders.py:Order` | 读取静态起始词汇；加 `--write` 首次创建模型和适配器 TODO。 |
| `python -m flowguard req add FILE --id R1` | 按字节保留一条实际主人消息；替代旧需求时加 `--supersedes R0`。 |
| `python -m flowguard check` | 通过共用后台任务检查受影响工作，复用仍有效的结果。 |
| `python -m flowguard check --full` | 执行完整模型检查，包括故意改坏。 |
| `python -m flowguard check --tests tests/test_orders.py` | 明确选择实际测试，审查备用路线；普通检查不运行 pytest。 |
| `python -m flowguard show` | 绘制冲突，否则绘制相对 HEAD 的改动；加 `MODEL --before REV` 指定版本。 |
| `python -m flowguard decide ID --owner "QUOTE" --request R1` | 为需求冲突记录有实际来源的主人选择。 |
| `python -m flowguard check --commit-ready` | 对照暂存字节读取当前结果；不会自动安装提交钩子。 |
| `python -m flowguard release --shards 4` | 检查全部模型，每项收集到的项目测试恰好运行一次，然后保留原始字节快照。 |

`check` 区分通过、冲突、模型错误、UNKNOWN 和 RUNNING。默认等待 90 秒；相同命令续接已有任务。已结束的 UNKNOWN 保持可见，并允许提交。不加 `--shards` 的 `release` 会说明没有运行测试。绘图使用 node、Playwright 和 Chromium；没有它们仍可得到 Mermaid 文本。

## 低成本使用已有认识

每个模型聚焦改动涉及的功能，也考虑共用状态的旧行为。先读简短的 `status` 或 `where`，只展开需要的部分。`where --flow`、`--arch`、`--text`、`--keyflows` 分别查调用、架构、原文和共享存储。按需使用 `--all`、`--json`、`--root DIR` 或 `--at REF`（`--at` 选择历史原文）。静态匹配只是候选，不是语义证明。

模型是 AI 主动用来规划修改、检查假设和对照实际行为的外部记录。它能减少重新理解的工作或发现实际错误才有价值；增加字段、记录或必经检查，本身不会让它更好。

## 升级和平台边界

1.0 只保留一个流程引擎，删除旧地图、旧 `.flowguard/models/`、target 命令和实验性 `behave` 引擎。按[升级指南](./docs/upgrade-1.0.md)把有用的规则和绑定迁到当前模型及测试；执行旧格式时会说明需要升级。迁移期间仍可静态查源码。

流程执行支持 Linux、Windows 和 Python 3.11 以上。macOS 可查静态源码、保存原话；执行流程会明确报告平台限制。模型只证明声明的有限边界和已有观察，仍需普通测试、复查及实际运行监测。

## 仓库结构

- `flowguard/flow/`：模型、原生记录器、任务、冲突历史、绘图及发布入口。
- `flowguard/map/`：共用源码索引、静态查询、原话记录和普通测试树分片，不需要手写地图文件。
- `.flowguard/flow/`：FlowGuard 自用功能模型。
- `.agents/skills/flowguard/`：唯一公开技能。
- `tests/`、`examples/`、`docs/`：测试、例子和详细指南。

许可证：MIT
