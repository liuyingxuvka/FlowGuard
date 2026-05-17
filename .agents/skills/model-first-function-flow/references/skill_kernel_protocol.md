# FlowGuard Skill Kernel Protocol

The `model-first-function-flow` Skill is a kernel, not a monolith. The kernel
owns trigger selection, hard gates, route selection, and resource discovery.
Detailed procedures live in sub-protocol references.

## Kernel Owns

- applicability decision: `use_flowguard`, `skip_with_reason`, or
  `needs_human_review`;
- flow lens: `behavior_flow`, `argument_flow`, or `decision_flow`;
- hard gates: real package import, no fake mini-framework, executable evidence
  over prose, skipped is not pass, and adoption evidence for real use;
- route map to specialized protocols;
- distinction between agent sub-protocols and package helper APIs.

## Sub-Protocols Own

| Sub-protocol | Owns |
| --- | --- |
| `core_modeling` | Risk Intent, state write inventory, function blocks, invariants, Explorer, CheckPlan |
| `model_mesh_maintenance` | parent/child model hierarchy and oversized-model governance |
| `test_mesh_maintenance` | parent/child test hierarchy plus validation evidence |
| `structure_mesh_maintenance` | parent/child script/module structure split evidence |
| `model_miss_review` | post-runtime model miss classification and closure |
| `conformance_adoption` | replay, install sync, shadow workspace sync, release sync, adoption evidence |
| `long_check_observability` | background log artifacts and completion proof |
| `framework_upgrade` | FlowGuard self-upgrades and broad capability claims |

## Helper APIs Are Not Sub-Skills

These are package helpers:

- `RiskIntent`, `RiskProfile`, `FlowGuardCheckPlan`;
- property factories and packs;
- `review_hierarchical_mesh()`, `review_test_mesh()`,
  `review_structure_mesh()`;
- public starter templates.

They can support a route, but they are not independently triggerable agent
sub-skills.

## Maintenance Rules

- Keep `SKILL.md` short enough to scan as a router.
- Add detailed procedures to references, not the kernel.
- Keep ModelMesh, TestMesh, and StructureMesh aligned as sibling
  parent/child partition routes for models, tests, and code structure.
- Avoid duplicate ownership of the same rule across multiple references.
- Preserve standalone FlowGuard use; OpenSpec/SPAC handoff remains optional.
- Before broad release, verify the installed Skill and source Skill match.
