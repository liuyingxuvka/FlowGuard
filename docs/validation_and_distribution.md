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

Native execution uses an explicit `--resume` operation. It independently
reconstructs every selected member's current command, complete declared input
set, producer, contract, manifest, suite inventory, obligations, toolchain,
environment, proof, and result identities. Only a terminal-pass full receipt
with an exact match is reported as `reuse_current`; every missing or stale
member executes its declared owner. The terminal report keeps separate
`executed_members` and `reused_members` counts. This is an execution command,
not a read-only receipt audit.

Current native and parent receipts belong under:

```text
.flowguard/evidence/skill-suite/
```

Those receipts are environment-local. The distribution inventory reports their exclusion explicitly instead of copying them into an installed skill package.

## Provider-neutral WorkContext

Every external planning provider retains sole ownership of its native files,
validation, status lifecycle, and finalization operations. FlowGuard may read
only explicitly declared, project-bounded artifacts through a registered
WorkContext adapter. It does not write provider content, execute or wrap
provider checks, open sessions, create caches or receipts, turn provider tasks
into FlowGuard execution owners, or decide provider lifecycle readiness.

FlowGuard models and tests keep their own native owners and evidence. Provider
status is planning context, never FlowGuard test proof.

SkillGuard V2 contract source, compiled contract, and check manifest are the
runtime authority for the current `v2-migration` lifecycle. Former V1 files are
migration evidence only and cannot provide closure or release proof.

## Model Regression Tiers

The checked-in `.flowguard/model-regression-manifest.json` is the execution authority. Filesystem discovery audits that manifest in both directions, but implicit `run_checks.py` discovery does not decide what runs.

The public simulator is the normal single entrypoint. It consumes that same
manifest and invokes each model's declared native runner; it does not import
and reinterpret heterogeneous models itself:

```powershell
python -m flowguard simulator --root . --list
python -m flowguard simulator --root . --model architecture_reduction
python -m flowguard simulator --root . --model "ui_*" --tier focused --json
python -m flowguard simulator --root . --all --tier full --jobs 1 --timeout 900
```

Execution requires at least one `--model` selector or explicit `--all`.
Unmatched selectors fail as invalid input instead of producing an empty pass.
The repository script remains the release-orchestration surface and uses the
same underlying execution owner.

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

A host shell or CI system may run the full command in the background. In human mode, bounded `START` and `DONE` events are written to stderr so a monitor can see which model is active and which children reached a terminal state. Complete child stdout/stderr are stored once as deterministic gzip objects below `objects/sha256/`. Their descriptors separate logical content hash/size from compressed storage hash/size and retain only bounded diagnostic tails in JSON. `receipt.json` remains isolated per child; parent JSON does not contain another full child payload.

Progress proves liveness only. Do not claim completion from a process id, a growing log, a `START` line, or some passing children. The run becomes terminal only after the command exits and the output root contains `report.json` plus `evidence-run.json`, and its scope head references the exact result fingerprint; a passing full claim additionally requires every selected child to be terminal pass, no missing/skipped child, a passing manifest audit, and no tracked mutation.

If no `--output-dir` is supplied, FlowGuard creates an operating-system temporary directory and reports it. For durable local evidence, always provide a distinct output directory such as:

```text
.flowguard/evidence/model-regressions/<run-id>/
```

Do not reuse an old directory as evidence for changed inputs without current freshness verification.

## Evidence Storage And Explicit Cleanup

Executable model source lives in `.flowguard/**/model.py` with its native
`run_checks.py`. Evidence, extra local worktrees, build products, caches, and
release receipts are generated state. They are not additional model versions
and are excluded from the clean installed skill projection.

Every current retained run has an immutable `evidence-run.json`. Its scope has
one atomic `CURRENT.json`; named `PINS.json` bindings may retain release runs.
Modification time never creates evidence authority. Historical directories
without the current manifest are visible as `legacy_unmanaged` and are not
rewritten or made current by inference.

Use the lifecycle commands in order:

```powershell
python -m flowguard evidence-audit --root .flowguard/evidence --json
python -m flowguard evidence-gc-plan --root .flowguard/evidence --keep 2 --preserve skill-suite --output .flowguard/evidence-gc-plan.json --json
python -m flowguard evidence-gc-apply --root .flowguard/evidence --plan .flowguard/evidence-gc-plan.json --json
python -m flowguard evidence-gc-restore --root .flowguard/evidence --quarantine-id <id> --json
python -m flowguard evidence-gc-purge --root .flowguard/evidence --quarantine-id <id> --json
```

Audit and plan are read-only with respect to retained evidence. Apply checks
the exact audit/head/pin/candidate identities again and moves only still-
unreachable candidates. Restore reverses the exact quarantine before purge.
Purge accepts only one quarantine beneath the declared root after current and
pinned replay succeeds. Keep the plan outside the retained evidence root so
writing the plan cannot stale its own audit snapshot. Repeat `--preserve` for
each exact audited legacy root still bound by another workflow. Audit reports
classified, control, and unclassified byte totals; cleanup should not proceed
while unclassified bytes remain. Validation never calls these persistent
cleanup operations automatically.

## Author Sync, Install, Check, Parity, And Uninstall

Set `CODEX_HOME` to the target Codex home. Set
`FLOWGUARD_AUTHOR_SHADOW_SKILLS` to the exact `.agents/skills` directory of an
explicit maintainer workspace. The author shadow is a managed skill tree, not
a second whole-repository copy.

Preview and then synchronize the author shadow without touching surrounding
peer-owned repository files:

```powershell
python scripts/install_flowguard_skills.py author-sync --source . --target $env:FLOWGUARD_AUTHOR_SHADOW_SKILLS --dry-run --json
python scripts/install_flowguard_skills.py author-sync --source . --target $env:FLOWGUARD_AUTHOR_SHADOW_SKILLS --json
```

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
python scripts/install_flowguard_skills.py parity --source . --formal .agents/skills --shadow $env:FLOWGUARD_AUTHOR_SHADOW_SKILLS --installed $env:CODEX_HOME\skills --json
```

Preview and then perform a safe uninstall:

```powershell
python scripts/install_flowguard_skills.py uninstall --codex-home $env:CODEX_HOME --dry-run --json
python scripts/install_flowguard_skills.py uninstall --codex-home $env:CODEX_HOME --json
```

Lifecycle guarantees:

- A repeated unchanged install is idempotent.
- `author-sync` accepts only an explicit author-shadow skill root, never
  `CODEX_HOME`; it changes only the declared 15 members and its ownership
  record, and rolls back an incomplete activation.
- `install` independently projects the clean `consumer_distribution`; it does
  not convert installed consumers into author source.
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

FlowGuard v0.68.7 is source-only. Bind local release readiness to the exact
current ten-owner parent receipt and its frozen validation-input and release
tree manifests. The verifier only reads and compares identities; it never
starts a validation producer:

The parent producer creates one immutable validation observation for its own
invocation. It resolves and semantically verifies each exact-current child once,
reuses those typed results for all declared sibling and aggregate subsets, and
then performs one fresh source-identity comparison after native producers end.
New leaf receipts are published from those exact fresh owner contexts without
per-leaf source rebuilding or receipt-store scans, and their identities are
reconciled once before parent or revision-bundle publication. If any governed source, owner, receipt,
dependency, toolchain, environment, or child identity changed, publication is
blocked. If the final comparison did not run, currentness is `not_run`. The
observation is never a persistent cache or cross-invocation authority, and a
matching final boundary does not repeat unchanged child semantic validation or
add a third repository scan.

Before that final parent owner starts, freeze one accepted v5 model revision
for the same source identity. Its revision-local delta and cumulative
`CurrentEffectiveIntentView` are separate inputs: the latter must reverify every
active intent source and bind the exact current 51-owner self-model denominator
once per owner. The model-regression manifest, compiled self-blueprint,
behavior-commitment ledger, generated field inventory, public API/docs, and
accepted revision must all describe that same frozen source. A one-time intent
bootstrap receipt or a later refinement receipt is model-authority evidence;
neither replaces any of the ten validation-owner receipts.

```powershell
python scripts/verify_flowguard_release.py --root . --phase local-candidate --parent-receipt <parent-receipt-id> --receipt-root .flowguard/evidence/validation-owners --json
```

After committing, verify the immutable local tag against the parent-bound
release tree:

```powershell
python scripts/verify_flowguard_release.py --root . --phase tag --tag v0.68.7 --parent-receipt <parent-receipt-id> --receipt-root .flowguard/evidence/validation-owners --json
```

After pushing the tag and creating an asset-free GitHub Release, verify the
peeled remote tag and release metadata:

```powershell
python scripts/verify_flowguard_release.py --root . --phase published --tag v0.68.7 --parent-receipt <parent-receipt-id> --receipt-root .flowguard/evidence/validation-owners --repository liuyingxuvka/FlowGuard --json
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

原生执行通过显式 `--resume` 操作组合当前证据。它会独立重建每个选中成员的
当前命令、完整声明输入集合、生产者、合同、清单、套件 inventory、义务、工具链、
环境、证明和结果身份；只有完整匹配的终态 full-pass 回执才会标记为
`reuse_current`，缺失或失效的成员必须执行自己的声明负责人。终态报告分别给出
`executed_members` 和 `reused_members`。这是可能执行缺失工作的执行命令，不是
只读回执审计。

当前原生回执和父级回执放在：

```text
.flowguard/evidence/skill-suite/
```

这些回执属于当前环境。分发 inventory 会明确报告它们被排除，而不是把它们复制进安装后的技能包。

### 模型回归分档

`.flowguard/model-regression-manifest.json` 是运行权威。文件发现只用于双向审计清单是否完整，不能再由隐式寻找 `run_checks.py` 决定运行范围。

普通使用统一从公共模拟器入口进入。模拟器消费同一份 manifest，并调用每个
模型自己声明的原生 runner；它不会导入后重新解释不同模型：

```powershell
python -m flowguard simulator --root . --list
python -m flowguard simulator --root . --model architecture_reduction
python -m flowguard simulator --root . --model "ui_*" --tier focused --json
python -m flowguard simulator --root . --all --tier full --jobs 1 --timeout 900
```

执行时必须至少提供一个 `--model` 或明确使用 `--all`。没有匹配项的 selector
会返回 invalid input，不能成为空集合的假通过。仓库回归脚本仍用于 release
编排，但与模拟器共用同一个执行 owner。

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

你可以用宿主 shell 或 CI 把 full 命令放到后台。在人类输出模式下，有限的 `START` / `DONE` event 会写到 stderr，让监控者看到当前模型和已到达终态的 child。完整 stdout/stderr 只存一次，放在 `objects/sha256/` 的确定性 gzip object 中；descriptor 分别记录逻辑内容与压缩存储的 hash/大小，JSON 中只留下有限诊断 tail。每个 child 的 `receipt.json` 仍独立保存，parent JSON 不再复制完整 child payload。

Progress 只证明任务还活着。进程 id、不断增长的 log、`START` 行或部分 child 通过，都不能作为完成证据。只有命令退出、输出根目录同时生成 `report.json` 与 `evidence-run.json`，并且 scope 的 current head 精确绑定该结果指纹后，整次运行才进入终态；full pass 还要求所有选中 child 都是终态 pass、没有 missing/skipped child、manifest audit 通过，并且没有 tracked mutation。

不传 `--output-dir` 时，FlowGuard 会创建操作系统临时目录并在结果中报告。需要持久本地证据时，应显式使用独立目录，例如：

```text
.flowguard/evidence/model-regressions/<run-id>/
```

输入变化后，不要在没有当前 freshness 验证的情况下复用旧目录作为证据。

### 证据存储与显式清理

`.flowguard/**/model.py` 和对应原生 `run_checks.py` 是可执行模型源码。
证据、额外本地 worktree、build 产物、缓存和 release 回执属于生成状态，
不是更多模型版本，也不会进入干净的技能安装投影。

当前持久 run 必须有不可变 `evidence-run.json`，其 scope 使用一个原子更新的
`CURRENT.json`；需要长期保留的 release 可以用 `PINS.json` 精确绑定。
修改时间不会产生权威。没有当前 manifest 的历史目录显示为
`legacy_unmanaged`，不会被推断成 current，也不会被静默改写。

清理严格按以下顺序：

```powershell
python -m flowguard evidence-audit --root .flowguard/evidence --json
python -m flowguard evidence-gc-plan --root .flowguard/evidence --keep 2 --preserve skill-suite --output .flowguard/evidence-gc-plan.json --json
python -m flowguard evidence-gc-apply --root .flowguard/evidence --plan .flowguard/evidence-gc-plan.json --json
python -m flowguard evidence-gc-restore --root .flowguard/evidence --quarantine-id <id> --json
python -m flowguard evidence-gc-purge --root .flowguard/evidence --quarantine-id <id> --json
```

audit 与 plan 不修改持久证据。apply 会再次核对 audit、head、pin 和 candidate
身份，只隔离仍不可达的对象；purge 前可以精确 restore。purge 只能删除声明
root 下一个精确 quarantine，而且 current/pin replay 必须继续有效。plan 必须写在
持久 evidence root 之外，避免计划文件使自己的 audit snapshot 失效；仍被其他流程
引用的 legacy 根应逐个重复传入 `--preserve`。audit 会报告 classified、control 与
unclassified 字节，存在未分类字节时不得开始清理。普通验证永远不会自动调用这些
持久清理操作。

### 作者同步、安装、检查、对比与卸载

把 `CODEX_HOME` 指向目标 Codex home；把
`FLOWGUARD_AUTHOR_SHADOW_SKILLS` 指向一个明确作者工作区的
`.agents/skills`。作者 shadow 是受管理的技能树，不是第二份整仓副本。

先预览，再同步作者 shadow；周围由其他 AI 拥有的仓库文件不会被触碰：

```powershell
python scripts/install_flowguard_skills.py author-sync --source . --target $env:FLOWGUARD_AUTHOR_SHADOW_SKILLS --dry-run --json
python scripts/install_flowguard_skills.py author-sync --source . --target $env:FLOWGUARD_AUTHOR_SHADOW_SKILLS --json
```

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
python scripts/install_flowguard_skills.py parity --source . --formal .agents/skills --shadow $env:FLOWGUARD_AUTHOR_SHADOW_SKILLS --installed $env:CODEX_HOME\skills --json
```

先预览，再安全卸载：

```powershell
python scripts/install_flowguard_skills.py uninstall --codex-home $env:CODEX_HOME --dry-run --json
python scripts/install_flowguard_skills.py uninstall --codex-home $env:CODEX_HOME --json
```

生命周期保证：

- 对未变化内容重复 install 是幂等的。
- `author-sync` 只接受明确的作者 shadow skill root，绝不使用
  `CODEX_HOME`；它只改声明的 15 个成员和自己的 ownership record，激活不完整时
  会整体回滚。
- `install` 独立生成干净的 `consumer_distribution`，不会把已安装 consumer
  变成作者源码。
- `check` 和 `parity` 只读，所以不接受 `--dry-run`。
- 目标 ownership 文件是 `<skills-root>/.flowguard-skill-suite-ownership.json`。
- uninstall 只删除 installer-owned 且仍匹配安装 hash 的文件。
- 用户修改过或不归 installer 拥有的文件会保留，并报告 conflict 或 extra。
- parity 比较完整相对路径集合、raw hash 和规范化 semantic hash；只匹配 `SKILL.md` 和一个 contract 不算完整一致。
- 当前回执、当前报告、progress ledger 和 Python bytecode 只有在命名规则明确报告时才算合法排除。

Distribution pass 只证明文件树一致性和 ownership 安全。它不证明 SkillGuard、路线原生检查、模型回归、测试、OpenSpec verification 或发布后检查已经通过。

### 发布闭环

FlowGuard v0.68.7 只发布源码。本地发布结论必须绑定当前 10 个验证负责人组成的
精确父回执，以及父回执冻结的验证输入清单和发布树清单。验证器只读取并比对
身份，不会启动任何验证生产者：

父验证负责人只在本次调用中建立一份不可变的验证观察：每个精确当前的 child
只解析并做一次语义验证，后续兄弟步骤和多个聚合只引用这份观察中的精确子集；
所有原生生产者结束后，只做一次新的源码/负责人“身份是否变化”比较；新增 child
回执直接使用这次最终观察中的负责人上下文批量发布，不为每个 child 重建源码身份
或单独扫描回执库，随后统一对账一次新增回执。任何源码、负责人、回执、依赖、
工具链、环境或 child 身份发生变化都会阻止发布；最终源码比较或回执对账没有运行
时，当前性必须是 `not_run`。这份观察不是持久缓存，也不能跨调用成为权威；身份
完全一致时，不再重复没有变化的 child 语义验证，也不增加第三次整库源码扫描。

最终父验证负责人开始之前，还必须为同一个源码身份冻结并接受一份 v5 模型修订。
这份修订里的本轮局部变化与累积 `CurrentEffectiveIntentView` 是两个不同输入；
完整当前意图必须重新核实每个有效来源，并对本版精确的 51 个自模型负责人逐一
绑定。模型回归清单、编译后的自蓝图、行为承诺账本、生成的字段清单、公开 API/
文档和已接受修订必须全部描述同一个冻结源码。一次性的意图 bootstrap 回执或
后续 refinement 回执属于模型权威证据，不能代替十个验证负责人的任何一份回执。

```powershell
python scripts/verify_flowguard_release.py --root . --phase local-candidate --parent-receipt <parent-receipt-id> --receipt-root .flowguard/evidence/validation-owners --json
```

提交完成后，先把本地不可变 tag 与父回执绑定的发布树进行比较：

```powershell
python scripts/verify_flowguard_release.py --root . --phase tag --tag v0.68.7 --parent-receipt <parent-receipt-id> --receipt-root .flowguard/evidence/validation-owners --json
```

推送 tag 并创建零资产 GitHub Release 后，再验证剥离后的远端 tag 和 Release 元数据：

```powershell
python scripts/verify_flowguard_release.py --root . --phase published --tag v0.68.7 --parent-receipt <parent-receipt-id> --receipt-root .flowguard/evidence/validation-owners --repository liuyingxuvka/FlowGuard --json
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
