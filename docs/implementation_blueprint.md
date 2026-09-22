# Implementation Blueprint

FlowGuard's models explain intended behavior. The implementation blueprint
answers whether the model is connected to the code, resources, tests, and
oracles that make that behavior real. It is a derived, checkable view; it is
not a second model authority and it never copies production source text.

## Start from implementation, then bind both directions

The first input is an independent implementation inventory. Discovery covers
the declared software boundary and records production surfaces plus build,
runtime, dependency, configuration, schema, data, asset, migration,
external-service, and verification material. Every admitted item receives one
explicit disposition. A parse gap, unresolved dynamic effect, hidden writer,
or omitted required resource blocks static completion.

The binding review asks two questions:

1. Does every required model obligation have exactly one current primary
   implementation?
2. Does every behavior-bearing implementation surface lead to a model
   obligation, an owner contract, or an explicit non-behavior disposition?

The direct behavior implementation owns the exact `BehaviorBlockContract`.
Helpers, adapters, serializers, and storage bindings reference that same
obligation through typed supporting relations; they do not create duplicate
product behaviors or helper-local fallback obligations. Each block states its
input, state, output, effect, error, decision, order, retry, timeout, and
completion dimensions. A path or function name proves traceability only;
independent semantic references and applicable oracles are still required.

Every block has exact `BehaviorCaseContract` and `BehaviorCoverageEdge` rows
connecting implementation, model, source-independent rules, oracle, declared
good/boundary/protected-failure cases, checker design, and its current native
owner. `CoverageExecutionEvidence` remains separate. A full-suite receipt is
never copied across blocks, and every discovered test node receives a terminal
disposition.

`ModelTestAlignmentReport` is an independent artifact with its own fingerprint.
`BlueprintTopologyReport` records exact parent/child output-to-input relations;
parent completion requires the named child output to be consumed through the
named input mapping. Resource and intent inventories are joined by current
fingerprints; a failed intent discovery is never treated as an empty intent
set.

## Depth and affected-only reading

The static ladder is `inventory`, `traceability`, `independent_semantics`,
`model_code_test`, `resource_oracle`, and `static_blueprint`. The result reports
every layer, all gaps, the deepest proven layer, and the first incomplete layer.
`StaticBlueprintReadinessReport` can be `ready`, `incomplete`, `stale`, or
`blocked`. Test/checker execution is a separate receipt-backed status; a
static `not_run` design remains an execution gap and is never relabeled pass.

An explicit whole-target blueprint, self-qualification, or release request may
select the full boundary. Ordinary maintenance reads only the compact identity
and the affected owner neighborhood, then verifies the selected content-
addressed shards and relation objects. Unchanged siblings are reusable only
when their exact consumed fingerprints remain current. The affected reader
rejects an old full-payload shard instead of falling back to a whole report.

## Public lifecycle boundary

The public command surface is deliberately limited to `read`, `change`, and
`release`; blueprint depth is a subject of those operations, not an additional
CLI route. A request selects a subject and explicit scope:

```powershell
python -m flowguard read --root <project-root> --request read.json --json
python -m flowguard change --root <project-root> --request change.json --json
python -m flowguard release --root <project-root> --request release.json --json
```

`read` consumes only the selected current identity, index, and bounded shards;
it starts zero producers and writes nothing. `change` runs only affected
native owners and derived structure coverage. `release` verifies an accepted
current projection after source, toolchain, and impact identities are frozen.
Missing, stale, failed, skipped, not-run, or ambiguous evidence remains
visible and blocks the matching claim. The Python implementation exposes
internal typed blueprint helpers to the three operations; those helpers are
not alternate public entry points.

The installed skill is the clean consumer projection at
`$CODEX_HOME/skills/flowguard/SKILL.md`. The source checkout, package,
installed skill, local repository, Git tag, and GitHub release are separate
evidence domains. A GitHub publication happens only after `release` accepts the
current projection. The native model directory remains the exchangeable DNA;
the compact operation result is only its bounded read projection.

## Architecture reduction before release

The blueprint can reveal duplicate handlers, adapters, branches, fields, and
validation layers, but it never grants deletion permission by appearance. An
ordinary collapse needs current `safe_by_equivalence` evidence. A public facade
needs `safe_by_public_facade` evidence proving delegation to the selected owner
and primary path without independent business authority. Intentional behavior
retirement requires a complete disposition for every commitment, consumer,
interface, model, code path, test, negative case, skill, prompt, topology
relation, and release claim.

FlowGuard executes the candidate's exact covered test plus caller/consumer,
state, side-effect, and error parity checks under bounded process supervision.
Only current child receipts are composed into one child-bound aggregate. An
unrelated, stale, failed, unclean, incomplete, or relabeled receipt cannot
close a contraction. A clean review may therefore finish with every candidate
retained for a distinct responsibility and zero safe deletions.

## Recorded contraction and token evidence

The v0.68.7 historical cleanup retained immutable history, archived OpenSpec
changes, old snapshots, receipts, and adoption logs as evidence rather than
current runtime. It reduced independent owners and routes while adding the
source, topology, intent, binding, and authority detail needed for trustworthy
claims. A recorded compact projection reduced one read-only report from
364,497 characters to 2,604 while preserving base, candidate, affected-closure,
diff, and observed-head identities. That receipt is evidence for that bounded
projection, not a universal token guarantee.

## 中文说明

实现蓝图检查模型是否真的连接到代码、资源、测试和判断依据。每个行为块只
有一个主要负责人，helper、适配器、序列化和存储代码只通过支持关系连接到同
一个义务；不能因为路径相似就制造第二个功能或 fallback。蓝图同时保留静态
设计状态和真实执行状态，`not_run` 只表示尚未执行，不能被说成通过。

普通修改只读取受影响的负责人邻域和内容寻址分片；只有明确请求完整蓝图、自
我资格或发布闭合时才检查完整边界。公开入口只有 `read`、`change`、`release`，
蓝图深度是这些操作内部的主题，不再暴露旧的独立命令。发布前的结构收缩仍
需要当前等价性或公共门面证据；“看起来重复”不能替代证据。
