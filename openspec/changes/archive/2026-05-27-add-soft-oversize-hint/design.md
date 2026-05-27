## Context

The user wants a gentle nudge, not a governance gate. The wording should help
agents notice oversized work without making normal work feel blocked or
ceremonial.

## Design

Use one compact hint:

```text
When a model, test, script, module, or command is becoming large, slow, or hard
to follow, consider whether a parent/child split would make it easier to
maintain or verify.
```

Follow with a compact option map:

```text
Models -> ModelMesh
Tests -> TestMesh
Scripts/modules/APIs -> StructureMesh
Long checks -> LongCheck observability
```

Avoid:

- fixed runtime thresholds;
- "must split" language;
- new sub-skills or gates;
- external planner requirements;
- repeated disclaimers that over-explain the non-goal.

## Validation

- Focused docs tests.
- Skill Kernel FlowGuard rollout checks.
- Full practical unit test suite.
- OpenSpec strict validation.
