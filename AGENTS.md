# FlowGuard repository rules

This repository uses its own small executable feature models and native recorder.

## Every task

1. At the start of a session and after any loss of context, run `python -m flowguard status` before anything else.
2. Store actual owner words once with `python -m flowguard req add <file|-> --id <id>`, byte for byte: never a plan, a list or text an AI wrote. Use `--supersedes` for a replacement; never edit `.flowguard/requests/`.
3. Find the owner with `python -m flowguard where NAME`. For changed state, actions, conditions, settings or endings, update the affected feature model before code: turn affected old and new requested outcomes into explicit `reach`/`progress` promises, even in the first model. Run `check`. For code claims, follow the installed `flowguard/flow/HOWTO.md` and bind only the affected actions to real public calls. When explaining a flow, embed the `python -m flowguard show` picture as `![Flow](PATH)` using its returned path.
4. Change code and tests together. Run the affected real tests and report their exact result, plus any inherited technical work still open. Use `check --commit-ready` against the staged bytes; finished UNKNOWN remains visible and permits a commit. No automatic hook is required.
5. Commit in your own words, adding `Request: R<n>` for a change answering stored owner words. Do not invent attribution for experimental plans or AI prose.
6. Before publishing, freeze the source and require the complete real `ci.yml` workflow on that exact SHA. Ubuntu Python 3.11 runs the full model and test release in four shards; Python 3.13 runs native recorder/adapter controls and static/package smoke; Windows Python 3.12 runs the complete flow suite and two disjoint static/package smoke groups. All jobs must pass. Do not repeat the full local suite just to create another checkpoint.

## Owners and layout

- `flowguard/flow/`: the single executable model engine, native recorder, jobs, history, decisions, pictures and release.
- `flowguard/map/`: shared inventory, static source queries, original owner words and test-tree utilities; no map file or target interpreter.
- `.flowguard/flow/`: independent self-models; useful code bindings use the same native adapter/recorder as projects.
- `.agents/skills/flowguard/`: the single public skill; the installed HOWTO owns detailed model-writing guidance.
- `tests/`, `examples/`, `docs/`: actual controls, small examples and upgrade guidance.

## Working rules

- Extend the existing owner rather than adding another executor, record format, cache or workflow for the same job.
- Keep required old behavior when changing shared state. A clean reduced abstraction does not prove omitted behavior. Preserve scope and actual regression evidence; do not silence a conflict by deleting its model.
- Keep source and request boundaries honest. Unknown native observations, unfinished work and capped exploration stay visible.
- No generated execution records or standalone hash manifests in git. Preserve immutable owner records; keep disposable caches out of commits.
- Tests never skip through swallowed errors. Only explicit platform/version/os `pytest.mark.skipif` conditions may skip; the test hooks enforce this. Never weaken a test to hide an actual failure.
- Source equivalence uses `flowguard/map/common.py:normalize_newlines` for source text, with LF/CRLF controls; binary resources keep exact bytes.
- Changelogs describe user-visible changes with the actual date; omit internal action IDs and branch names.
- Installing the skill, tagging and publication require the maintainer's explicit request.
