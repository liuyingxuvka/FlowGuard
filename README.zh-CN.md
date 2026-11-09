# FlowGuard

<p align="center"><img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" /></p>

[English](./README.md)

FlowGuard 帮写代码的 AI 先比较真实行为，再核对要求。普通测试自动给出三个信号：变了什么、哪些副本该一起变却没变、违反了哪条独立规矩。生成的代码地图帮助找到已有负责人，避免又写一套实现。

默认就是跑项目测试，看 FlowGuard 那几行。源码变化时比较可支持的旧、新结果类；同名锚点必须一致；有出处的独立规则表达预期。源码没变且没有约束违反时保持安静。规则和可选小模型帮助后续会话保留重要判断；这不等于已经证明普遍节省时间或 token，之前的可选使用对照没有证明收益。[4.0 迁移说明](./docs/upgrade-4.0.md)列出这次执行边界的变化。

## 开始

从这个仓库安装；PyPI 上同名的项目不是本工具。需要 Python 3.11 或更新版本。

```bash
python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git"
cd your-project
python -m flowguard init
python -m pytest
```

`init` 启用 pytest 插件，添加采集哨兵、CI 片段和四条项目规则，不为当前开发任务建模。源码导航用 `show "what it decides"`；可选模型视图会加载所查看的模型。只有某条规则需要引用时才保存相关原话，一次、逐字节保留。

## 一条规则，绑定每个必要副本

规则从要求独立写出预期；源码里的锚点连接真实函数；字面情况行保留已知回归。[本地规则指南](./.agents/skills/flowguard/references/rules.md)含完整的双锚点例子，会和技能一起复制。


最短锚点是在真实函数上方写 `# flowguard: sensor NAME`。工具从参数推断输入和上下文；确认含义和单位，需要一致的副本挂同名锚点。函数不存在或明确声明的签名矛盾为红；没验证的读数为灰。刚写的权威文档可能显示 green*，这不等于独立确认。旧的完整注释写法和字面情况行继续有效。

## 源码地图和语言边界

基础安装只需 Python 读取器，不带外语种 grammar。要用下面已冻结的读取器，请安装可选附加：`python -m pip install "flowguard[languages] @ git+https://github.com/liuyingxuvka/FlowGuard.git"`。只在出现相应语言时载入解析器；缺少 grammar 会明确报告该读取器不可用。读取源码不等于执行或编译源码。

| source | map facts | executable behavior anchors |
| --- | --- | --- |
| Python | 声明、调用、依赖、读写和固定查询 | Python 函数 |
| JS/JSX、TS/TSX | 声明、调用点、导入/再导出、赋值、确定的键、Prisma 写入和读取、catch 兜底、判断里的字面值和比较用的常量名、查表、声明的取值集合和函数体形状 | 最小版，只支持 vitest（ESM）：模块顶层函数；jest 项目只做静态检查 |
| Prisma schema、SQL 文件 | 模型、表、列（`@map`、`@@map`、`[方括号]` 写法）、带 `onDelete` 的关系、`CHECK (col IN (...))` 集合 | 不是代码 |
| C、C++ | 声明、调用、包含、赋值和确定的键 | 不支持 |
| C# | 声明、调用、using 声明、赋值和确定的键 | 不支持 |

`capabilities()` 显示实际文件、解析错误和查询支持范围。外部依赖、动态派发、宏和有歧义的绑定明确保留；grammar 能解析不代表语义覆盖完整。TS/JS 项目用 `python -m flowguard check --static`：不启动 pytest，只做地图类检查，输出和普通测试结束时一样：兜底账本、负责人以外的写入、登记的配对、不在声明集合里的取值、删除时没处理的受限子表、几份描述之间缺的列、新的标签写法、别处还写着的旧值、被改函数没改的相似实现；有红时退出码为 1。`init` 发现 `package.json` 时生成一个 vitest（或 jest）测试来执行它，结果就出现在 `npm test` 里。vitest 项目里，`init` 还会写 `flowguard.vitest.mjs`，并在 vitest 配置里加两行，都标着 `flowguard: vitest`（删掉这两行就撤销）。相对任务开始没有 TS/JS 改动时，它什么都不加；有改动时，vitest 会包住挂了 `// flowguard: sensor 名` 的模块顶层函数和这次改过的函数，记录它们的调用，按代表值把每次调用回放一遍（函数比较用的常量，包括常量名和导入的常量，以及它查的表的键），在同样的输入上跑基准版本和同名副本，测试汇总之后打印和 pytest 一样的变化情况类、副本红和规则红。回放时挡住写文件、子进程、网络和线程；代码或参数里用到数据库客户端的函数一律不回放。jest、CommonJS 配置、类方法和异步结果只做静态检查或标灰。vitest 运行之外，TS/JS 代码从不执行，调用按名字解析。外语种的字面集合、测试发现和完整符号读取查询尚不支持；C、C++、C# 读取器保持冻结。结构规则使用未实现的查询、解析失败的源码，或没有查询任何源码时为灰。只有要求本身限定语言时才显式限域，不为变绿排除不方便的文件。源码、读取器/grammar 版本和项目解析配置变化会使缓存事实失效。[意图指南](./docs/intent-guide.md)有一个小的源码查询例子。

## 日常命令

| command | purpose |
| --- | --- |
| `python -m pytest` | 跑普通测试，读取最多十行的三个 FlowGuard 信号。 |
| `python -m flowguard` | 读十行以内的简报，记下这次任务的基准提交，不运行测试。 |
| `python -m flowguard show "what it decides"` | 新写判断之前找已有负责人和静态候选。 |
| `python -m flowguard show WINDOW` | 读规则或已记录的锚点、模型观察；历史明确标为历史。 |
| `python -m flowguard try ACCEPT days=4` | 查看一个真实输入的结果，上下文由实际测试提供。 |
| `python -m flowguard try ACCEPT days=4 --grid` | 打印全部已计算代表值；分区未闭合仍为灰。 |
| `python -m flowguard watch -- python app.py` | 正常运行 Python 目标，记录锚点并检查模型。 |
| `python -m flowguard model draft PUBLISH` | 按观察路径起草节点和边，要求仍需确认。 |
| `python -m flowguard check` | 通过普通 pytest 重查受影响的规则和测试。 |
| `python -m flowguard check --all --deep` | 在 CI 运行所有意图项、普通项目测试、决策探针和变异检查。 |
| `python -m flowguard req list` | 列出已存原话；`show R1` 读取原文。 |

没有规则时，检查只说一行：

```text
FlowGuard check: no intent rules.
```

情况行保持字面值，不会悄悄缩水。可支持的分区全量运行，不设固定情况数上限。一个运行时观察真实调用，在同一组上下文里回放安全的输入类，再复查原值；场景在同一个已采集会话里，以新的函数级夹具重跑原测试。观察不启动 Python 子进程，也不开嵌套测试会话。标定测试不会让写操作变得可安全重放；有副作用的业务仍由普通测试执行，小模型只连接实际读数。函数指纹用于增量选择；未解析导入、外部输入或不可用的夹具会保守重跑或标灰。相似只是一条线索，不构成等价证明。

## 边界和迁移

规则检查声明的输入和真实绑定，不证明事实真伪，也不覆盖应用所有行为。灰色说明尚未验证什么。保留普通测试和审查。相似但必须不同的判断用 `distinct`，替代用 `supersedes`，只有下层判断确实简化上层规则时才用 `uses`。

真正拆分判断时，场景关系连接真实的上下层读数，由引擎提供验证过的联合输入。检查会联合组合全部已验证下层输入，包括嵌套的 uses。闭合的布尔/枚举域可以完整穷尽；开放域只检查可支持的分区代表，不能声称枚举每个值。依赖或归属约束放在其已有负责人处，用有出处的 `structure_rule` 检查。不要求为整个应用建模，也不增加一套层次维护层。

旧状态机、后台任务、图片和发布测试运行器已退役。`status`、`where`、`draft`、`decide`、`release` 不保留兼容别名。4.0 也退役了诊断和分片参数、独立的检查器流程记录；只在子进程里调用的守护目标不再算已观察。保留原话、已有规则和情况行，用真实测试重建生成的观察。详见[意图指南](./docs/intent-guide.md)和[4.0 迁移说明](./docs/upgrade-4.0.md)。

## 仓库

- `flowguard/structure/`：生成代码地图和固定源码查询。
- `flowguard/intent/`：规则、锚点、小流程和 pytest 集成。
- `flowguard/map/`：共享源码及原话字节读取。
- `.agents/skills/flowguard/`：唯一公开技能。
- `tests/`：普通控制和项目自己的意图规则。

License: MIT

源码锚点取代 `.home` 和手写适配函数。小型分层模型只连接节点、边、状态转移和真实读数；未验证或不支持的范围保持灰色。模型也可能和 AI 一起理解错要求，仍要保留独立测试和出处原话。
