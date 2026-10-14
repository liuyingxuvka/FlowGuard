# FlowGuard 0.70.1 修复交接记录

2026-10-14。基线：main `f9b4633b26a99fa58cb339cc936d18579fa3860d`，0.70.0。
只更新末位版本至 **0.70.1**。以下实施对应 2026-10-14 修订的 A01—A10，不恢复退役框架。

## 完成表

| 项目 | 状态和实际改动 | 验收与边界 |
| --- | --- | --- |
| A01 影响闭包 | 完成。`map/impact.py` 默认完整反向 BFS；`cli.py` 保留明确 `--depth` 截断并提示。实际依赖与合法声明并用；`deps --write` 保留未验证声明。 | 三层链、环、无关组件排除、声明的 lazy/TS alias 用例通过。不自动解析任意动态门面或 tsconfig。 |
| A02 检查回指 | 完成。共享测试、顶层模型、owner model/helper、runner、删除/重命名和旧地图验证字段差异均进入范围；输出注册表真实 ID，未知归属非零。 | 有限变化场景通过；summary 单独变化只审阅。旧地图仅用于 git 变更范围，没有第二权威。 |
| A03 PASS 缓存 | 完成。`map/proof.py` 使用既有 COMPONENTS/依赖闭包、直接锚点、模型、地图和 Python/引擎摘要；未知输入重跑，仅存 PASS；runner 不缓存。扩展既有 `model_cache.py`。 | helper 变坏普通运行立即 FAIL；完整边界第二次可复用；未知 helper/config、引擎变化和失败修复回归通过。缓存自模型保留抽象探索，真实回放限制五个明确场景。 |
| A04 执行诚实性 | 完成。`mapfile.model_registry` 是共同模型清单；check 和 proof 复用。未知/混合 selector、重复 ID、不支持路径、空坏例子、无效 conformance 和普通 Python 解析错误均失败。 | release 实际 **34 declared / 34 executed / 34 passed**。零模型明确没有模型证明；误用组件 ID 提示实际模型 ID。 |
| A05 真实测试结果 | 完成。现有 `model_test_alignment.py` 增加薄接入 `bind_pytest_execution` 与输入摘要；复用现有 JUnit/parser/nodeid recorder。触及的 owner runner 准确声明 30 个抽象规则检查及“执行证据未提供”。 | passed/failed/skipped/未收集/运行中变化/运行后变化、全局非零、漏输入及错误绑定均验证。最终外层 pytest 的一个真实指纹义务经源码审计和结果接入后通过；不宣称全仓业务义务已全面绑定。无嵌套 pytest。 |
| A06 源码绑定 | 完成。`model_test_alignment_source.py` 拒绝未知/错误 receiver 的同名调用、恒真断言和无值依赖断言；支持简单 import/alias 和直接结果/直线局部赋值。 | 合法直接/别名返回值断言通过，错误 receiver/恒真断言阻断；纯设计 not_run 保留。复杂数据流与动态 receiver 仍需人工审阅。 |
| A07 自地图/模型 | 完成。登记八个组件已有真实测试，新增且仅新增一个 `change_impact.py`；公共 lazy facade 的 27 个 owner 依赖明确登记为未验证声明。更新描述和指纹。 | 新模型七个有限场景、两个坏版本及真实回放通过；缓存沿用 A03；skill-assets 如实注明分发测试与模型执行覆盖的差别。 |
| A08 完整模板 | 完成。移除旧 TestEvidence 参数/reuse ticket 演示，五类构造器及派生契约使用一致业务/承诺/路径 ID；样本证据标为演示。 | 生成后实际运行六报告 **[True, False, True, False, True, False]**，未放松身份检查。 |
| A09 文档与可见性 | 完成。发布输出保留五项债务与原因；历史自审文档明确旧结果/退役 CLI；read 说明可能写缓存、截断未读数量；更新短技能说明。 | lint 零 error；两组声明依赖警告明确可见。没有新 debt schema、审批门槛或全架构重构。 |
| A10 性能 | 测量完成，无需性能工程，停止。仅有限输出与同次 modelrun 的摘要复用。 | 同机预热中位数 read 0.2002s、component read 0.1454s、无变更 change 0.3610s，均在原基线两倍以内。 |

所有源码均在既有 owner 内修改。新增产品核心自模型只有一份；新增真实结果回归文件是一组有限测试，不是另一套测试框架。14 项能力保留。

## 实际验证

- 修改期间按负责文件运行对应 pytest、专项模型和生成模板执行；所有针对性检查通过。
- 最终 `python -m flowguard read`：输出 **11,912** 字符，截断明确提示未完全展示范围。
- 最终 `python -m flowguard change`：退出 0，结构检查 **0 error / 2 warning**，列出真实测试和模型 ID。
- 最终完整测试一次：`FLOWGUARD_PYTEST_NODEIDS=.flowguard/cache/final-nodeids.json python -m pytest -q -p flowguard.pytest_nodeid_recorder --junitxml=.flowguard/cache/final-pytest.xml`：**1392 passed，340 subtests passed，31.59s**；外层墙钟 32.289s，输入运行前后摘要一致。
- 使用同次 JUnit/精确 nodeid/运行元数据，消费实际 `test_fingerprint_value_is_deterministic` 结果：源码审计通过、执行行 passed/current、对齐通过。边界仅该明确义务，未替其他组件或外部系统宣告运行。
- 最终 `python -m flowguard release`：strict check 0 error；lint error 0；**34 模型通过**，声明和执行集合相等；墙钟 **24.334s**。原版本同机基线约 17.85s；增加缓存输入检查与一个模型，仍在两倍以内。
- 最终 `python -m flowguard map lint --json`：**0 error / 56 warning / 72 info**；五项原有 accepted_debts 保留。告警不是本批全部要消除的 bug。
- `git diff --check`、主技能 quick_validate、技能包测试通过；主入口 84 行，model-test 协议 133 行。
- 复跑独立审计探针：默认三层影响/删除/模型回指修复；未知 ID、不支持模型路径、无入口语法错误、None conformance 非零；helper 变坏普通运行 FAIL。未声明的 lazy facade 原探针仍不自动连边，这是本批明确保留的解析边界；登记依赖的对应回归通过。

性能预热后各三次。无变更 change 使用包含本次工作树的 git index tree 作为 `--base`，因此只测空变更路径，未把本次大修的影响输出当作日常基线。原基线 read 0.175s、组件 read 0.125s、空 change 0.298s；当前中位数分别约 1.14、1.16、1.21 倍。未引入 daemon、分布式队列、read 时全模型检查或 runner 缓存。

## 保留限制和后续操作

1. 新项目先登记准确的文件、测试、模型和动态依赖。未声明且解析器不理解的实际调用仍可能漏关联；不要把地图完整度当作自动消灭全部 bug 的保证。
2. 需要实现执行结论的 model-test 计划使用 `bind_pytest_execution`，提供同次 exact nodeid、JUnit、命令/退出码以及代码/模型/测试输入摘要，并附源码审计。设计计划不冒充真实执行。
3. 配置、环境、外部系统或未知 helper 输入无法证明闭合时，安全重跑模型。当前只接 pytest，不扩展浏览器、数据库、Vitest/Jest。
4. 既有 runner 按其声明边界检查；本次只修正触及 runner 的误导说明，没有把全部专项 runner 改为真实系统回放。
5. 五项架构债务继续在后续触及 owner 时处理。没有实测缺陷或瓶颈，不追加治理平台、层层测试或全面拆模块。

本批验证支持上述明确修复边界，不表示已发现或消灭所有软件 bug。完整执行结果及元数据在可删除 cache 中，未提交生成证据或新增历史权威。
