# FlowGuard Validation And Skill Distribution

FlowGuard is an AI-agent skill suite powered by an executable check engine. This guide explains how to validate the current repository without confusing progress with proof, and how to install or compare the complete 15-member skill tree without overwriting user-owned files.

## Evidence Has Three Layers

| Layer | Question answered | Required evidence | Claim boundary |
| --- | --- | --- | --- |
| Prompt and contract structure | Is each skill internally well-formed and route-specific? | canonical 15-member inventory, generated contracts, resolvable references, SkillGuard static/contract/depth results | no route-native behavior has necessarily executed |
| Native evidence receipt | Did one route's real check run against the declared current inputs? | immutable terminal receipt, command and input fingerprints, exact status, covered obligations, independently derived freshness result | covers that route and receipt scope only |
| Self-governance parent closure | Are all required member receipts current and consumed by the parent? | 15 required child identities/fingerprints, exact-pass verification results, inventory and route hashes, parent closure receipt, distribution boundary | covers the declared suite obligations only; it does not predict future agent behavior or prove production correctness |

`pass`, `partial`, `running`, `pass_with_gaps`, and “the command started” are not interchangeable. A parent closure cannot manufacture missing native evidence. When a prompt, contract, checker, model, test, command, dependency, or covered input changes, the affected receipt must be verified again and may require a rerun.

The structural suite command is:

```powershell
python scripts/check_flowguard_skill_suite.py --root . --skillguard all --json
```

It checks the canonical inventory, generated-contract parity, and all 15 SkillGuard static/contract/depth results. Its own claim boundary is structural: native receipts and the evidence-bound parent closure remain separate gates.

Current native and parent receipts belong under:

```text
.flowguard/evidence/skill-suite/
```

Those receipts are environment-local. The distribution inventory reports their exclusion explicitly instead of copying them into an installed skill package.

## Read-only OpenSpec Context

Official OpenSpec remains the sole owner of its proposal, design,
specifications, tasks, validation, status lifecycle, and archive operations.
FlowGuard may read the current authoring files and derive checkbox status as
project-bounded planning context. It does not write OpenSpec, execute or wrap
its checks, open sessions, create caches or receipts, reconcile OpenSpec tasks
into FlowGuard execution owners, or decide archive readiness.

FlowGuard models and tests keep their own native owners and evidence. An
OpenSpec checkbox or derived context status is never FlowGuard test proof.

SkillGuard V2 contract source, compiled contract, and check manifest are the
runtime authority for the current `v2-migration` lifecycle. Former V1 files are
migration evidence only and cannot provide closure or release proof.

## Model Regression Tiers

The checked-in `.flowguard/model-regression-manifest.json` is the execution authority. Filesystem discovery audits that manifest in both directions, but implicit `run_checks.py` discovery does not decide what runs.

| Tier | Intended use | Allowed claim |
| --- | --- | --- |
| `fast` | short development feedback on the smallest registered tier | fast-tier feedback only |
| `focused` | a broader selected set, optionally filtered or sharded | focused feedback for the selected models only |
| `full` | every required non-excluded manifest entry at or below the full tier | may contribute to release evidence only when every selected child has a current terminal pass and the repository stayed non-mutating |

First audit the manifest without running models:

```powershell
python scripts/run_flowguard_model_regressions.py --audit-only --json
```

Run the normal development tier with an explicit evidence directory:

```powershell
python scripts/run_flowguard_model_regressions.py --tier fast --output-dir .flowguard/evidence/model-regressions/fast-local
```

Select a focused family and deterministic shard:

```powershell
python scripts/run_flowguard_model_regressions.py --tier focused --model "ui_*" --shard 1/2 --jobs 1 --output-dir .flowguard/evidence/model-regressions/focused-1 --json
```

Run the release-relevant tier conservatively:

```powershell
python scripts/run_flowguard_model_regressions.py --tier full --jobs 1 --timeout 900 --output-dir .flowguard/evidence/model-regressions/full-local --full
```

`--model` accepts an exact id or glob and may be repeated. `--shard` uses `N/M`. `--jobs` must be positive, and parallel execution is rejected when a selected manifest entry is not shard-safe. `--timeout` overrides each child timeout; it is not an overall release deadline. The default is non-mutating: a tracked-file change blocks the result.

## Concise, JSON, And Full Output

All productized validation output uses one result meaning:

- Default human output is concise: status, scope/tier, counts, first actionable failures or blockers, artifact locations, and claim boundary.
- `--json` emits stable machine-readable fields with no localized preamble.
- `--full` expands human-readable child details and residual risk. It does not change the selected tier or turn a scoped result into a broad pass.

Canonical statuses and exit codes are:

| Status | Exit code | Meaning |
| --- | ---: | --- |
| `pass` | 0 | the declared required scope passed |
| `fail` | 1 | executed validation found a failure |
| `blocked` | 2 | required closure could not be evaluated or satisfied |
| `invalid_input` | 3 | arguments, manifest, or input shape were invalid |
| `timeout` | 4 | required execution exceeded its time bound |
| `cancelled` | 5 | execution was cancelled before complete terminal closure |
| `partial` | 6 | only scoped or incomplete evidence exists |
| `internal_error` | 70 | the validation system itself failed |

## Background Progress Is Not Completion

A host shell or CI system may run the full command in the background. In human mode, bounded `START` and `DONE` events are written to stderr so a monitor can see which model is active and which children reached a terminal state. Child stdout, stderr, and `receipt.json` files are isolated below the chosen output directory.

Progress proves liveness only. Do not claim completion from a process id, a growing log, a `START` line, or some passing children. The run becomes terminal only after the command exits and the output root contains `report.json`; a passing full claim additionally requires every selected child to be terminal pass, no missing/skipped child, a passing manifest audit, and no tracked mutation.

If no `--output-dir` is supplied, FlowGuard creates an operating-system temporary directory and reports it. For durable local evidence, always provide a distinct output directory such as:

```text
.flowguard/evidence/model-regressions/<run-id>/
```

Do not reuse an old directory as evidence for changed inputs without current freshness verification.

## Install, Check, Parity, And Uninstall

Set `CODEX_HOME` to the target Codex home. Set `FLOWGUARD_SHADOW` only when comparing a shadow workspace.

Preview an install without writing:

```powershell
python scripts/install_flowguard_skills.py install --source . --codex-home $env:CODEX_HOME --dry-run --json
```

Install the complete tree, then run the read-only check:

```powershell
python scripts/install_flowguard_skills.py install --source . --codex-home $env:CODEX_HOME --json
python scripts/install_flowguard_skills.py check --source . --codex-home $env:CODEX_HOME --json
```

Canonical author-side install and check first require the packaged authority to
match the complete generated consumer projection:

```powershell
python scripts/compile_flowguard_consumer_suite_authority.py --root . --check --json
```

The installed package ships this exact authority as
`flowguard/consumer-suite-authority.json`. Ordinary project audit and upgrade
compare it directly with `$CODEX_HOME/skills/` and the ownership manifest;
they do not read the author suite map or a project-local copy.

Compare canonical source, formal-repository, shadow-workspace, and installed trees:

```powershell
python scripts/install_flowguard_skills.py parity --source . --formal .agents/skills --shadow $env:FLOWGUARD_SHADOW\.agents\skills --installed $env:CODEX_HOME\skills --json
```

Preview and then perform a safe uninstall:

```powershell
python scripts/install_flowguard_skills.py uninstall --codex-home $env:CODEX_HOME --dry-run --json
python scripts/install_flowguard_skills.py uninstall --codex-home $env:CODEX_HOME --json
```

Lifecycle guarantees:

- A repeated unchanged install is idempotent.
- `check` and `parity` are read-only and therefore do not accept `--dry-run`.
- The target ownership record is `<skills-root>/.flowguard-skill-suite-ownership.json`.
- Uninstall removes only installer-owned files that still match their installed hash.
- User-modified and unowned files are preserved and reported as conflicts or extras.
- Parity compares complete path sets plus raw and normalized semantic hashes; matching only `SKILL.md` and one contract is not enough.
- Each parity root has an explicit role. Formal and shadow maintainer roots use
  `author_source`; installed roots use `consumer_distribution` and are compared
  against the generated clean consumer projection.
- Environment-local receipts, current reports, progress ledgers, and Python bytecode are exclusions only when a named rule reports them.

A distribution pass proves file-tree parity and ownership safety. It does not prove that SkillGuard, native route checks, model regressions, tests, OpenSpec verification, or post-publication checks passed.

## Release Closure

FlowGuard v0.58.4 is source-only. Bind local release readiness to the current
eight-child unified result and verify that no matching wheel or source archive
exists:

```powershell
python scripts/verify_flowguard_release.py --root . --phase local --json
```

After pushing the immutable tag and creating an asset-free GitHub Release,
verify the remote tag and release metadata:

```powershell
python scripts/verify_flowguard_release.py --root . --phase published --tag v0.58.4 --repository liuyingxuvka/FlowGuard --json
```

The published phase reuses the local checks and additionally requires the
remote tag to resolve to the local release commit and a published, non-draft
GitHub Release with zero assets. A failed published check requires a corrective
version; never move the existing tag.

## Claim Checklist

Before writing “FlowGuard passed,” name the actual scope:

1. Which layer passed: structural, native receipt, or parent closure?
2. Which tier and filters ran?
3. Are all required children terminal, current, and exact pass?
4. Where are the final receipts and full artifacts?
5. Were skipped checks, blockers, stale evidence, and residual risk reported?
6. Does source/formal/shadow/installed parity matter for this claim, and is it current?

Only a separate release closure can combine these results with the full test suite, OpenSpec verification, package/version/tag agreement, remote publication, and post-publication verification.

---

## 中文说明

FlowGuard 是一套由可执行检查引擎驱动的 AI-agent 技能套件。本说明告诉你怎样验证当前仓库而不把“还在运行”误当成“已经证明”，也说明怎样安全安装或比较完整的 15 项技能树，而不覆盖用户自己的文件。

### 证据有三层

| 层级 | 回答的问题 | 必须有的证据 | 声明边界 |
| --- | --- | --- | --- |
| 提示词与合同结构 | 每项技能是否结构完整、route-specific？ | canonical 15 项 inventory、生成合同、可解析引用、SkillGuard static/contract/depth 结果 | 不代表路线原生行为已经执行 |
| 原生证据回执 | 某条路线的真实检查是否针对声明的当前输入运行？ | 不可变终态回执、命令和输入指纹、exact status、覆盖义务、独立推导的新鲜度结果 | 只覆盖该路线和该回执 scope |
| 自治理父闭环 | 父级是否消费了所有必需成员的当前回执？ | 15 个必需 child 的 identity/fingerprint、exact-pass 验证结果、inventory/route hash、父级闭环回执、分发边界 | 只覆盖声明的技能套件义务；不预测未来 agent 行为，也不证明生产系统整体正确 |

`pass`、`partial`、`running`、`pass_with_gaps` 和“命令已经启动”不是一回事。父级闭环不能凭空制造缺失的原生证据。提示词、合同、检查器、模型、测试、命令、依赖或覆盖输入一旦变化，受影响回执必须重新验证，也可能必须重跑。

### 只读 OpenSpec 上下文

官方 OpenSpec 独立拥有 proposal、design、spec、tasks、验证、状态生命周期
和归档。FlowGuard 只能在当前项目内读取这些编写材料，并根据任务勾选情况
生成只读的规划上下文；不能修改 OpenSpec、包装或执行其检查、创建会话/
缓存/回执、把 OpenSpec 任务变成 FlowGuard 测试负责人，也不能替 OpenSpec
判断能否归档。

FlowGuard 的模型和测试分别拥有自己的执行者与证据。OpenSpec 的任务勾选
或上下文状态不能当成 FlowGuard 检查已经运行的证明。

结构层的技能套件命令是：

```powershell
python scripts/check_flowguard_skill_suite.py --root . --skillguard all --json
```

它核对 canonical inventory、生成合同一致性，以及 15 项 SkillGuard static/contract/depth 结果。它自己的声明边界是“结构通过”；原生回执和证据绑定的父闭环仍是独立 gate。

当前原生回执和父级回执放在：

```text
.flowguard/evidence/skill-suite/
```

这些回执属于当前环境。分发 inventory 会明确报告它们被排除，而不是把它们复制进安装后的技能包。

### 模型回归分档

`.flowguard/model-regression-manifest.json` 是运行权威。文件发现只用于双向审计清单是否完整，不能再由隐式寻找 `run_checks.py` 决定运行范围。

| 档位 | 用途 | 可以怎么声明 |
| --- | --- | --- |
| `fast` | 最小注册范围的短周期开发反馈 | 只能说 fast-tier 范围通过 |
| `focused` | 更宽的选定范围，可加 filter 或 shard | 只能说选中模型的 focused 范围通过 |
| `full` | 所有必需且未明确排除的 manifest 项 | 只有每个选中 child 都有当前终态 pass、且仓库未被修改时，才可以参与 release 证据 |

先只审计 manifest：

```powershell
python scripts/run_flowguard_model_regressions.py --audit-only --json
```

运行日常 fast 档，并指定证据目录：

```powershell
python scripts/run_flowguard_model_regressions.py --tier fast --output-dir .flowguard/evidence/model-regressions/fast-local
```

选择 focused family 和确定性 shard：

```powershell
python scripts/run_flowguard_model_regressions.py --tier focused --model "ui_*" --shard 1/2 --jobs 1 --output-dir .flowguard/evidence/model-regressions/focused-1 --json
```

保守运行 release 相关的 full 档：

```powershell
python scripts/run_flowguard_model_regressions.py --tier full --jobs 1 --timeout 900 --output-dir .flowguard/evidence/model-regressions/full-local --full
```

`--model` 可以是精确 id 或 glob，也可以重复。`--shard` 格式是 `N/M`。`--jobs` 必须大于零；如果选中的 manifest 项不是 shard-safe，并行会被拒绝。`--timeout` 覆盖的是每个 child 的 timeout，不是整次发布 deadline。默认运行不得修改 tracked file；发现修改会阻断结果。

### 精简、JSON 与完整输出

- 默认人类输出只显示 status、scope/tier、counts、前几个可行动 failure/blocker、artifact 位置和 claim boundary。
- `--json` 输出无本地化前缀的稳定机器字段。
- `--full` 展开人类可读的 child 详情和 residual risk；它不会改变 tier，也不会把 scoped 结果升级成 broad pass。

Canonical status 和退出码：

| Status | 退出码 | 含义 |
| --- | ---: | --- |
| `pass` | 0 | 声明的必需 scope 全部通过 |
| `fail` | 1 | 已执行验证发现失败 |
| `blocked` | 2 | 必需闭环无法评估或无法满足 |
| `invalid_input` | 3 | 参数、manifest 或输入结构无效 |
| `timeout` | 4 | 必需执行超过时间边界 |
| `cancelled` | 5 | 在完整终态闭环前被取消 |
| `partial` | 6 | 只有局部或不完整证据 |
| `internal_error` | 70 | 验证系统本身失败 |

### 后台进度不等于完成

你可以用宿主 shell 或 CI 把 full 命令放到后台。在人类输出模式下，有限的 `START` / `DONE` event 会写到 stderr，让监控者看到当前模型和已到达终态的 child。每个 child 的 stdout、stderr 和 `receipt.json` 会隔离在选定输出目录下面。

Progress 只证明任务还活着。进程 id、不断增长的 log、`START` 行或部分 child 通过，都不能作为完成证据。只有命令退出并在输出根目录生成 `report.json` 后，整次运行才进入终态；full pass 还要求所有选中 child 都是终态 pass、没有 missing/skipped child、manifest audit 通过，并且没有 tracked mutation。

不传 `--output-dir` 时，FlowGuard 会创建操作系统临时目录并在结果中报告。需要持久本地证据时，应显式使用独立目录，例如：

```text
.flowguard/evidence/model-regressions/<run-id>/
```

输入变化后，不要在没有当前 freshness 验证的情况下复用旧目录作为证据。

### 安装、检查、对比与卸载

把 `CODEX_HOME` 指向目标 Codex home；只有比较 shadow workspace 时才需要 `FLOWGUARD_SHADOW`。

先预览安装：

```powershell
python scripts/install_flowguard_skills.py install --source . --codex-home $env:CODEX_HOME --dry-run --json
```

安装完整文件树，再运行只读检查：

```powershell
python scripts/install_flowguard_skills.py install --source . --codex-home $env:CODEX_HOME --json
python scripts/install_flowguard_skills.py check --source . --codex-home $env:CODEX_HOME --json
```

比较 canonical source、formal repository、shadow workspace 和 installed tree：

```powershell
python scripts/install_flowguard_skills.py parity --source . --formal .agents/skills --shadow $env:FLOWGUARD_SHADOW\.agents\skills --installed $env:CODEX_HOME\skills --json
```

先预览，再安全卸载：

```powershell
python scripts/install_flowguard_skills.py uninstall --codex-home $env:CODEX_HOME --dry-run --json
python scripts/install_flowguard_skills.py uninstall --codex-home $env:CODEX_HOME --json
```

生命周期保证：

- 对未变化内容重复 install 是幂等的。
- `check` 和 `parity` 只读，所以不接受 `--dry-run`。
- 目标 ownership 文件是 `<skills-root>/.flowguard-skill-suite-ownership.json`。
- uninstall 只删除 installer-owned 且仍匹配安装 hash 的文件。
- 用户修改过或不归 installer 拥有的文件会保留，并报告 conflict 或 extra。
- parity 比较完整相对路径集合、raw hash 和规范化 semantic hash；只匹配 `SKILL.md` 和一个 contract 不算完整一致。
- 当前回执、当前报告、progress ledger 和 Python bytecode 只有在命名规则明确报告时才算合法排除。

Distribution pass 只证明文件树一致性和 ownership 安全。它不证明 SkillGuard、路线原生检查、模型回归、测试、OpenSpec verification 或发布后检查已经通过。

### 发布闭环

FlowGuard v0.58.4 只发布源码。把本地发布结论绑定到当前统一门禁的 8 个子结果，
并确认不存在对应版本的 wheel 或源码包：

```powershell
python scripts/verify_flowguard_release.py --root . --phase local --json
```

推送不可变 tag 并创建零资产 GitHub Release 后，再验证远端 tag 和 Release 元数据：

```powershell
python scripts/verify_flowguard_release.py --root . --phase published --tag v0.58.4 --repository liuyingxuvka/FlowGuard --json
```

published 阶段会重新检查本地条件，并要求远端 tag 指向同一提交、Release 已发布且不是 draft、资产列表为空。若发布后验证失败，应发布新的修正版，不能移动已有 tag。

### 声明前检查

在写“FlowGuard 已通过”之前，至少回答：

1. 通过的是结构层、原生回执层，还是父闭环层？
2. 运行了哪个 tier 和 filter？
3. 所有必需 child 是否都是 current、terminal、exact pass？
4. 最终回执和完整 artifact 在哪里？
5. skipped check、blocker、stale evidence 和 residual risk 是否明确报告？
6. 这个声明是否需要 source/formal/shadow/installed parity，它现在是否有效？

只有独立的 release closure 才能把这些结果与完整测试、OpenSpec verification、package/version/tag 一致性、远端发布和发布后验证组合起来。
