## Why

FlowGuard's framework package has accumulated repeated command wrappers, broad
helper surfaces, and shadow-workspace model artifacts as the product grew. This
change reduces safe structural complexity now while keeping public imports,
CLI behavior, validation evidence, and peer-agent work intact.

## What Changes

- Add model-backed simplification evidence for the first contraction pass:
  existing-model grounding, architecture-reduction classification,
  StructureMesh target ownership, and development-process validation gates.
- Consolidate repetitive FlowGuard template CLI wrapper functions behind a
  single table-driven command registration path while preserving command names,
  stdout JSON behavior, `--output`, and `--force`.
- Keep the broad `flowguard.__init__` public facade stable; do not remove
  public exports as part of this cleanup.
- Clean shadow-only duplicate `.flowguard` model artifacts through the local
  sync pass, without deleting peer-created OpenSpec or source work.

## Capabilities

### New Capabilities

- `flowguard-structure-simplification`: Defines the observable contract for
  model-backed structural simplification of FlowGuard itself, including public
  facade preservation, CLI template parity, shadow artifact cleanup, validation
  evidence, and local install/workspace sync.

### Modified Capabilities

- None.

## Impact

- Affected code: `flowguard/__main__.py`, focused CLI/template tests, the new
  OpenSpec change, FlowGuard adoption evidence, and shadow workspace cleanup.
- Public API: no intended import, dataclass, report, or command-name changes.
- Validation: focused unit tests, FlowGuard self-model checks, OpenSpec
  validation, local editable install verification, and shadow import checks.
