# FlowGuard

<p align="center"><img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" /></p>

[中文说明](./README.zh-CN.md)

FlowGuard gives an AI a small executable model of a feature, connected to real code and stored owner words. It checks combinations that examples miss, keeps unresolved conflicts across sessions, and helps the next change start from existing knowledge.

## Five-minute start

Install from this repository; the PyPI package called flowguard is a different project.

```bash
python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git@v1.4.0"
python scripts/install_skill.py --target ~/.codex/skills
cd your-project
python -m flowguard status
python -m flowguard req add owner-message.txt --id R1
python -m flowguard where place_order
# For a behavior change, update the affected feature model before implementation.
python -m flowguard check
python -m pytest -q tests/test_orders.py
git add -A
git commit -m "Charge each order once" -m "Request: R1"
```

The skill installer is in a source checkout. Point its target at your agent's skills directory. Static queries and owner records work without a model. Start a model when state, actions, conditions, settings or endings change; the installed [model guide](./flowguard/flow/HOWTO.md) includes a runnable example and a code adapter.

## One model, connected to code

Write one small feature machine in `.flowguard/flow/`, using `Model`, fields, actions and explicit promises. Keep the model's expected behavior independent of the implementation. Bind it through `Model.bind_adapter` to compare actual calls and outcomes with those expectations. The same native recorder captures actual reads, calls and selected pytest execution; missing observations remain unknown.

For existing Python code, `python -m flowguard draft pkg/orders.py:Order` reads static vocabulary without executing the project. Add `--write` once to create model/adapter TODOs. Let the AI complete independent behavior from the requests and connect the real calls, then run `check`. The draft is a starting point, not a verdict; completed author files are never replaced.

`check` explores the declared finite state space. It reports violated promises, dead ends and unreachable goals with the shortest available path and their source requests. `check --full` also tries deliberate breakages. A clean result covers the declared model and observed code boundary; omitted behavior still needs a model or a relevant test.

Owner words live unchanged in `.flowguard/requests/`. Open conflicts and their retained scope live in `.flowguard/conflicts.json` and remain visible after a restart. A smaller model cannot silently erase an earlier obligation. Real code repairs need current native correspondence and an executed regression; a genuine replacement requirement uses the original owner words. `show` draws the stored witness without rerunning the application.

## Daily commands

| command | purpose |
| --- | --- |
| `python -m flowguard status` | Refresh changed models; show open work, source words and questions. |
| `python -m flowguard where NAME` | Find source, callers, model coverage and request links without importing project code. |
| `python -m flowguard draft pkg/orders.py:Order` | Read static starting vocabulary; `--write` creates model/adapter TODOs once. |
| `python -m flowguard req add FILE --id R1` | Preserve one actual owner message byte for byte; use `--supersedes R0` when it replaces an earlier request. |
| `python -m flowguard check` | Check affected work through the shared background jobs and reuse current results. |
| `python -m flowguard check --full` | Run the complete model checks, including deliberate breakages. |
| `python -m flowguard check --tests tests/test_orders.py` | Explicitly audit selected real tests for fallback behavior; ordinary checks do not run pytest. |
| `python -m flowguard show` | Draw open conflicts, otherwise the change against HEAD; add `MODEL --before REV` to choose. |
| `python -m flowguard decide ID --owner "QUOTE" --request R1` | Record an actual sourced owner choice for a requirement conflict. |
| `python -m flowguard check --commit-ready` | Read current results against the staged bytes; no hook is installed automatically. |
| `python -m flowguard release --shards 4` | Check all models, run every collected project test once, then retain the original-byte snapshot. |

`check` returns clean, conflict, model error, UNKNOWN or RUNNING. Its default wait is 90 seconds; repeat the same command to resume existing work. Finished UNKNOWN stays visible and permits a commit. `release` without `--shards` reports that tests were not run. Pictures use node, Playwright and Chromium; Mermaid text remains available without them.

## Use existing knowledge cheaply

Keep each model focused on the changed feature, including the old behaviors that share its state. Read the compact `status` or `where` result first; expand only what you need. `where --flow`, `--arch`, `--text` and `--keyflows` inspect calls, architecture, original passages and shared stores. Add `--all`, `--json`, `--root DIR` or `--at REF` as needed (`--at` selects historical text). Static matches are candidates, not semantic proof.

The model is an external record the AI actively uses to plan a change, question an assumption and compare actual behavior. It is useful when it prevents rediscovery or catches a real mistake; more fields, records or mandatory checks do not make it better by themselves.

## Upgrade and platform boundary

Version 1.0 uses one flow engine. The old map, old `.flowguard/models/`, target commands and experimental `behave` engine are removed. Follow the [upgrade guide](./docs/upgrade-1.0.md) to carry useful rules and bindings into the current models and tests; old-format execution explains what needs upgrading. Static source queries remain usable during migration.

Flow execution works on Linux and Windows with Python 3.11 or newer. macOS retains static queries and request storage; flow execution reports the platform limit. Models prove only their declared finite boundary and recorded observations. Keep normal tests, review and production monitoring.

## Repository

- `flowguard/flow/`: the model, native recorder, jobs, conflict history, pictures and release owner.
- `flowguard/map/`: shared source inventory, static queries, requests and ordinary test-tree sharding; no hand-maintained map file.
- `.flowguard/flow/`: FlowGuard's own feature models.
- `.agents/skills/flowguard/`: the single public skill.
- `tests/`, `examples/`, `docs/`: controls, examples and longer guidance.

License: MIT
