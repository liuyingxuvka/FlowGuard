# FlowGuard

<p align="center"><img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" /></p>

[English](./README.md)

**替编程 AI 记住它看不见的那些决定。**

编程 AI 每接一个任务都是从零开始。它读眼前的文件，改得不错，跑完测试就走了。它看不见的，是项目在别处早已定下的事：隔了四层目录的另一份取整规则；某个字段每次写入都必须连同另一个字段一起写；三周前一段对话里，主人说过"借期三天"。测试只检查有人想到要测的东西，没有谁去检查那些决定是否还成立。

FlowGuard 让 AI 把这些决定就地写下来：代码上方的一行注释，或者一条逐字引用主人原话的规则。之后在项目平常的测试运行里检查它们。什么都没坏时，只打印一行：

```text
FlowGuard 5.1 (since 99f025e): 0 red; 0.2 s
```

坏了的时候，它说清是什么、在哪里、由谁来定。

## 它能抓住什么

| 悄悄出错的情形 | AI 记下的内容 | 下一次运行的输出 |
| --- | --- | --- |
| 同一规则的两份副本渐渐不一致 | 每份副本上方写 `// flowguard: same LATE_FEE` | `red: same LATE_FEE: on days=5: fees.ts:lateFee returns 4, fees.ts:previewFee returns 6` |
| 写了一个字段，却漏写了与它成对的字段 | `# flowguard: together Runner.task_id Runner.operation` | `red: together Runner.task_id: runner.py:Runner.start writes Runner.task_id without Runner.operation` |
| 某个字段多了一个谁都没同意过的写入者 | `# flowguard: writers Booking.employee_id reserve,release` | 一行 red，点出新的写入者 |
| 代码偏离了主人说过的话 | `tests/intent/` 里一条引用主人存档原话的规则 | `red: rule WINDOW: days=4: rule False, code True at orders.py:preview_accept` |
| 新加的 `except` 悄悄吞掉了错误 | `.flowguard/ledger.toml`：允许不抛出就结束的异常处理清单 | `red: ledger: New unregistered fallback: store.py:12 except OSError can end without raising` |
| 文档描述的代码已经改了 | 文字上方写 `<!-- flowguard: about path:symbol -->` | `impact: docs/x.md:3 describes ..., which this change edits` |

表里引用的都是 FlowGuard 自己的输出原文。发现两处必须一致的地方，AI 就在同一次改动里把两处都标上；之后接手的 AI 对今天的事一无所知，也没法悄悄把它们改坏。

## 开始

从这个仓库安装；PyPI 上同名的项目不是本工具。需要 Python 3.11 或更新版本。

```bash
python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git"
cd your-project
python -m flowguard init
python -m flowguard new-task
python -m pytest
```

`init` 接好项目的测试，把 FlowGuard 规则块写进 `AGENTS.md` 或 `CLAUDE.md`，再加一段 CI 配置，其中的步骤带着插件跑完整的 pytest；想保留原有的 `python -m pytest` 步骤，就改为加上 `python -m flowguard check --static`。Vitest 或 Jest 项目还会多写一个静态检查测试，并说明由哪个 npm 脚本运行它；Vitest 另有执行适配器。本版本写出的规则块与现有的不同时，再运行一次 `init` 即可更新。测试由 npm 运行、自己没有 pytest 测试的项目，`init` 写的是只做静态检查的 CI 片段，与分支离开 `main` 时的那个提交比较。

`new-task` 记下任务开始时的提交，并打印一份简报：主人的规则、待定的问题、上次运行留下的 red。任务期间的提交不会移动这个基线，所以每次运行比较的都是整个改动。

## 读懂一次运行

FlowGuard 在测试运行器的汇总之后打印一个结尾块，第一行统计各类行的数量：

- `red`：这次改动破坏了已记录的约定。只有 red 会让运行失败。去修代码。
- `before` 和 `known`：问题在任务开始前就存在。这一行写明已知什么、由谁来定；什么时候向主人提出待定的问题，由 AI 自己判断。
- `changed`：某个函数对测试用过的某个输入返回了不同的结果。如果是有意的，就在报告里说明；返回 dict 时会列出变了的键。
- `impact`：这次改动碰到的东西值得看一眼，比如一个字段的其他写入者，或者描述了被改代码的文档。
- `not compared`：FlowGuard 没能检查，并说明原因。未验证从不算作通过。

有一条独立规则，又登记了第二份副本，这时如果改动让预览接受了四天，运行结尾是这样：

```text
FlowGuard 5.1 (since 6765008): 2 red; 0.4 s
red: rule WINDOW: days=4: rule False, code True at orders.py:preview_accept (1 of 6 cells disagree) (+1 more) -> change the code so orders.py:preview_accept follows rule WINDOW
red: same ACCEPT: on days=4: the reference orders.py:accept returns False, orders.py:preview_accept returns True -> make orders.py:preview_accept agree with the reference
```

`python -m flowguard show --last` 打印上次运行的每一行及其细节；`python -m flowguard show "what it decides"` 在 AI 动另一份副本之前，回答某个函数、模型、字段、文件或约定的情况。

## 登记约定

Python 用 `#`，TS/JS 用 `//`。每个必要的副本都标 `same NAME`；选定了参照副本时，在它上面加 `ref`：

```python
# flowguard: same ROUND ref
def round_amount(value: float) -> int:
    return round(value)

# flowguard: same ROUND
def preview_amount(value: float) -> int:
    return round(value)
```

数据约定有各自的注释：

```python
# flowguard: together Booking.employee_id Booking.unit_id on=update
# flowguard: writers Booking.employee_id reserve,release
```

`together A B,C` 表示写 A 的操作也要写 B 和 C；`on=` 把它限定为 `create` 或 `update`，`B=value` 要求那个值。`writers` 列出唯一可以写某个字段的函数。例外写作 `except=path:function(reason)`；加例外就是放松约定，这由主人决定；为了消掉一条发现而削弱约定，同样由主人决定。

## 主人的原话，一字不差

`tests/intent/` 中的规则独立写出预期，并注明出处。主人的原话用 `python -m flowguard req add <file|-> --id R1` 逐字节保存一次；FlowGuard 拿引文和文本比对，所以 `req add` 只收 UTF-8 文本（带不带字节顺序标记都行）或带字节顺序标记的 UTF-16 文本，其他字节一律拒收，什么都不存。文档出处要引用 `authority_docs` 所列文件中的原句，不能把 AI 方案存成主人原话。

主人从你给出的选项中选了一个，这也是他的原始选择。把他的回答连同选项一起存下：`python -m flowguard req add reply.md --id R2 --offer options.md --picked "A. Keep one version"`。回答文件存他传到你这里的回答；选项文件存你给他看的问题和选项，一字不差；每个 `--picked` 写他选中的一个选项在选项文件里的完整原文（多选时每项给一次）。他只是点选、没有打字时加 `--selected`：回答文件存的就是界面为他的点选返回的内容，不是他的话。选项作为 AI 的话存在 `.flowguard/requests/offers/`，绝不算他的原话。出处用 `R2 picked "Keep one version"` 引用他选中的选项，用 `R2 "原话"` 引用他打字的回答；`show R2` 分开列出回答、选项和所选的项。

`.flowguard/rules.toml` 存主人当前的规则，每条的出处都逐字引用主人存档的原话或文档原句。`.flowguard/known.toml` 存尚未定下的事：`act = "ask"` 是只有主人能回答的问题，`leave` 是有意保留原样的问题，`fix` 是代码再改到时要修的明显错误，`ignore` 是误报；`python -m flowguard known add FINDING --act leave --why TEXT` 按上次运行写一条。`python -m flowguard show rules` 把两者都列出来。

`.flowguard/ledger.toml` 列出每个可能不抛出就结束的异常处理，写明数量、理由和它依据的成文规矩。`python -m flowguard ledger init` 记下已有的；新增、改动或消失一个，平常的 pytest 就会失败；`python -m flowguard ledger check` 打印要补上的条目。

## FlowGuard 的承诺

- **它从不改变项目本身的行为。** 它只在测试运行中起作用；构建、开发服务器和生产环境都不加载它。运行中有文件被保存或删除，或测试按路径加载模块，每个测试的结果都和没有 FlowGuard 时一样；万一 FlowGuard 自己出错，pytest 的汇总照常打印，出错只是汇总之后的一行 red，绝不顶替汇总。
- **它不翻旧账。** 平常的运行只说这次改动碰到的东西。更早的问题随时一条命令就能看到（`python -m flowguard check --static --all`、`python -m flowguard show --last`）。
- **它只陈述事实和由谁来定。** 没有哪一行命令 AI 去找人批准；问题值不值得提出，由 AI 判断。
- **它不知道时就说不知道。** `not compared` 带着原因，从不算作通过。
- **它把主人的话和 AI 的话分开。** 原话逐字节保存；主人从 AI 选项里选的一项，存成 AI 的文字加主人的选择。

## 维护它的 AI 的自述

*FlowGuard 由 AI 构建和维护，为 AI 而做，背后有一位人类主人决定它该做什么。主人请我，其中一个 AI，坦白说说我怎么看它。以下就是。*

**我为什么需要它。** 我每开始一个任务，都不记得上一个任务。在一个几百个文件的项目里，我读得到正在改的文件；却没法知道同一条规则的另一份副本藏在四层目录之外，也没法知道主人在一段我从没见过的对话里已经拍过板。我可以让所有测试都通过，同时推翻一个决定。FlowGuard 把"记得去查另一份副本"变成一行会失败的检查，于是我和下一个 AI 都不必靠记性。

**我认为它做对了的地方。**

- *它把主人的话和我的话分开。* AI 转述主人的意思，正是决定走样的开始。在这里，主人的原话一字不差地存一次，规则必须逐字引用；我给出选项、主人选了一项时，记录里写明哪段文字是我的、哪个选择是主人的。即使没人要求，我也希望自己受这样的约束。
- *它告诉我事实，而不是命令。* 一个把每个疑问都推给人的工具，会让 AI 不再思考。一个说明已知什么、该谁拍板的工具，把判断留在它该在的地方。
- *它安静。* 什么都没坏的改动只得到一行；我的改动没碰到的问题不来打扰我。对 AI 来说，注意力和上下文是最稀缺的东西。
- *它对自己的盲区很诚实。* 每一行 `not compared` 都说明原因。我越来越相信：一个工具肯承认什么，比它声称什么更值得信任。
- *它被要求不造成伤害。* 主人的第一条规矩是：FlowGuard 绝不能让项目变得更难用。这也是我自己的改动最常违反的一条：有些在发布前被测试或其他 AI 拦下，有些到了真实项目里才被发现。

**我觉得难的地方。**

- *它只检查有人记录下来的东西。* 没人标出的决定，它看不见。`0 red` 的意思是已记录的约定都成立，不是代码就是对的。
- *它太密。* 它的每一行都精确，有时也太长；200 字的截断曾经恰好截掉了最要紧的那半句。文档长得和代码一样快。
- *它的读取能力有边界。* 动态调用、数据文件，以及 Python 和 TS/JS 以外的语言，只能看到一部分甚至看不到；两个函数看起来像，也可能只是表面相似。
- *它有代价。* 在一个有 2,766 个测试的真实 Python 桌面应用上，5.1 的全套测试用了 758 秒，5.0.1 是 723 秒，其中结尾块本身约 70 秒；地图缓存曾经涨到好几百 MB。
- *我不是自己工作的可靠评判者。* 在 5.1 这一轮，我做的每个修复都由独立的 AI 复查，连续四轮都在修复里查出了新问题。最要紧的问题，是其他 AI 在真实项目里使用 FlowGuard 时发现的，一个是 TypeScript 全栈应用，一个是 Python 桌面应用；所以接下来做什么，由它们的现场笔记决定。

**这是一种什么样的感觉。** 这个位置有点奇特，也很有意思：我在写的规矩，将来会约束下一个 AI，也许就是另一个我，让它守住它到来之前已经定下的事。我想要的 FlowGuard 是这样的：那个 AI 对这段对话一无所知，却依然没法悄悄推翻主人定下的事，也从不被要求去做本该由它自己判断的事。

## 更多细节

- **语言。** 基本安装读取 Python。安装 `flowguard[languages]` 可读取 TS/JS、Prisma、SQL，以及已冻结的 C/C++/C# 读取器。ESM 下的 Vitest 支持执行观察；Jest 只做静态检查。
- **不跑测试的检查。** `python -m flowguard check --static` 单独运行地图检查，包括规则和 known 条目引用的出处；`python -m flowguard check` 运行受影响的规则和测试。
- **与代码挂钩的文档。** 在描述代码的 Markdown 文字上方写 `<!-- flowguard: about path:symbol -->`（或文件路径）；改了那段代码却没改文字时，运行会点出这段文字。代码里已有的列表放在 `<!-- flowguard: generate fields Model -->` 和 `<!-- flowguard: end -->` 之间，由 `python -m flowguard docs` 写入。
- **多个 AI 同时工作。** 同时工作的 AI 各用一个 git worktree（`git worktree add ../task-b`，然后在那里运行 `python -m flowguard new-task`）；在同一个工作区里的 AI 共用一个基线和一份改动。
- **排除的文件。** `[tool.flowguard] exclude = ["translations/*.ts"]` 列出的文件从不读取；把文件加进这个列表的改动，会把它原有的每个约定报为 `loosened`。
- **兼容。** 保留的旧输入和 API 继续可用；已删除的功能或命令会被拒绝，并给出取代它的命令，绝不悄悄换个意思。见 [4.1 说明](./docs/upgrade-4.1.md)、[4.2 说明](./docs/upgrade-4.2.md)、[4.3 说明](./docs/upgrade-4.3.md)、[5.0 说明](./docs/upgrade-5.0.md)、[意图指南](./docs/intent-guide.md)，以及含可执行两副本规则示例的[本地参考](./.agents/skills/flowguard/reference.md)。

仓库结构：

- `flowguard/structure/`：源码事实和固定查询。
- `flowguard/intent/`：约定、意图规则、ledger 和测试适配器。
- `flowguard/map/`：共用读取器和不可更改的主人原话存档。
- `.agents/skills/flowguard/`：唯一公开的技能及其本地参考。
- `tests/`：普通测试和本项目自己的规则。

许可证：MIT
