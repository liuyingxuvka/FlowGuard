# Implementation Blueprint

FlowGuard's models can explain what software is supposed to do. An
implementation blueprint answers a different question: have those models been
connected to everything that actually makes the software work?

The blueprint is a derived, checkable package. It does not become a second
model-system authority, it does not copy production source text, and it does
not rebuild the software automatically.

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

A path and function name provide traceability only. Reconstruction closure also
needs source-independent semantic references and applicable oracles. Together
they cover inputs, outputs, state and effects, errors, and any relevant order,
retry, timeout, or decision rules. Resource references identify the non-code
material needed to build and run the bounded software without embedding
passwords, tokens, private keys, or production source text.

## Two Results, Not One Green Light

Static blueprint qualification and empirical reconstruction are deliberately
separate:

| Result | Possible states | Meaning |
| --- | --- | --- |
| Static blueprint | `complete`, `incomplete`, `stale`, `blocked` | whether the current inventory, bindings, semantics, resources, oracles, and owner fingerprints close |
| Empirical reconstruction | `not_run`, `pass`, `fail`, `blocked` | whether an explicitly requested isolated reconstruction produced current evidence |

`static_status=complete` together with `empirical_status=not_run` is a valid
static result. Its claim is exactly: **blueprint complete; reconstruction not
verified**. It must never be shortened to “the software was reconstructed” or
“clean-room reconstruction passed.”

Supplying `--require-reconstruction` only requires a matching receipt. It never
launches reconstruction. A usable receipt binds the exact blueprint
fingerprint, isolated environment, source-access policy, covered oracle set,
and evidence fingerprint.

## Ordinary Tasks Stay Affected-Only

An explicit whole-software blueprint, export, reconstruction qualification, or
release requirement can request the full boundary. Ordinary maintenance does
not. It loads the compact blueprint identity and the smallest affected owner
neighborhood, then revalidates only the content-addressed shards touched by the
change and any owners connected through their bindings.

That means adding this capability does not make every bug fix scan the whole
repository, export every shard, or reconstruct the application. Unchanged
sibling shards may be reused only when their exact content and consumed owner
fingerprints remain current.

## Four Command-Line Entries

Audit FlowGuard's own checked-in self-blueprint without writing any projection
or attempting reconstruction:

```powershell
python -m flowguard flowguard-self-blueprint-check --root . --json
```

Audit an inventory without changing it:

```powershell
python -m flowguard implementation-inventory-audit `
  --inventory implementation-inventory.json `
  --root . `
  --json
```

Check static and empirical status from existing artifacts without writing or
running missing owners:

```powershell
python -m flowguard model-blueprint-check `
  --inventory implementation-inventory.json `
  --manifest software-blueprint.json `
  --binding-report model-implementation-bindings.json `
  --observed-snapshot-fingerprint <current-snapshot-fingerprint> `
  --semantic-mesh-fingerprint <current-mesh-fingerprint> `
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
  --portable-owner-fingerprints '{"portable:system":"<current-portable-fingerprint>"}' `
  --resource-fingerprints '{"resource:runtime":"<current-resource-fingerprint>"}' `
  --oracle-fingerprints '{"oracle:behavior":"<current-oracle-fingerprint>"}' `
  --output exported-blueprint `
  --json
```

The self-audit, inventory audit, and check commands are read-only. Export writes only beneath the
explicit output directory and verifies its canonical manifest and
content-addressed JSON shards. None of the three commands starts a builder,
reconstruction job, missing validation owner, or model-authority update.

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

## 中文说明

实现蓝图解决的是一个很具体的问题：FlowGuard 不只要知道“软件应该怎么运
行”，还要确认这些模型是否真的连接到了让软件运行起来的全部代码和资源。

它先从独立实现清单出发，而不是相信模型自己列出的代码名单。每个有行为的
入口、状态写入和外部影响，都要反向找到模型义务或明确的负责人；每个模型
义务也要正向找到唯一的主要实现。只有文件路径和函数名还不够，还必须有不
依赖源码原文的语义说明、可判断对错的 oracle，以及构建、运行、配置、数据、
迁移和外部服务等资源引用。

静态结果和经验重建结果始终分开。`static_status=complete`、
`empirical_status=not_run` 的意思只是“蓝图静态闭合，但尚未验证重建”，绝
不能写成“已经从零重建成功”。即使加上 `--require-reconstruction`，命令也
只会检查是否已有匹配回执，绝不会自动启动重建。

普通修改仍然只看受影响范围：加载紧凑的蓝图身份、找到受影响的负责人邻域，
只更新失效的内容寻址分片。只有明确要求整套蓝图、导出、重建资格或发布闭合
时，才检查完整边界。

发布前可以让模型帮助寻找重复结构，但这不是随意删代码。只有具备当前等价性
证据的候选才可以删除或合并；公开入口如果必须保留为委托门面，还要有当前证
据证明它只转交给唯一的负责人和主路径，没有自己的业务权威。缺少证据、证据
过期或只证明少数属性时，都必须保留或继续验证。
