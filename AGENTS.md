# FlowGuard repository rules

FlowGuard maintains a living, code-anchored map of a project (`.flowguard/map.json`),
executable models of its risky flows, and 10 capability reviews. This repository uses
FlowGuard on itself.

## Every task in this repository

1. `python -m flowguard read` - read the map first; open only the files of the components you touch.
2. Make the change. Keep responsibilities single-owned; extend the existing owner instead of adding a second one.
3. `python -m flowguard change` - fix every check error; run the tests and models it lists.
4. Update the description of every component listed as REVIEW, then `python -m flowguard map confirm <id>`.
5. Before each push, run the affected checks selected above and report their results. For the final frozen source SHA, the complete `ci.yml` workflow must pass: Ubuntu Python 3.11 runs `python -m pytest -q` and `python -m flowguard release` once; Ubuntu Python 3.13 and Windows Python 3.12 run the six core path/packaging test files and the real skill copy/`--check`. Those two smoke environments do not claim complete cross-platform coverage. Publication waits for the entire workflow on the exact source SHA; do not repeat the full local suite solely to produce another checkpoint.

## Layout

- `flowguard/` engine and the 10 capabilities; `flowguard/map/` map, discovery and proof layer.
- `.agents/skills/flowguard/` the single public skill (SKILL.md, references, one protocol per capability, assets).
- `.flowguard/map.json`, `.flowguard/models/`, `.flowguard/verification/owners/*/run_checks.py`:
  FlowGuard's own map and models. `.flowguard/cache/` is never committed.
- `tests/` unit tests; `examples/` runnable teaching models; `docs/` long-form notes.

## Rules

- No generated evidence, receipts or hashes in git except the `fingerprint` fields written by `confirm`.
- Do not add a second way to do something that already has an owner; extend the owner.
- When `map lint` reports a real architecture problem you are not fixing now, record it in
  `accepted_debts` with a reason instead of hiding it.
- Report exactly which commands you ran and their results; never mark unrun checks as passed.
- Installing the skill (`python scripts/install_skill.py --target <skills dir>`), tagging and
  publishing are separate steps that need the maintainer's explicit request.
