# Moving from FlowGuard 4.1 to 4.2

4.2 is a feature release. Source comments, rules, literal rows, sources, flows, ledger entries and owner-word records keep their meaning and bytes; nothing needs rewriting. This page lists what you will notice.

## What changes in a run

| 4.1 | 4.2 |
| --- | --- |
| Every `python -m flowguard` brief moved the task baseline to HEAD, so a brief after a commit dropped what the task had changed | The baseline stays while it is an ancestor of HEAD. Start the next task with `python -m flowguard new-task`. |
| Pytest stayed quiet when only TS/JS, Prisma or SQL files changed | Such a change runs the same map checks as `check --static`. |
| Two owners' pair reds shared one line `配对没写：…` | One line per owner: `配对没写 OWNER：…`. |
| A pair's operation reached test files and the other packages of a monorepo by name | It stays in production code of the caller's package; a test's fixture write is not held to the pair. |
| The value gate took a field's set from the first Prisma enum it met, a provider template included, and dropped the SQL `CHECK` of such a field | Only the schemas the generator reads gate (a package that names none is judged by all and says so); a `CHECK` stays beside the enum. A TS type is gated by its own sets unless the file imports it from the Prisma client. |
| Label leads grouped codes, keys and routes with labels | Only spellings of one kind group; test files and FlowGuard's generated files are left out. |
| `--all` showed this change's leads after the old ones, often in the overflow | New leads come first; `--leads` prints them all. |
| `init` wrote the interpreter path into the generated npm files and registered the plugin in both `addopts` and `conftest.py` | The path lives in the git-ignored `.flowguard/cache/python`; the plugin is registered once, and the older conftest line is removed. Run `init` again to update the generated files. |

## New, opt-in or automatic

- `on=update` / `on=create` after a data owner's `with=` list.
- Structure listing: never-filled tables, label tables, delete rules that differ between two Prisma schemas, legacy fallbacks by how the catch ends; each closes with a `[structure]` decision.
- `init` adds the static test to one unit suite script and never to an integration or end-to-end suite.
- `[tool.flowguard] archives = ["path/**", ...]` names the files no code runs against (default: under a `docs` folder).
- `show Model.field` lists `with=` candidates; `show QUERY --full`; `check --leads`.
- vitest: an execution-side red is a failed test case in the reporters.
