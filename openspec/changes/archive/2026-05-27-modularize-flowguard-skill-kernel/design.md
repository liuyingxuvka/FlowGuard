## Design

### Kernel Shape

The main `SKILL.md` becomes the Skill Kernel:

- trigger summary;
- hard gates;
- route map;
- workflow skeleton;
- resource map.

It should not inline every specialized protocol. Specialized procedures live in
`references/*.md`.

### Sub-Protocol Ownership

Agent sub-protocols are behavior guides:

- `modeling_protocol.md`: core model-first workflow and flow-type guidance.
- `model_mesh_protocol.md`: multi-model and oversized model governance.
- `test_mesh_protocol.md`: slow/layered validation evidence.
- `structure_mesh_protocol.md`: large script/module decomposition evidence.
- `model_miss_protocol.md`: post-runtime model miss handling.
- `conformance_adoption_protocol.md`: conformance replay, install verification,
  adoption logging, and sync evidence.
- `long_check_protocol.md`: background model/test execution artifact contract.
- `framework_upgrade_protocol.md`: FlowGuard self-upgrade and broad capability
  claims.

Package helper APIs remain APIs, not sub-skills:

- `RiskIntent`, property factories, packs, templates, `FlowGuardCheckPlan`,
  `review_test_mesh`, `review_structure_mesh`, and `review_hierarchical_mesh`.

### Compatibility

Existing public references remain available. The main Skill still mentions the
important trigger phrases so Codex can discover the Skill. Detailed strings
move into references and docs tests should verify the route rather than require
all long-form rules in `SKILL.md`.

### Validation

Validation requires:

- OpenSpec strict validation;
- a FlowGuard rollout model for Skill Kernel modularization;
- focused docs/API/template tests;
- full unit test discovery;
- local install and shadow workspace sync before release;
- GitHub push/tag/release only after local validation passes.
