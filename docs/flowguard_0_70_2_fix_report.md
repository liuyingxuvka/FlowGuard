# FlowGuard 0.70.2 修复与验收报告

本次按交接包的 A01–A37 修复，起点为 GitHub main 的 0.70.1（a7fb5f9）。交接包文件名写的是 0.71.0，但维护者明确要求只增加末位，因此发布版本为 **0.70.2**。没有恢复旧版的证据平台、结果缓存或大型流程系统。

## 现在能做什么

地图保留 37 个组件、4 条流程；默认 `read` 实测 7357 字符，完整显示组件和流程。代码变动可以定位直接负责者、调用者、有关测试和模型。地图声明的依赖要有真实 import、明确的模块字面量或精确说明的已接受债务支撑。产品调用图不会因为公共 lazy facade 而虚构全项目调用关系。

模型执行不再复用 PASS 缓存。契约模型必须真的使用 Explorer、探索非空边界、检查坏版本，并在规定的探索或一致性阶段执行 IMPLEMENTED_BY 所指代码。普通 owner runner 必须完成实际检查，不能仅靠返回 0 假通过。TESTED_BY 将规则连到存在的测试；真实 pytest 记录负责执行状态、输入范围和新鲜度，调用方不能自己填一个“已通过”来冒充证据。

日常 `change` 会显示有关架构问题；循环依赖是发布错误，近似重复、跨组件修改已声明状态是提示。说明不是执行证明，抽象自检会明确标注。`release` 的 PASS 只表示地图、架构错误和已登记模型通过，测试需要单独运行。

## 行动清单执行情况

“完成”表示实现及对应有限验收已完成，不表示静态分析可识别任意程序的所有缺陷。

| 项目 | 结果及关键实现位置 |
| --- | --- |
| A01 Windows / CI | 修正测试生成 CRLF 的方式；CI 覆盖 Ubuntu Python 3.11、3.13 和 Windows 3.12；升级 checkout/setup-python。 |
| A02 编码和路径 | common/inventory/impact/proof 处理 UTF-8、BOM、声明 GBK 的源码、中文 git 路径、绝对路径及解析缓存隔离；保留编码回归。 |
| A03 历史记录 | CHANGELOG 补 0.70.1，旧版使用真实提交引用；删除重复的旧修复报告。 |
| A04 PASS 缓存 | 删除模型 PASS 缓存和相关自检；每次重新执行；去掉模型缓存的 --force。 |
| A05 空跑拒绝 | proof/runner 验证真正 Explorer、非空探索、坏版本和 runner 完成计数；模板使用 run_owner。 |
| A06 代码与规则 | 规定阶段追踪实现函数调用；坏版本必须违反原规则，崩溃、预算耗尽、伪造同名规则不能算检出。 |
| A07 未登记模型 | 标准 owner 目录内的模型或 runner 未登记时明确报错。 |
| A08 负责代码选模型 | COMPONENTS、IMPLEMENTED_BY 和组件 models 双向检查；改实现文件可选中负责它的模型。 |
| A09 规则—测试连线 | 校验 TESTED_BY 的规则名、测试路径、函数及删除/改名情况；测试变动可反向选模型。 |
| A10 影响自检减负 | 删除 change_impact.py 自检模型，使用普通测试，避免为测试选择再执行整套测试。 |
| A11 test_ 产品文件 | 组件明确列出的源码优先于文件名启发式；自地图相应补齐。 |
| A12 import 选测试 | 反向遍历真实 imports，保留沿途 __init__、conftest 子树和测试 helper 的影响。 |
| A13 测试/模型改动 | 仅测试或模型改动缩到有关检查，不将其误扩散为产品依赖闭包。 |
| A14 公共入口与依赖 | lazy exports 指向真实负责模块；反射与星号导入保守处理；depends_on 无证据时报错。 |
| A15 配置/文档 | 源码字面量引用配置或文档时选相应测试；无检查时直说。 |
| A16 测试登记 | 纠正自地图误登记/漏登记，未登记可收集测试明确提示。 |
| A17 确认循环 | 忽略 status/fingerprint 对地图语义差异的影响；单纯 confirm 不再制造新的描述变更。 |
| A18 输出与语言 | change 去重、截断长列表并提示剩余量；test_commands 支持按语言/文件模式声明；共享一次解析上下文。 |
| A19 架构日常可见 | 同进程输出受影响组件 ARCH；循环附 import 行号；局部变量改名不逃过重复函数识别；直接修改别人的已声明状态提示。 |
| A20 危险入口 | 对声明入口的危险副作用反查模型；允许带原因的 NOT_MODELED，不伪称有限模型证明了文件系统/CLI 集成。 |
| A21 自动发现 | 支持 console_scripts、局部 imports、构造对象方法和回调；降低构造初始化、env.copy 等误报。 |
| A22 scan 限规模 | 默认最多 40 个组件，按完整子树合并并保持唯一归属；按 imports 猜测试；深度发现独立执行。 |
| A23 诊断 | digest 保留模块赋值和条件定义；模型依赖加载错误明确归环境/解释器；静态 flow_step_unreached 降为 INFO。 |
| A24 接入/升级 | 接入文档提供六条 AGENTS 规则；检测旧接口并给 0.69 升级指南；不自动覆盖现有 AGENTS。 |
| A25 地图预算 | 默认 8000 字符；先保留流程，再按完整组件截断，并列隐藏组件 ID。 |
| A26 首次接入 | 修正 first_map；新建尚未提交地图不会被误判 BLOCKED；cache 自带 gitignore。 |
| A27 承诺检查 | 对无关任务的承诺账本问题给提示，避免与已有模型检查互相阻断。 |
| A28 五个检测保护 | 在现有测试负责人内补五个真正缺陷检测回归；五个隔离突变分别被测试检出。 |
| A29 能力名 | 13 个能力名可直接作模板名；architecture-reduction 指向真实协议片段；拓扑坏样例正确退出非零。 |
| A30 拓扑与输出 | 不再将单个写者误判共享写者；实际多个写者保留检出；shard/预算输出进入 cache；删除无人消费的 result.json 写入。 |
| A31 模型拼接 | strict 模式确实约束父级和范围；旧路线指向现有能力，保留兼容常量。 |
| A32 模型—测试对照 | recorder v2 为运行事实唯一来源；支持无 JUnit 的真实记录；准确匹配函数、类、参数；raises/状态改变支持，空断言、mock、遮蔽不算实现证据；删除旧 runtime_test_evidence。 |
| A33 自检诚实 | runner 报告是否加载负责组件代码；清理旧 JSON、无效环境变量和重复脚本头；修正状态、副作用、依赖和组件绑定。 |
| A34 文档减负 | 合并 mesh 文档，删除旧完成计划和死资产；主 SKILL 85 行，升级指南 23 行；协议最多 130 行。 |
| A35 测试减负 | benchmark 语料一次计算；删除两项重复整模型子进程测试，保留敏感性检查；旧 receipt 决策分支不再测试。 |
| A36 打包安装 | wheel 仅包含 flowguard 和 dist-info；教学案例留仓库；安装路径变量校验及 Windows 路径回归。 |
| A37 发布 | pyproject、公开版本与 CHANGELOG 统一 0.70.2；README、报告与当前 32 个模型一致；只推 main。 |

## 实际验收

本地 Python 3.12：

- 最终外层 `python -m pytest -q -p flowguard.pytest_nodeid_recorder --junitxml=...`：**1490 passed，340 subtests passed，40.98 秒**。记录前后输入一致，有 1490 个实际 nodeid 及 JUnit 摘要。
- `python -m flowguard release`：**32 passed，0 failed；32 declared，32 executed；verify: PASS**。不嵌套 pytest，不读取旧 PASS 缓存。
- `python -m flowguard map lint`：**0 errors，56 warnings，57 info**。四项真实、注明原因的架构债务保留；未把 warning 全部压成假绿。
- 消费上述实际外层 pytest 记录：deterministic fingerprint 的单条代码/规则/测试关系 source audit 和 alignment 都通过。此结果只授权这一条关系，不授权“整个仓库业务都对齐”。
- import 标准答案：136 个测试文件各自真实执行，全部通过；125 个产品模块平均选择 **56.7** 个测试（审计基线 68.0）。漏选共 **25 个模块—测试对，全部来自同一个允许例外文件** test_python_function_state_verification_owner.py，它使用动态 spec_from_file_location；其他文件未漏。
- 架构缺陷复现 d1/d2/d3/d4 四种均有 ARCH 提示；d3 写依赖、confirm 后 release 仍退出 1。d6 的不同措辞语义重叠不保证识别，没有为它加入语言推断系统。
- `read`：7357 字符，37 个组件、4 条流程都可见；`change flowguard/core.py`：2978 字符。
- 清空旧 build 后构建 flowguard-0.70.2-py3-none-any.whl：只有 flowguard/ 和 dist-info/；技能安装及 --check 通过；git diff --check 通过。
- A01–A04 阶段已推 main，GitHub CI 三个平台组合均成功：run 38528738035。最终提交的 CI 结果见 GitHub Actions；本地验收不能替代用户电脑上的手动 Windows 中文环境运行。

按风险运行有限回归及两次整体验收；未逐项重复整套测试。A01–A04 分项提交；后续共享文件的修复按代码层、专项能力和发布文档分组提交。这与交接包“每项独立提交/阶段推送”的机械流程不同，所有项目的实现及最终集成状态一起验收。

## 保留边界与后续动作

1. **抽象自检不是业务执行证明。** 仍有 owner runner 只验证方案结构，输出明确标注 abstract boundary。需要真实业务保证时，给现有负责人加最短 conformance 轨迹；不要为了清掉提示再建一套证据平台。
2. **静态调用图有边界。** 动态 import、反射和运行时依赖注入可能需要明确测试连线；已知动态加载例外保留。先登记真实漏测，再决定是否扩展解析，避免为一个例外扩大所有改动的测试范围。
3. **有限模型只证明声明范围。** NOT_MODELED 的八个文件系统/CLI 集成入口有明确原因；这些由普通集成回归负责。新的高风险行为应接到既有模型，不必把每个函数都模型化。
4. **保持四项架构债务可见。** 不要仅为了 0 warning 重构；只有债务对应的真实变更任务出现时再消除。flow_step_unreached 是静态提示，不阻断发布。
5. **后续开发按六条接入规则执行。** 先读地图、找唯一负责者；改完运行 change；只跑其选出的检查；更新并 confirm 对应组件；发布时外层测试和 release 各运行一次。没有“测试套测试”的要求。

本次没有发布 tag/GitHub Release，也没有新建分支。缓存、运行证据、wheel 和临时夹具不提交；仅组件 confirm 所需 fingerprint 随地图提交。
