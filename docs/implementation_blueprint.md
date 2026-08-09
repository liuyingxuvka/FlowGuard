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

The direct behavior implementation binding owns the exact behavior-block
obligation. A helper, adapter, serializer, or storage binding references that
same obligation and the direct owner's required semantic dimensions, but does
not enter the primary-obligation denominator as another owner. A missing,
ambiguous, or mismatched direct owner is a real gap; FlowGuard does not invent a
helper-local fallback obligation.

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
connecting its own implementation surface and block-local portable
input/output/state mapping to source-independent rules, the shared parent
model, oracle, owner-declared good/boundary/protected-failure cases, one
accepted checker design per dimension, and its current pytest or native-check
owner. Several blocks may share one model-level source-case origin, but each
materialized checker uses its own block-local case identity; a primary block's
fields or cases cannot stand in for a sibling.
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
tests, resources, and intent once. Native readiness keeps typed coverage rows
so it remains a self-contained review, but the normalized and canonical
physical form gives every complete coverage row one owner:
`shared_objects[coverage_id]`. The normalized behavior view carries the report
identity and exact coverage fingerprints; each coverage shard is a strict
current-schema envelope containing only ordered object references. The affected
reader rejects an old full-payload shard instead of guessing or falling back to
the whole report. Its logical fingerprint does not change merely because shard
sizes or layout change. An ordinary task loads one exact
`AffectedBlueprintNeighborhood` and verifies every referenced shared object
before use, which keeps token use proportional to the change.
The affected index fingerprints every base object independently, then builds the
validated object-id denominator once for all affected and topology edges. It
does not recreate that complete denominator per edge, but every reference still
fails closed when its object is missing.

## Provider-Neutral Command-Line Entries

The primary whole-target route accepts three independently prepared, strict
current artifacts: the target descriptor, frozen provider evidence, and the
native report set. FlowGuard derives every readiness row and gap; callers do
not submit their own pass rows. Python AST and pytest are only possible
providers. TypeScript, another software language, a workflow engine, traces,
contracts, or a mixed target use the same target-neutral entry:

The project preset also derives one internal
`BlueprintManifestQualificationReport` while checking manifest identity,
inventory, bindings, independent semantic and oracle references, resources,
tests, and current fingerprints. It is deliberately not a public constructor
and exposes `static_manifest_status`, `static_manifest_ready`, and an exact
claim boundary rather than a generic `ok` or completion sentence. This child
result is one input to project/static/target readiness; it cannot represent
whole-target understanding, implementation admission, execution, or release
readiness by itself.

```powershell
python -m flowguard target-system-blueprint-audit `
  --descriptor target-system.json `
  --frozen-evidence frozen-provider-evidence.json `
  --native-report-set native-report-set.json `
  --json
```

When the same audited target must be saved or exchanged, use the single
provider-neutral export entry with the same three strict inputs:

```powershell
python -m flowguard target-system-blueprint-export `
  --descriptor target-system.json `
  --frozen-evidence frozen-provider-evidence.json `
  --native-report-set native-report-set.json `
  --output exported-target-blueprint `
  --json
```

Export invokes the same native qualifier used by audit, then mechanically
projects that exact descriptor, frozen provider evidence and layer plan,
complete native report set (including portable models, typed members,
implementation or external owners, tests, resources, intent, topology, and
typed receipts), and qualification/readiness result. It uses the existing
`CanonicalBlueprintProjection` manifest, `BlueprintShard` content addressing,
writer, and verifier. The Python-project convenience export below uses that
same envelope and materialization kernel; it is not a second authority or a
compatibility format.

`load_canonical_blueprint_projection` is the one strict current-schema disk
loader. It rejects extra files, extra or missing directories, reparse points,
non-current manifest/shard shapes, and content-address mismatches. Its generic
claim stops there: it does not prove that identity or readiness is a function
of the intended target. `target-system-blueprint-export` therefore performs a
second, target-owned rebind against the exact descriptor, frozen evidence,
native report set, and compiler qualification after writing. A manifest and
identity shard that were rewritten and rehashed consistently pass the generic
content check but fail this target rebind.

The writer snapshots the complete owned tree, validates the staged tree, and
revalidates both immediately before activation. If directory activation fails
after the old tree was moved aside, the prior tree is restored even when
another process recreated the output path. Cleanup of an obsolete backup is
best-effort after commitment and cannot make an already activated projection
look uncommitted.

This command always qualifies the whole declared target. It has no affected
scope switch. Local maintenance uses `affected-blueprint-understanding` below,
whose content-addressed reader owns the smaller affected neighborhood.

A native test row may remain a static `not_run` design without inventing a
receipt. A `passed` row is accepted only when the report set carries the exact
leaf `ValidationOwnerContract`, immutable `EvidenceReceipt`, and independently
derived `ReceiptVerificationResult`. FlowGuard checks their owner, revision-
bound member obligation, command, input, toolchain, environment, terminal
result, currentness, eligibility, and content fingerprints; parent, relabeled,
cross-owner, incomplete, or reused receipts are rejected.

The compact self-qualification view therefore reports two bounded groups:
static blockers and execution gaps. A planned leaf whose checker design is
complete but whose execution is `not_run` remains visible as an execution gap;
it is neither misreported as a broken DNA binding nor implied to have passed.
Missing owners, obligations, dimensions, oracles, or checker designs remain
static blockers.

Ordinary maintenance starts from an already qualified, content-addressed
index. It reads only the named change seeds, their propagated parent/child,
producer-consumer, delegation, support, or sibling impact, the exact relation
objects that caused propagation, referenced objects, and the common readiness
ledger. Cycles and duplicate declarations converge to the same deterministic
closure:

```powershell
python -m flowguard affected-blueprint-understanding `
  --index affected-blueprint-index.json `
  --shard-store blueprint-shards.json `
  --object-store blueprint-objects.json `
  --affected-id <changed-model-or-surface-id> `
  --json
```

`project-blueprint-audit` remains the language-specific convenience route for
a declared project definition whose concrete discovery and test adapters are
already registered. Its definition names the target kind and boundary, stable
model owners, independent semantic provenance, implementation surfaces, an
embedded `ProjectTestInventory`, exact test evidence, resources, intent, and
current fingerprints. On every audit, FlowGuard re-discovers the current test
sources and assertion-bearing nodes and compares them with that embedded
inventory; a test fingerprint copied only from the blueprint cannot certify
itself. A model that owns a native checker instead of a pytest node must declare
its bounded checker path; FlowGuard re-hashes that actual checker file before
accepting its evidence identity. Qualification also rederives every canonical
provider result from the current preparation and compares the complete input,
payload, capability, status, finding, kind, version, and registry identity
against the frozen evidence. Re-freezing a changed payload around itself does
not make it current. The manifest's semantic-mesh fingerprint is derived from
the reviewed topology report, and child runtime evidence must exist in the
current owner-bound evidence registry:

```powershell
python -m flowguard project-blueprint-audit `
  --root <project-root> `
  --definition <project-blueprint.json> `
  --json
```

For exchange between tools or projects, wrap the same canonical projection in
one portable file. This is a transport envelope, not a second model: its
manifest and shards are the exact current content-addressed projection above.
The envelope records three separate facts so a compact read cannot accidentally
turn “saved” into “understood” or “executed”: static model status, portable
integrity status, and execution-evidence status. It does not invoke providers,
source, tests, or reconstruction. The file can be checked in an isolated
directory with no project source available:

```powershell
python -m flowguard project-blueprint-portable-export `
  --root <project-root> `
  --definition <project-blueprint.json> `
  --output portable-blueprint.json `
  --compact `
  --json

python -m flowguard portable-blueprint-verify `
  --bundle portable-blueprint.json `
  --json
```

`--compact` changes only the printed report. The file remains complete, with
all twenty project projection kinds, member identities, fingerprints, and
readiness gaps. A consumer that needs details can load the same file; it never
falls back to source, Python, an alternate provider, or a missing shard.

A missing required provider capability blocks that exact boundary; the core
does not reject a target merely because it is not Python. These audit/read
commands do not write the target, start a validator, or activate a model
revision.

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

The checked-in self-blueprint definition keeps authored behavior semantics
separate from mechanical source identities. Check those identities without
writing by default; only an explicit author-maintenance step may refresh them:

```powershell
python scripts/compile_flowguard_self_blueprint_definition.py
python scripts/compile_flowguard_self_blueprint_definition.py --write
```

The compiler requires exactly one current composite contract for each manifest
owner and changes only its model, runner, purpose-declaration, and
purpose-closure source identities. Missing, foreign, duplicate, stale, linked,
or concurrently changed owners block; it never invents behavior semantics or a
fallback owner.

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

Candidates that share the same tests and coverage rows reference one
content-addressed evidence neighborhood. The review stores that full
neighborhood once, while each candidate binds its own callers, behavior, state,
effects, and errors to the exact neighborhood fingerprint. Missing, stale, or
inline fallback evidence is rejected; proof receipts continue to carry the
complete resolved evidence.

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

When a caller explicitly needs a portable checkpoint of the model, write the
same canonical project bundle to an explicitly selected directory:

```powershell
python -m flowguard project-blueprint-export `
  --root <project-root> `
  --definition <project-blueprint.json> `
  --output exported-blueprint `
  --json
```

For a bounded status check without the full graph, use the compact audit view:

```powershell
python -m flowguard project-blueprint-audit `
  --root <project-root> `
  --definition <project-blueprint.json> `
  --compact `
  --json
```

The project, self, candidate, reduction, and inventory audit commands are
read-only. Project export consumes that same canonically assembled project
bundle and reuses the provider-neutral export's existing projection envelope,
writer, and verifier. It writes only beneath the explicit output directory and
verifies its manifest and content-addressed JSON shards. Its twenty
project-specialized projection kinds preserve the project identity and
definition, frozen provider evidence, independent
implementation inventory and audit, model/code bindings, semantics, oracles,
behavior model and cases, topology, model/test alignment, test inventory,
resources, intent lineage, normalized and affected indexes, shared objects,
and every readiness/depth/gap result. A raw manifest plus caller-repeated labels
is not another qualification path. None of these commands starts a missing
validation owner or model-authority update.

Export completion means only that this exact snapshot was materialized and
verified. The provider-neutral and Python-project convenience exports can both
materialize a growing blueprint while it still reports `incomplete`, `stale`,
`blocked`, or `not_run`; those statuses travel inside the readiness shard and
remain distinct from model completeness. Both commands report
`materialization_ok` / `materialization_status` for the write-and-verify action
and `model_readiness_status` for the blueprint itself; neither reuses a generic
`ok` field that could be mistaken for model readiness.

## Architecture Reduction Before Release

Once the blueprint closes, it can reveal duplicate handlers, adapters,
branches, state fields, and validation layers. This is a review queue, not
permission to delete them.

Before release, FlowGuard may use the current model and implementation bindings
to propose a smaller architecture. It first asks whether each surface is still
necessary to the current DNA. An ordinary removal or collapse needs current
`safe_by_equivalence` evidence that its observable contract is preserved. A
public entrypoint may remain as a thin facade only with current
`safe_by_public_facade` evidence showing that it delegates to the selected
owner contract and primary path and has no independent business authority. A
behavior that the current product goal intentionally no longer needs may be
removed only through `retire_behavior` with a complete disposition of every
commitment, consumer, interface, model, code path, test, negative case, skill,
prompt, topology relation, and release claim. Property-only evidence, stale
delegation evidence, or an incomplete retirement inventory keeps the candidate
unresolved; historical age and apparent duplication are not proof.

A contraction proof is not a caller-written `pass`. FlowGuard executes the
candidate's exact covered test and its caller/consumer, state, side-effect, and
error parity check under bounded process-tree supervision. Only exact-current
passing child receipts are composed into one child-bound aggregate in the
repository's canonical validation-owner store. The review reloads the aggregate
and children, rebuilds their current owner contexts, and rechecks governed
inputs immediately before publishing its result. An unrelated test, alternate
receipt root, missing parity dimension, failed or unclean command, stale child,
or relabeled receipt cannot make a contraction ready.

Architecture reduction therefore follows the model; it never makes the model
look complete by deleting an unexplained behavior.

FlowGuard's self-audit independently derives the complete reduction universe
and a separate candidate inventory from the exact current self blueprint. An
owned singleton signal may close as typed retain. A signal that forms a real
candidate can close only through candidate-bound distinct-commitment retain
evidence or verified contraction proof; otherwise it remains visible and blocks
release cleanup readiness. A clean review may finish with candidates recorded,
all of them honestly retained for distinct responsibilities, and zero safe
deletions.

## Measured v0.68.7 Contraction

The v0.68.7 cleanup was measured against commit
`fa8a9a4d9280cea6128e9d23517fe67533424e5e`. Immutable history, archived
OpenSpec changes, old model snapshots, receipts, and adoption logs were kept as
evidence and were not counted as current runtime. The current runtime package
plus executable self-model surface changed from 303 to 283 files (-20, or
6.600660%), and the current model-owner manifest changed from 65 to 51 owners
(-14, or 21.538462%). The fourteen retired owners are
`legacy_compatibility_cleanup`, `maintenance_scan_router`,
`model_angle_deliberation`, `model_similarity_consolidation`, and
`template_harvest_closure`, plus `openspec_archive_cleanup`,
`readme_positioning_20260602`, `release_visibility_process`, and
`risk_purpose_header`, plus `ai_surface_streamlining`,
`reduce_architecture_surface`, `simplify_flowguard_structure`,
`structure_surface_simplification`, and `simplify_field_schema`.

This is not a claim that the whole implementation became smaller. Completing
the DNA, topology, intent, binding, affected-scope, and authority paths added
necessary mainline detail: Python lexical tokens in the runtime package plus
current executable self-models rose from 867,087 to 1,055,846 (+188,759, or
21.769326%). The
contraction is structural: fewer independent owners and paths, with the
remaining protection moved into their direct current owners. The clearest
local example is the former 2,468-line standalone similarity engine: its
current `CanonicalRelation` handoff is 256 lines and uses 1,174 rather than
16,359 Python lexical tokens (-92.823522%).

Daily AI use is reduced independently from model depth. On one recorded
pre-finalization read-only `ModelRevisionPlan` report, the full representation was 364,497
characters and the compact projection was 2,604 characters. The compact view
kept the same base, candidate, affected-closure, diff, and observed-head
identities while reducing rendered text by 99.285591% (139.975806 times
smaller); it performed no writes and executed no models. This proves compact
projection of that report, not universal token usage for every tool or model.

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
只作为支持关系连接到主要行为，引用同一个行为义务和同一组语义要求，但不进入
主要义务统计成为第二个负责人；负责人缺失、歧义或要求不一致时必须明确报错，
不能被重复算成另一个产品功能，也不能临时造一个 helper 自己的替代义务。

每个行为块都要精确连到代码、独立语义、判断依据、测试设计、具体测试节点和
当前执行证据。整套测试通过不能平均贴到所有行为块上。意图清单为空时，也只
能在存在证据绑定的“确实没有声明意图”说明时闭合；搜索失败不能冒充没有意图。

蓝图会分层说明自己理解到了哪里：代码与资源清单、模型和代码的双向绑定、
独立设计语义、模型—代码—测试绑定、资源和判断依据，最后才是静态蓝图整体。
AI 必须报告最深已证明层和缺口，不能自己给自己打一个笼统的“理解充分”。
在这些层闭合后，静态蓝图准备度会给出 `ready`、`incomplete`、`stale` 或
`blocked`，列出全部缺口、最深完成层和第一个未完成层。测试设计是否齐全与
本次测试是否真正执行并通过是两个独立结果，不能互相冒充。
紧凑报告也会把静态结构缺口和执行缺口分开：设计完整但尚未运行的叶子测试仍会
显示为 `not_run` 执行缺口，却不会被误算成 DNA 绑定损坏，更不会被说成已经通过。

普通修改仍然只看受影响范围：加载紧凑的蓝图身份、找到受影响的负责人邻域，
只更新失效的内容寻址分片。共享的负责人、契约、语义、oracle、测试、资源和
意图只保存一次，调整分片大小不会改变逻辑身份，所以 token 消耗跟当前改动
范围走。只有明确要求整套蓝图、导出、自我资格或发布闭合时，才检查完整边界。

显式导出会把同一份规范蓝图的全部层做成内容寻址文件，包括目标定义、provider
证据、行为和父子接口、代码绑定、测试绑定、资源、意图、受影响索引以及完整的
准备度和缺口。导出成功只说明这份模型快照已经被完整写出并校验，不会把模型里
仍存在的 `incomplete`、`stale`、`blocked` 或 `not_run` 自动说成“理解完整”。

发布前可以让模型帮助寻找重复结构和历史功能，但这不是随意删代码。它先判断
每个表面对当前软件 DNA 是否仍有必要。普通删除或合并仍然需要当前等价性证据；
公开入口如果必须保留为委托门面，还要证明它只转交给唯一负责人和主路径，没
有自己的业务权威。如果当前产品目标明确不再需要某个历史行为，也可以走
`retire_behavior`，但必须逐项说明它的承诺、使用者、接口、模型、代码、测试、
反例、技能、提示词、拓扑关系和发布声明是删除、转移还是仅留在历史里。缺少普
通等价性证据或完整退役证据时，它仍是未解决问题，不能用“看起来没用”冒充清
理完成。

FlowGuard 自己的清理审计也遵守同样规则：它从当前自我蓝图独立列出完整清理
分母，再另外生成候选。所谓“可以安全收缩”的证明必须真的运行候选绑定测试和
调用者、状态、副作用、错误四类一致性检查，再把这些子结果组成一份当前证明；
自己写一个通过记录、拿无关测试来凑数或换一个临时证据目录都不算。最终即使
没有任何可以安全删除的候选，只要所有表面都已有明确职责或有诚实的未解决记
录，报告仍能准确说明软件现在为什么保留这些结构；发布门只接受前者全部闭合。

这次 v0.68.7 的实测结果也要分开理解。当前运行包和可执行自模型合计少了 20 个
文件，模型负责人从 65 个降到 51 个；旧的独立相似性引擎被精确关系交接替代，
这一个局部的代码 token 减少了约 92.82%。但是为了补齐 DNA、拓扑、意图、代码
和测试绑定以及权威证据，运行主干和当前自模型的代码 token 总量增加了约
20.39%。所以这次清理的真实结果是“重复路线变少、主干理解变完整”，不是整库
代码盲目变少。日常 AI 使用通过紧凑投影单独解决：一份明确记录为发布前样本的
同源只读报告从 364,497 个字符缩到 2,604 个字符，减少约 99.29%，而且模型身份
和受影响范围保持一致。
