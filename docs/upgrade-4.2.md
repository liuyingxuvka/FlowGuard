# Moving from FlowGuard 4.1 to 4.2

4.2 is a feature release. Source comments, rules, literal rows, sources, flows, ledger entries and owner-word records keep their meaning and bytes; nothing needs rewriting. This page lists what you will notice.

## What changes in a run

| 4.1 | 4.2 |
| --- | --- |
| Every `python -m flowguard` brief moved the task baseline to HEAD, so a brief after a commit dropped what the task had changed | The baseline stays while it is an ancestor of HEAD. Start each task with `python -m flowguard new-task` (rule 1 of the block `init` writes says so). |
| Without a brief, pytest compared with HEAD, so a commit made during the task hid what the task changed | The first pytest session, `check` or `check --static` of a task records HEAD as its baseline when none is recorded (not on a detached HEAD, not in `--collect-only`, not under `--base`). Before that the title says `相对 HEAD`. |
| Pytest stayed quiet when only TS/JS, Prisma or SQL files changed | Such a change runs the same map checks as `check --static`. |
| Two owners' pair reds shared one line `配对没写：…` | One line per owner: `配对没写 OWNER：…`. |
| A pair's operation, and the delete check's, reached test files and the other packages of a monorepo by name | Both stay in production code of the caller's package; a test's fixture write is not held to a pair. Some delete leads that a test or another package used to hide now appear. |
| The value gate took a field's set from the first Prisma enum it met, a provider template or a `docs` snapshot included, and dropped the SQL `CHECK` of such a field | Only the schemas the generator reads gate (a package that names none is judged by its own schemas and says so); a `CHECK` stays beside the enum. A TS type is gated by its own sets unless the file imports it from the Prisma client. |
| A field's second value set (a CHECK beside an enum, a TS type) was named `values:NAME:<place with line numbers>` | Named `values:NAME:FILE`; the first enum of a schema in use stays `values:NAME`. |
| Label leads grouped codes, keys and routes with labels | Only spellings of one kind group; test files and FlowGuard's generated files are left out. |
| `--all` showed this change's leads after the old ones, often in the overflow | New leads come first; `--leads` prints them all. |
| `check --base X` was titled `相对 --flowguard-base X` | `相对 --base X`. |
| A vitest point no test reached read `未验证：NAME：没有测试走到（file:line）` | `未验证：NAME（file:line）：没有测试走到`, and only the points of the package the run belongs to. |
| A vitest run with the execution side on had only the project's own tests | It also has FlowGuard's project with one test case, "FlowGuard execution side", which fails on an execution-side red and passes otherwise. |
| `init` wrote the interpreter path into the generated npm files, registered the plugin in both `addopts` and `conftest.py`, and added the static test to every test script that runs named folders | The path lives in the git-ignored `.flowguard/cache/python`; the plugin is registered once, and the older conftest line is removed; the static test goes into one script (`test` first, then a unit script), never into a watch, integration or end-to-end suite, and only into a call whose options `init` can read. Run `init` again to update the generated files. |

## New, opt-in or automatic

- `on=update` / `on=create` after a data owner's `with=` list.
- Structure listing: never-filled tables, label tables and delete rules that differ between two Prisma schemas each close with a `[structure]` decision, which also silences the leads a change would get; the legacy fallbacks, grouped by how the catch ends, leave the list when their ledger entry gets a real reason and rule, or when the code hands the error on.
- `[tool.flowguard] archives = ["path/**", ...]` names the files no code runs against (default: under a `docs` folder).
- `show Model.field` lists `with=` candidates; `show QUERY --full`; `check --leads`.
