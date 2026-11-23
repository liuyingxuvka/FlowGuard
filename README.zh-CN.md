# FlowGuard

<p align="center"><img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" /></p>

[English](./README.md)

FlowGuard 在 AI 改项目时检查已经登记的约定：哪些副本必须一致、哪些字段必须一起写、谁可以写某个字段。普通测试会检查这些约定、独立意图规则和兜底账本。

发现问题仍靠认真审查。发现以后，在同一次改动里登记约定，让后续工作不能悄悄破坏它。缺失的业务决定由主人作出。

## 开始

从这个仓库安装；PyPI 上同名的项目不是本工具。需要 Python 3.11 或更新版本。

```bash
python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git"
cd your-project
python -m flowguard init
python -m flowguard new-task
python -m pytest
```

`init` 接好项目测试，写入 FlowGuard 规则块并生成 CI 片段。`AGENTS.md` 或 `CLAUDE.md` 里的规则块与当前版本写的不同时，简报会指出；再运行一次 `init` 即可改写。Vitest 或 Jest 项目还会生成静态检查测试，说明哪个 npm 脚本会跑它；Vitest 会接上执行侧。接好以后，使用项目平时的测试命令。

`new-task` 记下任务起点。任务中途提交不会移动这个基准；没有基准时，第一次测试也会记下。没有意图规则时，检查输出：

```text
FlowGuard 5.0 (since 99f025e): 0 red; 0.2 s
```

## 日常使用

1. 开工时运行 `python -m flowguard new-task`，读简报。
2. 跑项目普通测试，读测试汇总后的 FlowGuard 块。首行给出每一类的数目；pytest 运行在选中的测试全部跑完之前就结束时，首行也会写明（`run ended early (exit 3): 2 of 3 selected tests ran, the rest not checked`）。只有 `red` 使测试失败：这次改动破坏了已登记的约定，要改代码。`before` 和 `known` 在任务开始前就有：`->` 后面写明已知的情况和由谁决定，什么时候向主人提出未决的问题由你决定。`changed` 表示某个函数对测试用过的输入返回了别的结果：是有意的改动就在汇报里说明；结果是字典时，这一行列出变化的键（`now adds demandPeriodConvention='legacy-half-open' (3 other keys equal)`）。`impact` 和 `not compared` 不算失败；`not compared` 是没有验证，不算通过；vitest 运行没有收到地图检查的结果时，会单独占一行 `not compared` 说明。`python -m flowguard show --last` 列出上一次运行的每一行和细节：每个 vitest 包各一次，pytest、`check` 和 `check --static` 共一次，附 pytest 自己的退出码和失败数，以及简报计入的失败测试。
3. 修改另一份实现之前，用 `python -m flowguard show "what it decides"` 查函数、模型、字段和约定；地图不认识的名字会直说。对 Python 类的字段，`show Settings.appearance` 列出写它的地方，以及通过 `self`、带类型注解的名字或已声明类型的字段读它的函数（对它调用 asdict 和 vars 也算），`impact` 行数的就是这些（`5 readers (untyped reads not counted)`）：通过没有类型的名字读取不计入。这次改动不再写的字段，会列出任务开始时写它和读它、而现在已没有函数这样做的地方。

同时工作的几个智能体各用一个 git worktree（`git worktree add ../task-b`，然后在那里运行 `python -m flowguard new-task`）：每个 worktree 有自己的 `.flowguard/cache`、任务基准和改动集。同一个工作树里的智能体共用这些：一个智能体运行 `new-task` 会移动所有智能体的基准，每个智能体未提交的修改也算进其他智能体的改动。

## 登记约定

Python 用 `#`，TS/JS 用 `//`。每份必须一致的判断都写 `same NAME`；已经选定哪份作数时，在那份加 `ref`：

```python
# flowguard: same ROUND ref
def round_amount(value: float) -> int:
    return round(value)

# flowguard: same ROUND
def preview_amount(value: float) -> int:
    return round(value)
```

数据约定分开写：

```python
# flowguard: together Booking.employee_id Booking.unit_id on=update
# flowguard: writers Booking.employee_id reserve,release
```

`together A B,C` 是单向约定：写 A 的操作也必须写 B、C。`on=` 只取 `create` 或 `update`；`B=值` 要求写成该值，布尔值和空值两种语言的写法是同一个值（`=true` 与 `=True`、`=false` 与 `=False`、`=null` 与 `=None`）。Python 元组或列表赋值（`self.a, self.b = ...`，嵌套的和带星号的也算）以及 `for`、`with ... as` 目标里的每个名字各算一次写入。`together` 检查的是一次写入包含哪些字段，`B=值` 检查一个固定值；随条件变化的取值（缺少负责人时两个字段都为空）由测试负责，`0 red` 对它什么也没说。裸函数名只指注释所在文件；别的文件写仓库相对位置，例如 `src/store.py:reserve`。例外写成 `except=路径:函数(理由)`；加上例外就放宽了约定，这由主人决定。不要为了消掉发现而放宽约定。

FlowGuard 5.0 删除了 4.2 的注释写法（`sensor NAME`、`owner NAME`、`owner A with=...`、`alone=`、`owner A writers=...`）：每一处都在所在行报 red，并给出应改写成的 4.3 注释。

## 规则与兜底理由

`tests/intent/` 中的规则独立写出预期，并注明出处。主人的原话用 `python -m flowguard req add <file|-> --id R1` 逐字节保存一次。文档出处要引用 `authority_docs` 所列文件中的原句，不能把 AI 方案存成主人原话。

主人从你给出的选项中选了一个，这也是他的原始选择。把他的回答连同选项一起存下：`python -m flowguard req add reply.md --id R2 --offer options.md --picked "A. Keep one version"`。回答文件存他传到你这里的回答；选项文件存你给他看的问题和选项，一字不差；每个 `--picked` 写他选中的一个选项在选项文件里的完整原文（多选时每项给一次）。他只是点选、没有打字时加 `--selected`：回答文件存的就是界面为他的点选返回的内容，不是他的话。选项作为 AI 的话存在 `.flowguard/requests/offers/`，绝不算他的原话。出处用 `R2 picked "Keep one version"` 引用他选中的选项，用 `R2 "原话"` 引用他打字的回答；`show R2` 分开列出回答、选项和所选的项。

`.flowguard/rules.toml` 存主人现行的规则，每条一行文字，出处逐字引用存下的原话或文档原句。`.flowguard/known.toml` 存还没定论的事和对待方式：`act = "ask"` 是只有主人能答的问题，`leave` 是有意留着不动的问题，`fix` 是改到相关代码时就修的明确错误，`ignore` 是结构检查的误报。`python -m flowguard known add FINDING --act leave --why TEXT` 按上一次运行报出的某个 finding 的位置写入一条（`show --last` 列出每个 finding 的名字）。同名而相似的函数是否必须分开保留（比如不能导入应用的构建脚本），由主人决定：copies 行会说明它们有多相似，并给出 `known add copies:NAME --act ignore --why TEXT`，它记下每一份副本的位置，并让这条发现不再计入简报的数目；`show --last` 另列每份副本的签名、调用者和两者第一处不同的行。`python -m flowguard show rules` 列出两者，`new-task` 的简报会列出其中靠前的几条；`show NAME` 和 `show PATH` 开头先列出与这个名字、文件或文件夹有关的条目、规则和 flowguard 注释约定。

`.flowguard/ledger.toml` 记录能不抛出就结束的异常处理，注明数量、理由和依据的成文规则。`python -m flowguard ledger init` 记录已有处理，`python -m flowguard ledger check` 检查账本。不能登记的形式由发现行说明。

可执行的双副本规则示例和上下文注释见[本地参考](./.agents/skills/flowguard/reference.md)。

## 文档与代码挂钩

在描述代码的 Markdown 文字上方写 `<!-- flowguard: about path:symbol -->`（或只写文件路径）。改动改了那段代码却没改这段文字时，运行会用一行 `impact` 点出这段文字。标记的位置可以是仓库里的任何文件，数据文件或提交进仓库的生成文件也可以：ZIP 或 JSON 文件里写不了标记，所以在一段 Markdown 文字里列出这些生成文件，每个文件上方写标记，分别指向生成它的函数和它所依据的每个文件（叠在同一行上方的几个标记都描述这一行），并写明重新生成它的命令；函数读取的数据文件，上方写一个指向它自己的标记和一个指向读取它的函数的标记。之后改了这样的文件（`src/app/resources/model.json`、`docs/manual.txt`），pytest 和 `check --static` 都会点出它那一行。描述一个文件或 `folder/` 的文字就是这个模块的契约：它调用的函数或调用它的函数改了，只要调用还在，也会点出它（某个路由是否调用了它的负责函数由测试负责：别的文件里删掉对这个模块的调用的改动，不会点出这段文字）；`python -m flowguard show PATH` 列出模块的契约和连接；函数或常量的 `show NAME` 以及文档的 `show` 列出把它们联系起来的文字和标记；标记只有在 `check --static` 把它的位置解析到这个名字时才算，列出某个文件的函数或常量、或某个模型字段的生成区也算描述它们的文字。代码里已有的清单放在 `<!-- flowguard: generate fields Model -->`（或 `values NAME`、`functions path`、`constants path`）和 `<!-- flowguard: end -->` 之间，由 `python -m flowguard docs` 写入。生成区只放 map 知道的内容，Purpose 这类说明文字放在生成区之外。`python -m flowguard show Model.field`（或它的 `table.column`）开头先列出 Prisma schema、SQL 文件和 zod schema 如何声明这个字段，这个字段自己的 zod schema 排在前面（每个 schema 对象归属于它的驼峰词里包含的最长模型名）；以它为准，而不是文档里的表格。

## 其他检查与语言

`python -m flowguard check --static` 不跑测试；它也检查规则和 known 条目引用的出处，这些出处不必等长测试跑完，`python -m flowguard show rules` 说明每条出处是否成立。加 `--all` 查看完整结构清单。`python -m flowguard check` 跑受影响的规则和测试。已有深查和有限 flow 保持冻结，不属于上面的日常接入步骤。

基础安装读取 Python。TS/JS、Prisma、SQL 及冻结的 C/C++/C# 读取器使用 `flowguard[languages]`。Vitest 的 ESM 项目支持执行观察；Jest 只做静态检查。测试结束后的封闭比较跑不了的函数记为 `not compared`，并写明原因；任务起点的版本会把某次调用的参数当成别的参数时（比如在最前面插入了必填参数），这次调用也记为 `not compared`，在末尾加一个带默认值的参数则照常比较。参数不同的同名副本在 `check --static`、pytest 和 vitest 里都只报一行红，写明每个副本的参数和声明的返回类型：先确认它们是不是同一个决定的副本。Python 副本可以写明参数名的对应（`same NAME(days=overdue_days)`）；TS/JS 注释不写参数，TS/JS 副本按位置比较。测试输入上的一致不能证明业务答案正确。

保存在仓库里的 SQL 文件（比如手工安装的数据库升级包）描述它所创建的表，并与 Prisma schema 比较；只修改表的文件不描述任何表。有意保留过时的描述时，指定它某个文件里的一张表来记录：`python -m flowguard known add columns:prisma/migrations/~prisma/schema.prisma --site prisma/migrations/20240101_init/migration.sql:central_employees --act leave --why TEXT`。

列在 `[tool.flowguard] exclude = ["translations/*.ts"]` 里的文件（路径从项目根目录算，`**` 跨文件夹）从不被读取，任务起点的版本也不读，也不需要装它的读取器；一个改动把某个文件加进这个列表时，它原有的每条约定都是一行 `loosened`；任务起点的 pyproject.toml 解析不了时，这些文件记为一行 `not compared`。没被排除、读取器又没装的文件会让 `check --static` 带着错误原文退出（退出码 2），在 pytest 里则是 pytest 自己的汇总之后的一行红色 `map checks`。

FlowGuard 只在测试运行里起作用。它从不在测试里把函数再跑一遍；打包、开发服务器和正式运行都不会加载它。运行期间被另一个智能体或某个测试保存过的源文件，其中的函数从此不再记录：它们记为 `not compared`，每个测试都和不带 FlowGuard 时一样运行。同一仓库可以同时有几次运行，比如两个包各自的检查，或 vitest 运行与 `check --static` 并行：每次运行只等另一次运行对缓存的短暂写入，等满 5 秒会在 stderr 说明；vitest 运行则在第一行说明（`waited 9 s for .flowguard/cache/map.sqlite`）。

## 兼容与仓库

保留的旧输入和 API 继续支持；5.0 删除的功能会被拒绝并给出替代写法，不会悄悄改变旧输入的含义；FlowGuard 0.70 到 1.4 的顶层命令也一样：`flowguard: read was removed in 1.0 -> python -m flowguard show "words"`，退出码 2。现有契约见 [4.1 说明](./docs/upgrade-4.1.md)、[4.2 说明](./docs/upgrade-4.2.md)、[4.3 说明](./docs/upgrade-4.3.md)、[5.0 说明](./docs/upgrade-5.0.md) 和 [intent guide](./docs/intent-guide.md)。

- `flowguard/structure/`：源码事实与固定查询。
- `flowguard/intent/`：约定、意图规则、账本和测试适配器。
- `flowguard/map/`：共用读取器和不可改的主人原话记录。
- `.agents/skills/flowguard/`：唯一公开技能和本地参考。
- `tests/`：普通测试和本项目自己的规则。

License: MIT
