## Why

FlowGuard v0.58.2 incorrectly let `project-upgrade` depend on an author-side
suite map that was reachable only from an editable checkout. A real
non-editable installation therefore blocks every ordinary-project upgrade
before writing, even when the current global 15-skill consumer distribution is
complete.

## What Changes

- Replace the editable-checkout suite-map dependency in project adoption with
  validation of the one installed global consumer distribution and its
  target-owned release identities.
- Keep author suite maps, `.skillguard`, and project-local FlowGuard skill
  trees outside ordinary-project audit and upgrade.
- Add a subprocess regression that installs FlowGuard non-editably, connects a
  clean global 15-skill distribution, upgrades an empty project, and proves
  both successful writes and zero local suite residue.
- Backpropagate the v0.58.2 post-green failure into the project-adoption model,
  documentation, release checks, and SkillGuard-maintained FlowGuard contract.
- Preserve strict visible failure for a missing, modified, incomplete, or
  author-control-polluted global consumer distribution; no fallback or
  compatibility reader is introduced.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-adoption-version-gate`: Project audit and writing upgrade consume
  the global consumer distribution directly and remain portable under a
  non-editable FlowGuard installation.
- `flowguard-suite-inventory`: The clean installed consumer distribution
  exposes enough target-owned identity to validate its exact members and files
  without an author suite map.

## Impact

Affected surfaces include `flowguard/project_adoption.py`, installed-consumer
validation in the FlowGuard package, project-adoption tests, the checkout-local
project-adoption model, project integration guidance, the FlowGuard skill
contract, package versioning, installation parity, and release verification.
