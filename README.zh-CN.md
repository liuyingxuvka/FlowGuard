# FlowGuard

<p align="center"><img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" /></p>

[English](./README.md)

FlowGuard 帮写代码的 AI 找到已有判断，并在以后改动时保持必要副本一致。代码地图由工具生成。只有一个判断在几处、主人说“所有地方”、或修了一个 bug 时才写规则；普通修改仍用普通测试。

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

规则从要求独立写出预期；家的适配函数调用真实函数；字面情况行保留已知回归。[本地规则指南](./.agents/skills/flowguard/references/rules.md)含完整的两家例子，会和技能一起复制。


任一副本改动后，`check` 通过普通 pytest 执行当前源码。不一致为红，没验证的边界为灰。刚写的权威文档可能显示 green*，这不等于独立确认。

## 日常命令

| command | purpose |
| --- | --- |
| `python -m flowguard` | 项目已有规则时读取短屏幕和缓存，不运行测试。 |
| `python -m flowguard show "what it decides"` | 新写判断之前找已有负责人和静态候选。 |
| `python -m flowguard show WINDOW` | 读规则、出处、家和完整发现。 |
| `python -m flowguard show --draft orders:accept` | 为适配函数定位已有测试，不编造预期答案。 |
| `python -m flowguard check` | 通过普通 pytest 重查受影响的规则和测试。 |
| `python -m flowguard check --all` | 在 CI 运行所有意图项和普通项目测试。 |
| `python -m flowguard req list` | 列出已存原话；`show R1` 读取原文。 |

没有规则时，检查只说一行：

```text
FlowGuard check: no intent rules.
```

情况行保持字面值，不会悄悄缩水。出处、帮助代码、数据和实现变化都会使依赖结果失效。必要副本要明确绑定，候选相似不构成等价证明。`check --all` 为完整套件记录测试与代码的联系，局部 `check` 重录选中的测试。这些联系用于选择受影响测试，并为适配函数定位已有测试。直接运行 pytest 时，不普遍跟踪未标记的普通测试；明确标记的守护测试仍记录联系。联系缺失时按源码依赖保守选择。完整采集保留这些真实联系，因此会多做一些必要工作。

## 边界和迁移

规则检查声明的输入和真实绑定，不证明事实真伪，也不覆盖应用所有行为。灰色说明尚未验证什么。保留普通测试和审查。相似但必须不同的判断用 `distinct`，替代用 `supersedes`，只有下层判断确实简化上层规则时才用 `uses`。

旧状态机、后台任务、图片和发布测试运行器已退役。`status`、`where`、`draft`、`decide`、`release` 不保留兼容别名。保留原话档案，把有用的旧契约迁成规则和行，再删旧模型。详见[意图指南](./docs/intent-guide.md)和[迁移指南](./docs/upgrade-2.0.md)。

## 仓库

- `flowguard/structure/`：生成代码地图和固定源码查询。
- `flowguard/intent/`：规则、家和 pytest 集成。
- `flowguard/map/`：共享源码及原话字节读取。
- `.agents/skills/flowguard/`：唯一公开技能。
- `tests/`：普通控制和项目自己的意图规则。

License: MIT
