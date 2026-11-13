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

`init` 接好项目测试，写入 FlowGuard 规则块并生成 CI 片段。Vitest 或 Jest 项目还会生成静态检查测试，说明哪个 npm 脚本会跑它；Vitest 会接上执行侧。接好以后，使用项目平时的测试命令。

`new-task` 记下任务起点。任务中途提交不会移动这个基准；没有基准时，第一次测试也会记下。没有意图规则时，检查输出：

```text
FlowGuard 4.3 (since 99f025e): 0 red; 0.2 s
```

## 日常使用

1. 开工时运行 `python -m flowguard new-task`，读简报。
2. 跑项目普通测试，读测试汇总后的 FlowGuard 块。首行给出每一类的数目。只有 `red` 使测试失败：这次改动破坏了已登记的约定，要改代码。`before` 和 `known` 在任务开始前就有：照 `->` 后面写的做，写着 `ask owner` 时才告诉主人。`changed` 表示某个函数对测试用过的输入返回了别的结果：是有意的改动就在汇报里说明。`impact` 和 `not compared` 不算失败；`not compared` 是没有验证，不算通过。`python -m flowguard show --last` 列出上一次运行的每一行和细节。
3. 修改另一份实现之前，用 `python -m flowguard show "what it decides"` 查函数、字段和约定。

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

`together A B,C` 是单向约定：写 A 的操作也必须写 B、C。`on=` 只取 `create` 或 `update`；`B=值` 要求写成该值。裸函数名只指注释所在文件；别的文件写仓库相对位置，例如 `src/store.py:reserve`。例外写成 `except=路径:函数(理由)`，需要主人同意。不要为了消掉发现而放宽约定。

旧注释写法继续接受并提示弃用；内部登记和保存输入仍按原义读取。

## 规则与兜底理由

`tests/intent/` 中的规则独立写出预期，并注明出处。主人的原话用 `python -m flowguard req add <file|-> --id R1` 逐字节保存一次。文档出处要引用 `authority_docs` 所列文件中的原句，不能把 AI 方案存成主人原话。

`.flowguard/rules.toml` 存主人现行的规则，每条一行文字，出处逐字引用存下的原话或文档原句。`.flowguard/known.toml` 存还没定论的事和对待方式：`act = "ask"` 是只有主人能答的问题，`leave` 是主人推迟的问题，`fix` 是改到相关代码时就修的明确错误，`ignore` 是结构检查的误报。`python -m flowguard show rules` 列出两者，`new-task` 的简报会列出其中靠前的几条。

`.flowguard/ledger.toml` 记录能不抛出就结束的异常处理，注明数量、理由和依据的成文规则。`python -m flowguard ledger init` 记录已有处理，`python -m flowguard ledger check` 检查账本。不能登记的形式由发现行说明。

可执行的双副本规则示例和上下文注释见[本地参考](./.agents/skills/flowguard/reference.md)。

## 其他检查与语言

`python -m flowguard check --static` 不跑测试；加 `--all` 查看完整结构清单。`python -m flowguard check` 跑受影响的规则和测试。已有深查和有限 flow 保持冻结，不属于上面的日常接入步骤。

基础安装读取 Python。TS/JS、Prisma、SQL 及冻结的 C/C++/C# 读取器使用 `flowguard[languages]`。Vitest 的 ESM 项目支持执行观察；Jest 只做静态检查。测试结束后的封闭比较跑不了的函数记为 `not compared`，并写明原因。测试输入上的一致不能证明业务答案正确。

FlowGuard 只在测试运行里起作用。它从不在测试里把函数再跑一遍；打包、开发服务器和正式运行都不会加载它。

## 兼容与仓库

保留的旧输入和 API 继续支持；弃用功能会提示删除计划，不会悄悄改变旧输入的含义。现有契约见 [4.1 说明](./docs/upgrade-4.1.md)、[4.2 说明](./docs/upgrade-4.2.md)、[4.3 说明](./docs/upgrade-4.3.md) 和 [intent guide](./docs/intent-guide.md)。

- `flowguard/structure/`：源码事实与固定查询。
- `flowguard/intent/`：约定、意图规则、账本和测试适配器。
- `flowguard/map/`：共用读取器和不可改的主人原话记录。
- `.agents/skills/flowguard/`：唯一公开技能和本地参考。
- `tests/`：普通测试和本项目自己的规则。

License: MIT
