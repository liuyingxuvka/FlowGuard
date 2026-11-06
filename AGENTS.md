# FlowGuard repository rules

FlowGuard finds existing decisions and checks necessary copies against one executable rule.
Ordinary edits do not need an intent model or a separate task record.

<!-- flowguard:start -->
## FlowGuard rules for the project agent

1. At session start, look at `python -m flowguard` when the project has intent rules.
2. Before writing a decision, use `python -m flowguard show "what it decides"` to find its existing owner.
3. Write one rule, bind each real home, and add a literal regression row only when a decision has copies, the owner says everywhere, or a bug was fixed. Otherwise stay quiet.
4. After changing a bound decision run `python -m flowguard check`; CI runs `check --all`. Store actual owner words once with `req add`.
<!-- flowguard:end -->

## Owners and layout

- `flowguard/structure/`: generated Python map, fingerprints and fixed source queries.
- `flowguard/intent/`: rules, literal rows, real homes, pytest integration and incremental checks.
- `flowguard/map/`: shared source readers, Git boundaries and immutable owner records.
- `tests/intent/`: FlowGuard's own product rules; ordinary tests remain in `tests/`.
- `.agents/skills/flowguard/`: the single public skill. `docs/intent-guide.md` explains the API.

## Working and publishing

- Extend the existing owner. Do not add another runner, record format or workflow for the same job.
- Keep expectations independent of the implementation; bind actual calls and retain genuine regressions.
- Save only actual owner words, byte for byte. Never edit `.flowguard/requests/` or invent attribution.
- Change code and tests together. Record the actual command, result and any unfinished boundary.
- Tests never hide errors behind skips. Effective platform/version `skipif` or `xfail` markers retain their meaning.
- Source equivalence uses `flowguard/map/common.py:normalize_newlines`; binary resources keep exact bytes.
- Keep generated maps, pytest caches and execution records out of git.
- Commit in your own words. Add `Request: R<id>` for the stored words the change answers.
- Before publication freeze the source, run the full suite with a virtual environment outside this project,
  and require the complete `ci.yml` on that exact main commit. All Linux Python 3.11/3.13 and Windows
  Python 3.12 jobs must succeed. Do not replace failed or incomplete results with an older success.
- Changelogs use the actual date and describe user-visible changes. Feature releases raise the middle
  version number; small fixes raise the last. Installing the skill, tagging and publishing require
  the maintainer's explicit request.
