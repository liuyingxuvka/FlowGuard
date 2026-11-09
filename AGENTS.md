# FlowGuard repository rules

FlowGuard finds existing decisions and checks necessary copies against one executable rule.
Ordinary edits do not need an intent model or a separate task record.

<!-- flowguard:start -->
## FlowGuard rules for the project agent

1. Run the project's tests and read the FlowGuard lines; every red and lead ends with the next step: do it, and when it says to tell the owner, tell the owner before changing the structure.
2. A judgment or a field that must agree everywhere has one owner: `# flowguard: owner NAME` above it, `# flowguard: sensor NAME` above each copy, `writers=` on a data owner.
3. A rule the owner set that must keep holding goes into `tests/intent/`, its source the owner's words stored once, byte for byte, with `python -m flowguard req add <file|-> --id <id>`.
<!-- flowguard:end -->

## Owners and layout

- `flowguard/structure/`: generated Python map, fingerprints and fixed source queries.
- `flowguard/intent/`: rules, literal rows, source anchors, small flows, pytest integration and incremental checks.
- `flowguard/map/`: shared source readers, Git boundaries and immutable owner records.
- `tests/intent/`: FlowGuard's own product rules; ordinary tests remain in `tests/`.
- `.agents/skills/flowguard/`: the single public skill. `docs/intent-guide.md` explains the API.

## Working and publishing

- Extend the existing owner. Do not add another runner, record format or workflow for the same job.
- Keep expectations independent of the implementation; bind actual calls and retain genuine regressions.
- Save only actual owner words, byte for byte. Never edit `.flowguard/requests/` or invent attribution.
- Change code and tests together. Record the actual command, result and any unfinished boundary.
- Tests never hide errors behind skips. Effective platform/version `skipif` or `xfail` markers retain their meaning.
- One route per function: when a step fails, the error reaches the caller or is reported with its text; never a quiet default, a skipped check or a second path. `.flowguard/ledger.toml` lists every exception handler that can end without raising, per function with its count, what it does and why it may stay, and the written rule it serves; ordinary pytest fails on a new, changed or vanished one.
- Source equivalence uses `flowguard/map/common.py:normalize_newlines`; binary resources keep exact bytes.
- Keep generated maps, pytest caches and execution records out of git.
- Commit in your own words. Add `Request: R<id>` for the stored words the change answers.
- Before publication freeze the source, run the full suite with a virtual environment outside this project,
  and require the complete `ci.yml` on that exact main commit. All Linux Python 3.11/3.13 and Windows
  Python 3.12 jobs must succeed. Do not replace failed or incomplete results with an older success.

Version numbers are independent for each project; use the same MAJOR.MINOR.PATCH rules:

- At 1.0 and later, incompatible changes to a supported public CLI, skill id, SDK or saved input format raise MAJOR; backward-compatible features raise MINOR; corrections within the existing contract raise PATCH. Internal code volume or a dependency's version is not a version criterion. Never skip a number.
- Before 1.0, keep the unstable status explicit: incompatible public changes raise MINOR and describe migration. Publish 1.0 when declaring a stable contract, not merely because the implementation changed.
- A format consumed by a documented command remains a contract even when generated. Distinguish it from disposable caches. A new required field or changed supported meaning needs a compatibility decision; do not silently reinterpret old material.
- For a changed public surface, retain a small existing valid example and a real counterexample. Explain a corrected old bug separately from a new requirement. Give rejected old material a rebuild path from original inputs; never invent verified results, source digests or evidence fields to make it load.
- Record the release classification and migration in the existing CHANGELOG. Preserve historical commits, tags and releases; append corrections instead of renumbering them. Changes limited to repository policy or maintenance tooling do not by themselves require a product release. Raise a maintenance dependency only for a capability actually used or an evidenced correctness fix required by that workflow, not merely because a new tag exists.

Public saved inputs include the documented intent rules, literal rows, original data and immutable owner-word archives. Generated maps, traces and test caches may be rebuilt; they do not replace those inputs or independently verify their meaning.

Changelogs use the actual date and describe user-visible changes. Installing the skill, tagging and publishing require the maintainer's explicit request.
