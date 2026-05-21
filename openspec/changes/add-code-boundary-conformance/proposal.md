## Why

FlowGuard already compares model obligations, optional code contracts, and test
evidence. It also has a conservative Python source audit. Those layers still do
not directly answer a practical boundary question:

Does the real code surface only accept the inputs declared by the model-backed
contract, and does it only emit the outputs, errors, state writes, and side
effects declared by that boundary?

This matters when a model remains intentionally coarse. Ordinary tests can pass
representative examples while the real code accepts an unexpected input, emits
an extra output, or performs an undeclared side effect inside the modeled block.

## What Changes

- Add a code-boundary conformance helper under Model-Test Alignment.
- Let a review declare a finite code boundary contract and feed runtime
  observations from real code tests into that contract.
- Block green alignment when forbidden inputs are accepted or when real code
  produces undeclared outputs, error paths, state writes, or side effects.
- Update public templates, docs, Skill guidance, and rollout checks so agents
  know that code-boundary evidence is runtime/test evidence, not only model
  checking or source-audit evidence.

## Impact

This is a public helper/API addition. It preserves model-test-only and
model-test-code alignment compatibility. It does not add a new satellite skill,
does not change the artifact schema version, and does not add runtime
dependencies.
