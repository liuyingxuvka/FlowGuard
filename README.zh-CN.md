# FlowGuard

<p align="center"><img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" /></p>

[English](./README.md)

FlowGuard 帮写代码的 AI 找到已有判断，并在以后改动时保持必要副本一致。代码地图由工具生成。只有一个判断在几处、主人说“所有地方”、或修了一个 bug 时才写规则；普通修改仍用普通测试。

默认用法保持收窄：读状态、保存真实原话、找已有代码，在绑定判断改动后检查已有规则。可选使用对照没有证明正确性或时间收益；行为差异和小流程模型仍可用于重复判断、跨会话路径。要改一个需要规则的老判断，先补锚点再改。实测范围和边界见[迁移说明](./docs/upgrade-3.0.md)。

## 开始

从这个仓库安装；PyPI 上同名的项目不是本工具。需要 Python 3.11 或更新版本。

```bash
python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git"
cd your-project
python -m flowguard show "who may accept an order"
python -m flowguard init
python -m flowguard req add owner-message.txt --id R1
```

`show` 读取源码，不导入应用。能复用已有负责人就复用。`init` 添加 pytest 哨兵、CI 片段和四条项目规则，不为这次任务建模型。主人原话只保存一次，逐字节保留。

## 一条规则，绑定每个必要副本

规则从要求独立写出预期；源码里的锚点连接真实函数；字面情况行保留已知回归。[本地规则指南](./.agents/skills/flowguard/references/rules.md)含完整的双锚点例子，会和技能一起复制。


任一副本改动后，`check` 通过普通 pytest 执行当前源码。不一致为红，没验证的边界为灰。刚写的权威文档可能显示 green*，这不等于独立确认。

## 源码地图和语言边界

同一份生成地图和固定查询可读取下面的首批语言。正常安装包含对应 grammar 包；只有实际出现该语言时才载入解析器。读取源码不等于执行或编译源码。

| source | map facts | executable behavior anchors |
| --- | --- | --- |
| Python | 声明、调用、依赖、读写和固定查询 | Python 函数 |
| JS/JSX、TS/TSX | 声明、调用点、导入/再导出、赋值和确定的键 | 不支持 |
| C、C++ | 声明、调用、包含、赋值和确定的键 | 不支持 |
| C# | 声明、调用、using 声明、赋值和确定的键 | 不支持 |

`capabilities()` 显示实际文件、解析错误和查询支持范围。外部依赖、动态派发、宏和有歧义的绑定明确保留；grammar 能解析不代表语义覆盖完整。首批尚不支持外语种的异常处理、字面集合、测试发现和完整符号读取查询。结构规则使用未实现的查询、解析失败的源码，或没有查询任何源码时为灰。只有要求本身限定语言时才显式限域，不为变绿排除不方便的文件。源码、读取器/grammar 版本和项目解析配置变化会使缓存事实失效。[意图指南](./docs/intent-guide.md)有一个小的源码查询例子。

## 日常命令

| command | purpose |
| --- | --- |
| `python -m flowguard` | 项目已有规则时读取短屏幕和缓存，不运行测试。 |
| `python -m flowguard show "what it decides"` | 新写判断之前找已有负责人和静态候选。 |
| `python -m flowguard show WINDOW` | 读规则、出处、锚点和完整发现。 |
| `python -m flowguard show --draft orders:accept` | 为锚点定位已有标定测试，不编造预期答案。 |
| `python -m flowguard check` | 通过普通 pytest 重查受影响的规则和测试。 |
| `python -m flowguard check --all --deep` | 在 CI 运行所有意图项、普通项目测试、决策探针和变异检查。 |
| `python -m flowguard check --diagnose` | 按需记录检查阶段耗时和已激活锚点事件；排查完整套件时再加 `--all`。 |
| `python -m flowguard req list` | 列出已存原话；`show R1` 读取原文。 |

没有规则时，检查只说一行：

```text
FlowGuard check: no intent rules.
```

情况行保持字面值，不会悄悄缩水。出处、帮助代码、数据和实现变化都会使依赖结果失效。必要副本要明确绑定，候选相似不构成等价证明。`check --all` 为完整套件记录测试与代码的联系，局部 `check` 重录选中的测试。这些联系用于选择受影响测试，并为锚点定位已有标定测试。直接运行 pytest 时，不普遍跟踪未标记的普通测试；明确标记的守护测试仍记录联系。联系缺失时按源码依赖保守选择。完整采集保留这些真实联系，因此会多做一些必要工作。 普通检查只在所支持、输入可闭合的范围内复用结果；未验证的外部导入或调用仍会重跑，安装包版本相同不证明它没有外部输入。模块初始化仍算依赖，保留函数对象本身不等于执行函数体。即使源码未改，开放输入仍可能需要重跑。

## 边界和迁移

规则检查声明的输入和真实绑定，不证明事实真伪，也不覆盖应用所有行为。灰色说明尚未验证什么。保留普通测试和审查。相似但必须不同的判断用 `distinct`，替代用 `supersedes`，只有下层判断确实简化上层规则时才用 `uses`。

真正拆分判断时，场景关系连接真实的上下层读数，由引擎提供验证过的联合输入。检查会联合组合全部已验证下层输入，包括嵌套的 uses。闭合的布尔/枚举域可以完整穷尽；开放域只检查可支持的分区代表，不能声称枚举每个值。依赖或归属约束放在其已有负责人处，用有出处的 `structure_rule` 检查。不要求为整个应用建模，也不增加一套层次维护层。

旧状态机、后台任务、图片和发布测试运行器已退役。`status`、`where`、`draft`、`decide`、`release` 不保留兼容别名。保留原话档案，保留有用的契约和情况行，本轮不改 `.flowguard/models/`。详见[意图指南](./docs/intent-guide.md)和[迁移指南](./docs/upgrade-3.0.md)。

## 仓库

- `flowguard/structure/`：生成代码地图和固定源码查询。
- `flowguard/intent/`：规则、锚点、小流程和 pytest 集成。
- `flowguard/map/`：共享源码及原话字节读取。
- `.agents/skills/flowguard/`：唯一公开技能。
- `tests/`：普通控制和项目自己的意图规则。

License: MIT

3.0 用源码锚点取代 `.home` 和手写适配函数。纯判断直接调用；有副作用的函数用项目自己的普通测试标定，并读取真实结果。复杂部分可写小型分层流程模型，核对可确定的代码路径和测试实际顺序；未验证或不支持的范围保持灰色。[3.0 迁移说明](./docs/upgrade-3.0.md)列出重建方法。
