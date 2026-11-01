# FlowGuard repository rules

FlowGuard keeps the owner's words, finds code statically and runs the project's legacy
executable models in its release gate. This repository uses FlowGuard on itself.

## Every task in this repository

1. At the start of a session and after any loss of context, run `python -m flowguard status` before anything else.
2. When the owner asks for something, store the owner's own words once, as received: `python -m flowguard req add <file|-> --id <id>`. It stores only words the owner wrote, byte for byte: never a plan, a list or text an AI wrote. When a new owner message replaces an earlier one, add `--supersedes <old id>`; never edit `.flowguard/requests/`.
3. Find code with `python -m flowguard where NAME`; change code and its tests together; run the affected tests (`python -m pytest -q <files>`) and report exactly what you ran and the result.
4. Commit code and tests together in one commit with a message in your own words; add a line `Request: R<n>` when the change answers a stored owner request. The legacy map, `.flowguard/models/` and the target commands need no upkeep; when a legacy self-model fails after a change, fix the code or edit that model file directly.
5. Before each push, run the affected checks selected above and report their results. For the final frozen source SHA, the complete `ci.yml` workflow must pass: Ubuntu Python 3.11 runs the complete legacy release and test suite through `python -m flowguard release --shards 4`; Ubuntu Python 3.13 and the two nonoverlapping Windows Python 3.12 smoke jobs run the listed core path, packaging and independent static-query files. The real skill copy/`--check` runs once in each smoke environment. All jobs must pass; smoke jobs do not claim complete cross-platform coverage. Publication waits for the entire workflow on the exact source SHA; do not repeat the full local suite solely to produce another checkpoint.

## Layout

- `flowguard/` engine, node kinds (`validator.py`, `ui_flow.py`), the test-tree shard tool; `flowguard/map/` map, target, discovery and proof layer.
- `.agents/skills/flowguard/` the single public skill (SKILL.md, references).
- `.flowguard/map.json`, `.flowguard/models/`:
  FlowGuard's own map and models. `.flowguard/cache/` is never committed.
- `tests/` unit tests; `examples/` runnable teaching models; `docs/` long-form notes.

## Rules

- No generated check outputs, execution records or standalone hashes in git except the `fingerprint` fields written by `confirm`.
- Do not add a second way to do something that already has an owner; extend the owner.
- When `map lint` reports a real architecture problem you are not fixing now, record it in
  `accepted_debts` with a reason instead of hiding it.
- Report exactly which commands you ran and their results; never mark unrun checks as passed.
- Installing the skill (`python scripts/install_skill.py --target <skills dir>`), tagging and
  publishing are separate steps that need the maintainer's explicit request.

- Source-equivalence and fingerprint byte comparisons must use `flowguard/map/common.py:normalize_newlines`, with LF and CRLF coverage.
- CHANGELOG entries must describe user-visible changes in plain language, use the actual release date, and omit internal action IDs and branch names.

## Unreleased behavior engine

The resumed engine is entered only with `python -m flowguard.behave` on Python 3.12 or newer. Keep the released static `where` queries independent from it. The Python 3.11 legacy lane collects bootstrap guards and ignores native engine tests; Ubuntu Python 3.13 runs the complete engine tests once in the existing workflow. Do not replace full-state or fresh-evidence checks with sampled success claims.
