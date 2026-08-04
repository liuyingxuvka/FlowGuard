# Implementation Blueprint

FlowGuard's models can explain what software is supposed to do. An
implementation blueprint answers a different question: have those models been
connected to everything that actually makes the software work?

The blueprint is a derived, checkable view. It does not become a second
model-system authority and it does not copy production source text.

## Start From The Implementation, Not From A Self-Written List

The first input is an independent implementation inventory. Discovery examines
the declared software boundary and records production surfaces plus the build,
runtime, dependency, configuration, schema, data, asset, migration,
external-service, and verification material needed to reproduce behavior.

Every admitted item needs one explicit disposition. A file that could not be
parsed, a dynamic operation that cannot be resolved, a hidden state or effect
writer, or a required resource that was silently omitted blocks static
completion. A model or caller cannot declare the inventory complete merely by
listing the code it already knows about.

## Bind The Model And The Code In Both Directions

The binding review asks both questions:

1. Does every required model obligation have exactly one current primary
   implementation?
2. Does every behavior-bearing implementation surface lead to a model
   obligation, an owner contract, or an explicit non-behavior disposition?

Two primary implementations for the same obligation are not extra confidence;
they are conflicting ownership. An internal helper does not need to become a
public contract, but it must have a unique supporting path to its owner. An
unbound public entrypoint or hidden writer blocks the blueprint.

A path and function name provide traceability only. Static blueprint closure
also needs source-independent semantic references and applicable oracles. Together
they cover inputs, outputs, state and effects, errors, and any relevant order,
retry, timeout, or decision rules. Resource references identify the non-code
material needed to build and run the bounded software without embedding
passwords, tokens, private keys, or production source text.

The canonical unit is a `BehaviorBlockContract`, not a file, class, role, or
large feature label. Every behavior-bearing surface has exactly one primary
block owner and explicitly states input, state, output, effect, error,
decision, order, retry, timeout, and completion. Helpers, adapters,
serializers, and persistence code attach through typed supporting relations;
they are not promoted into duplicate product behaviors merely because they
contain code.

Every block has exact `BehaviorCaseContract` and `BehaviorCoverageEdge` rows
connecting implementation surfaces, source-independent rules, portable model,
oracle, owner-declared good/boundary/bad cases, one accepted checker design per
dimension, and its current pytest or native-check owner.
`CoverageExecutionEvidence` is separate. Placeholder cases and generated case
or checker ids cannot close static readiness, and one full-suite receipt cannot be copied
across all blocks. Delegated assertion helpers need a current acyclic call graph
ending at real assertion/native members. Every discovered test node also
receives a terminal disposition so an orphan test cannot disappear from the
denominator.

`ModelTestAlignmentReport` is a separate real artifact: its own fingerprint
commits to model obligations, owner code contracts, exact checker designs,
execution state, and every open gap. A binding-report fingerprint cannot stand
in for it. `BlueprintTopologyReport` then records exact parent/child
output-to-input relations, so a parent is complete only when the child's named
output is consumed through a named input mapping.

The blueprint joins one current resource inventory and one current intent
inventory. A resource category row does not copy a reduced resource record: it
points to the canonical `BlueprintResourceReference`, which preserves the exact
owner, artifact, content fingerprint, source-independent semantics, purpose,
and lifecycle role. The category adds only an independently fingerprinted
`current`, `external`, `scoped_out`, or `blocked` disposition. A blocked
category has no resource reference and therefore cannot manufacture a missing
blueprint input. An empty intent inventory is accepted only with an evidence-bound
no-intent rationale; failed discovery is not silently treated as “there was no
intent.”

## A Depth Ladder, Not One Self-Rated Green Light

The static result is split into an ordered ladder. `inventory` proves the
bounded denominator; `traceability` joins stable model obligations to code;
`independent_semantics` rejects semantics copied or inferred only from that
same code; `model_code_test` binds exact tests or native oracle checks;
`resource_oracle` closes build/runtime/data/configuration resources and
decision criteria; `static_blueprint` is the join of those five layers.

The report exposes every layer, its gaps, and `deepest_proven_layer`. An AI can
therefore say exactly how deeply it understands the software instead of
deciding for itself that it understands "enough". That depth is still separate
from the user's choice to write code and from DevelopmentProcessFlow's
implementation admission.

After those layers close, `StaticBlueprintReadinessReport` returns `ready`,
`incomplete`, `stale`, or `blocked`, every known gap, the deepest complete
layer, and the first incomplete layer. `ready` means the declared finite
current blueprint has closed its static evidence obligations. Test/checker
execution remains a separate receipt-backed status.

## Ordinary Tasks Stay Affected-Only

An explicit whole-target blueprint, export, self-qualification, or release
requirement can request the full boundary. Ordinary maintenance does
not. It loads the compact blueprint identity and the smallest affected owner
neighborhood, then revalidates only the referenced shared objects, topology
relations, and content-addressed shards touched by the change.

That means adding this capability does not make every bug fix scan the whole
repository or export every shard. Unchanged
sibling shards may be reused only when their exact content and consumed owner
fingerprints remain current.

The normalized projection stores shared owners, contracts, semantics, oracles,
tests, resources, and intent once. Its logical fingerprint does not change
merely because shard sizes or layout change. An ordinary task loads one exact
`AffectedBlueprintNeighborhood` and verifies every referenced shared object
before use, which keeps token use proportional to the change.

## Provider-Neutral Command-Line Entries

Audit any declared target system in memory through exact observation and
authority providers. Python AST and pytest are two software-provider examples;
JavaScript, workflow, trace, contract, or mixed providers use the same core.
The strict definition names the target kind and boundary, stable model owners, independent semantic provenance,
implementation surfaces, an embedded `ProjectTestInventory`, exact test
evidence, resources, and current fingerprints. On every audit, FlowGuard
re-discovers the current test sources and assertion-bearing nodes and compares
them with that embedded inventory; a test fingerprint copied only from the
blueprint cannot certify itself. A model that owns a native checker instead of
a pytest node must declare its bounded checker path; FlowGuard re-hashes that
actual checker file before accepting its evidence identity:

```powershell
python -m flowguard project-blueprint-audit `
  --root <project-root> `
  --definition <project-blueprint.json> `
  --json
```

A missing required provider capability blocks that exact boundary; the core
does not reject a target merely because it is not Python. The command does not
write the target, start a validator, or activate a model revision.

Audit FlowGuard's own checked-in self-blueprint without writing any projection.
When release cleanup needs both static DNA and
architecture-reduction results, use the composed option so the exact in-memory
blueprint is built once and shared by both bounded reviews:

Compact output projects its bounded status fields directly and does not first
serialize the complete code-model-test graph.
The immutable behavior report computes its canonical fingerprint once per
in-memory object and shares that exact value across qualification and reduction.
Normalized large payloads feed exact canonical JSON chunks into one digest and
byte counter; they do not retain several complete serialized copies, and the
logical payload is released before the physical projection is constructed.

```powershell
python -m flowguard flowguard-self-blueprint-check `
  --root . `
  --include-architecture-reduction `
  --compact `
  --json
```

Find unresolved behavior candidates from an independently discovered provider
inventory without writing a project definition or claiming that inferred
semantics are complete:

```powershell
python -m flowguard project-blueprint-candidate `
  --inventory implementation-inventory.json `
  --root . `
  --json
```

Review FlowGuard's own current blueprint for large or repeated structural
shapes. Every result is read-only; size/similarity candidates remain
`risky_keep` until separate equivalence and StructureMesh evidence exists.
This standalone form is useful when the blueprint result is not otherwise
needed; the release-facing composed form above avoids a second blueprint build.
Caller relations are resolved from one deterministic reverse call index rather
than rescanning every surface for every candidate:

```powershell
python -m flowguard flowguard-self-architecture-reduction-review `
  --root . `
  --compact `
  --json
```

Audit an inventory without changing it:

```powershell
python -m flowguard implementation-inventory-audit `
  --inventory implementation-inventory.json `
  --root . `
  --json
```

Check static artifact status from existing artifacts without writing or
running missing owners:

```powershell
python -m flowguard model-blueprint-check `
  --inventory implementation-inventory.json `
  --manifest software-blueprint.json `
  --binding-report model-implementation-bindings.json `
  --observed-snapshot-fingerprint <current-snapshot-fingerprint> `
  --semantic-mesh-fingerprint <current-mesh-fingerprint> `
  --test-inventory-fingerprint <current-test-inventory-fingerprint> `
  --model-test-alignment-report-fingerprint <current-alignment-fingerprint> `
  --portable-owner-fingerprints '{"portable:system":"<current-portable-fingerprint>"}' `
  --resource-fingerprints '{"resource:runtime":"<current-resource-fingerprint>"}' `
  --oracle-fingerprints '{"oracle:behavior":"<current-oracle-fingerprint>"}' `
  --json
```

Write one deterministic projection to an explicitly selected directory:

```powershell
python -m flowguard model-blueprint-export `
  --inventory implementation-inventory.json `
  --manifest software-blueprint.json `
  --binding-report model-implementation-bindings.json `
  --observed-snapshot-fingerprint <current-snapshot-fingerprint> `
  --semantic-mesh-fingerprint <current-mesh-fingerprint> `
  --test-inventory-fingerprint <current-test-inventory-fingerprint> `
  --model-test-alignment-report-fingerprint <current-alignment-fingerprint> `
  --portable-owner-fingerprints '{"portable:system":"<current-portable-fingerprint>"}' `
  --resource-fingerprints '{"resource:runtime":"<current-resource-fingerprint>"}' `
  --oracle-fingerprints '{"oracle:behavior":"<current-oracle-fingerprint>"}' `
  --output exported-blueprint `
  --json
```

The project, self, candidate, reduction, inventory, and artifact check commands
are read-only. Export writes only beneath the
explicit output directory and verifies its canonical manifest and
content-addressed JSON shards. None of these commands starts a builder,
missing validation owner, or model-authority update.

## Architecture Reduction Before Release

Once the blueprint closes, it can reveal duplicate handlers, adapters,
branches, state fields, and validation layers. This is a review queue, not
permission to delete them.

Before release, FlowGuard may use the current model and implementation bindings
to propose a smaller architecture. A removal or collapse is eligible only with
current `safe_by_equivalence` evidence that the observable contract is
preserved. A public entrypoint may remain as a thin facade only with current
`safe_by_public_facade` evidence showing that it delegates to the selected
owner contract and primary path and has no independent business authority.
Property-only evidence, stale delegation evidence, a required conformance
replay, or missing proof keeps the candidate blocked or retained.

Architecture reduction therefore follows the model; it never makes the model
look complete by deleting an unexplained behavior.

FlowGuard's self-audit independently derives the complete candidate denominator
from the exact current self blueprint. Large modules and repeated shapes are
reported as `risky_keep`, not automatic cleanup. A clean review may therefore
finish with candidates visible and zero safe deletions.

## 中文说明

实现蓝图解决的是一个很具体的问题：FlowGuard 不只要知道“软件应该怎么运
行”，还要确认这些模型是否真的连接到了让软件运行起来的全部代码和资源。

它先从独立实现清单出发，而不是相信模型自己列出的代码名单。每个有行为的
入口、状态写入和外部影响，都要反向找到模型义务或明确的负责人；每个模型
义务也要正向找到唯一的主要实现。只有文件路径和函数名还不够，还必须有不
依赖源码原文的语义说明、可判断对错的 oracle，以及构建、运行、配置、数据、
迁移和外部服务等资源引用。

蓝图的基本单位不是一个文件、一个角色或者一句“大功能”，而是一个行为块。
每个行为块只有一个主要负责人，并且要明确写出输入、状态、输出、副作用、
错误、判断、顺序、重试、超时和完成条件。helper、适配器、序列化和存储代码
只作为支持关系连接到主要行为，不能被重复算成另一个产品功能。

每个行为块都要精确连到代码、独立语义、判断依据、测试设计、具体测试节点和
当前执行证据。整套测试通过不能平均贴到所有行为块上。意图清单为空时，也只
能在存在证据绑定的“确实没有声明意图”说明时闭合；搜索失败不能冒充没有意图。

蓝图会分层说明自己理解到了哪里：代码与资源清单、模型和代码的双向绑定、
独立设计语义、模型—代码—测试绑定、资源和判断依据，最后才是静态蓝图整体。
AI 必须报告最深已证明层和缺口，不能自己给自己打一个笼统的“理解充分”。
在这些层闭合后，静态蓝图准备度会给出 `ready`、`incomplete`、`stale` 或
`blocked`，列出全部缺口、最深完成层和第一个未完成层。测试设计是否齐全与
本次测试是否真正执行并通过是两个独立结果，不能互相冒充。

普通修改仍然只看受影响范围：加载紧凑的蓝图身份、找到受影响的负责人邻域，
只更新失效的内容寻址分片。共享的负责人、契约、语义、oracle、测试、资源和
意图只保存一次，调整分片大小不会改变逻辑身份，所以 token 消耗跟当前改动
范围走。只有明确要求整套蓝图、导出、自我资格或发布闭合时，才检查完整边界。

发布前可以让模型帮助寻找重复结构，但这不是随意删代码。只有具备当前等价性
证据的候选才可以删除或合并；公开入口如果必须保留为委托门面，还要有当前证
据证明它只转交给唯一的负责人和主路径，没有自己的业务权威。缺少证据、证据
过期或只证明少数属性时，都必须保留或继续验证。

FlowGuard 自己的清理审计也遵守同样规则：它从当前自我蓝图独立列出全部候选，
体积大或形状相似默认只是 `risky_keep`。即使有候选，只要没有等价性证据，
“零个可以安全删除”也是一个正常、诚实的审计结果。
