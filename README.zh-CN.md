# FlowGuard

<p align="center"><img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" /></p>

[English](./README.md)

FlowGuard 在 AI 改代码时守住整个项目的一致。类型检查、lint 和测试检查的是"这一处写得对不对"；FlowGuard 管的是它们看不见的、跨整个项目的部分。它守四件事：

1. **一件事只有一个负责人。** 一个判断、一份数据各有一处负责。其他地方要么调用它，要么作为登记过的副本和它锁在一起，要么被指出来。
2. **主人的规矩可以执行。** 照主人原话写成的规则，代码违反时报红；需求变了而规则没跟着改时，给出线索。
3. **这次改动新增的结构问题会显现。** 新增的兜底分支、写进去的值不在声明的范围里、负责人之外的写入、该一起写的字段只写了一个、删父记录时留下子记录、副本行为分叉、同一个标签出现新写法。只报这次改动新增的；旧问题留在一张可以查看的清单里。
4. **改出意外时会告诉你。** 在能安全回放的地方，按情况类比较改前改后的行为。

它不是什么都能抓：没人写下来的需求、界面风格、并发和外部服务都不在范围内。灰表示未验证，从来不算通过。

**它怎么用。** 发现问题靠认真检查：AI 读代码、插探针、主人的话。发现以后把它登记下来——一个负责人、一对配对、一个取值集合、一条规则或一条账本条目——从此 FlowGuard 守住它不再退步。结构清单（`check --all`）告诉检查先看哪里。登记跟着软件一起长：从第一条需求开始，每发现一处问题、每定下一条规矩就加一条，模型和代码一起从小长到大。

## 开始

从这个仓库安装；PyPI 上同名的项目不是本工具。需要 Python 3.11 或更新版本。

```bash
python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git"
cd your-project
python -m flowguard init
python -m pytest
```

`init` 启用 pytest 插件，添加采集哨兵、CI 片段和三条项目规矩。项目里有 `package.json` 时，它再加一个 vitest（或 jest）测试，执行 `python -m flowguard check --static`，结果就出现在 `npm test` 里；vitest 项目还会接上执行侧。没有规则时，检查保持安静：

```text
FlowGuard check: no intent rules.
```

## 测试结束时看到什么

测试跑完后，FlowGuard 打印一段。标题写明这次任务的基准提交。下面是四类行，顺序是：红、变、线索、未验证。红全部打印；变、线索、未验证合计不超过十行；名字和位置不截断。每条红和线索后面都附可以照抄的下一步：一行负责人注释、一条账本条目、该改的规则行，或者一句要问主人的话。灰的测试项显示为 `U`（`-v` 下是 `UNVERIFIED`），汇总写成 `N unverified`，不算通过，退出码不变。基准代码还能观察、新代码却观察不了的，算观察丢失，测试失败。

## 四件事

### 一个负责人，副本锁在一起

在负责人上方写 `# flowguard: owner NAME`，在每个必须一致的副本上方写 `# flowguard: sensor NAME`；副本不一致就红。数据负责人写明谁能写它、什么必须和它一起改：

```python
# flowguard: owner hires.reserved writers=shop.store:reserve with=hires.updated_at
```

`check` 还会把每个负责人的相似实现放到负责人的情况类上跑，分成副本、分叉的副本和只是相似三组。即使什么都没登记，这次改过的函数如果原来和别的几份行为相同、而那几份这次没改，也会给出线索。另写一处之前，用 `show "what it decides"` 找到已有的负责人。

### 照主人原话写的规则

`tests/intent/` 里的规则独立于代码写出预期，保留字面回归行，并写明出处：主人的原话，用 `python -m flowguard req add <file|-> --id R1` 逐字节存一次。藏在上下文里的字段，在锚点上用 `fields 名字=表达式` 读出。一个常量从 14 改成 21 时，线索会列出还写着 14 的规则和判断。

### 新增的结构问题

`.flowguard/ledger.toml` 列出每个能不抛出就结束的异常处理，写明数量、理由和它依据的成文规矩；`python -m flowguard ledger init` 把现有的全部记为旧账。裸 `except`、`except Exception`、`contextlib.suppress`、警告过滤、`finally` 里的跳出和可能返回真值的 `__exit__` 不能登记。写进去的值不在声明集合里（`states`、枚举、Prisma enum、SQL `CHECK`）、负责人之外的写入、配对没写全，都是红；删父记录时留下子记录、某份 schema 描述缺列、标签出现新写法，是线索。改动碰到还没定下来的结构问题时，输出会提示先告诉主人；主人的决定记在 `[structure]` 下，以后不再提醒。

### 改前和改后

被改的函数和每个挂了锚点的点，都会换入基准代码，在各自的情况类上回放比较。保护会在写文件、起进程、联网、写数据库之前就拦住；被拦住、复制不了或看不清的调用为灰，并写明原因。改过的锚点如果指纹没变，就复用上一次的比较结果。

## 语言

基础安装读 Python。其他语言的读取器要装 `flowguard[languages]`。

| 源码 | FlowGuard 做什么 |
| --- | --- |
| Python | 上面全部，在普通 pytest 里 |
| TS/TSX、JS/JSX | 静态检查（地图查询、Prisma 写入、`catch` 兜底、字面值、声明集合、结构形状），在 `check --static` 和 `npm test` 里；vitest（ESM）还有改前改后比较和同名副本比较；jest 只有静态部分 |
| Prisma schema、SQL 文件 | 模型、表、列（`@map`、`@@map`、`[方括号]`）、带 `onDelete` 的关系、`CHECK` 集合 |
| C、C++、C# | 冻结的地图读取器：声明、调用、赋值 |

FlowGuard 的核心留在 Python；别的语言只做它需要的那一层薄接口。

## 日常命令

| 命令 | 用途 |
| --- | --- |
| `python -m pytest` | 跑测试，看 FlowGuard 那一段。 |
| `python -m flowguard` | 简短的简报，并记下这次任务的基准提交；任务中途提交，基准不变。 |
| `python -m flowguard new-task` | 开始下一个任务：HEAD 成为基准，再打印简报。 |
| `python -m flowguard show "what it decides"` | 查负责人、谁写谁读、副本和规则。 |
| `python -m flowguard check` | 重查受影响的规则和测试；副本发现在这里跑。 |
| `python -m flowguard check --static` | 不跑测试的地图检查；有红时退出码为 1。 |
| `python -m flowguard check --all --deep` | 全部检查，加上探针和变异检查，在 CI 里跑。 |
| `python -m flowguard ledger check` | 列出账本和代码之间的每一处差异。 |
| `python -m flowguard try ACCEPT days=4` | 在真实测试上下文里试一个锚点的输入。 |
| `python -m flowguard model draft PUBLISH` | 从记录到的路径起草一个小流程。 |
| `python -m flowguard req list` | 列出存下的主人原话。 |

## 边界和迁移

行为只在测试走到的上下文里比较，输出会写明是哪条测试。相似代码和新写法是线索，不是证明。副本彼此一致不能证明答案是对的；有出处的规则才能。4.1 和 4.2 保留 4.0 的全部注释、规则和保存的输入；见 [4.1 说明](./docs/upgrade-4.1.md)、[4.2 说明](./docs/upgrade-4.2.md) 和 [intent guide](./docs/intent-guide.md)。

## 仓库

- `flowguard/structure/`：代码地图和固定查询。
- `flowguard/intent/`：规则、锚点、兜底账本、负责人、pytest 插件和 vitest 一侧。
- `flowguard/map/`：共用的读取器和不可改的主人原话记录。
- `.agents/skills/flowguard/`：唯一的公开技能。
- `tests/`：普通测试和本项目自己的规则。

License: MIT
