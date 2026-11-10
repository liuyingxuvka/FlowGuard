# Moving from FlowGuard 4.1 to 4.2

4.2 is a feature release. Source comments, rules, literal rows, sources, flows, ledger entries, owner-word records and `[structure]` decisions keep their meaning and bytes; nothing needs rewriting, except the decisions on a schema folder listed below. This page lists what you will notice.

## What changes in a run

| 4.1 | 4.2 |
| --- | --- |
| Every `python -m flowguard` brief moved the task baseline to HEAD, so a brief after a commit dropped what the task had changed | The baseline stays while it is an ancestor of HEAD. Start each task with `python -m flowguard new-task`; rule 1 of the block `init` writes says so, so run `init` again to update a 4.1 block. new-task says which earlier commits it stops comparing and how to compare them once (`python -m pytest --flowguard-base OLD`). |
| Without a brief, pytest compared with HEAD, so a commit made during the task hid what the task changed | The first pytest session, `check` or `check --static` of a task on a branch records HEAD as its baseline when none is recorded (not on a detached HEAD, not in `--collect-only`, not under `--base` or `--flowguard-base`). Until new-task runs again, later tasks' commits count as this task's change: the title says how many commits the start lies before HEAD and names new-task. Where HEAD stands in, the title says `相对 HEAD`. |
| A recorded baseline commit the clone lacks (a shallow clone, rewritten history, a copied cache) compared nothing, silently or with Git's error | One line names it (`记下的任务开始 abc1234 不在这个仓库里…`) and the next step, new-task; nothing new is compared. |
| Pytest stayed quiet when only TS/JS, Prisma or SQL files changed | Such a change runs the same map checks as `check --static`. |
| Two owners' pair reds shared one line `配对没写：…` | One line per owner: `配对没写 OWNER：…`. |
| A pair's operation, and the delete check's, reached test files and the other packages of a monorepo by name | Both stay in production code of the caller's package; a test's fixture write is not held to a pair. Some delete leads that a test or another package used to hide now appear. |
| The value gate took a field's set from the first Prisma enum it met anywhere in the repository, a provider template or a `docs` snapshot included, and dropped the SQL `CHECK` of such a field | Only the schemas the generator reads gate, a write by its own package's schema; a `CHECK` stays beside the enum; a TS typed object is judged by its own type's declaration. Some reds of 4.1 that came from another package's or a template's enum go away; reds against a field's CHECK appear. |
| Each field had one value problem, `values:NAME` | It keeps that name; a field's further sets (a CHECK beside an enum, a second schema's enum, a TS type) are problems of their own, `values:NAME:<place>`. A 4.1 decision keeps closing what it closed. |
| A Prisma schema folder (several files, one datasource) was read file by file | It is one schema, named by its folder. Column and onDelete problems recorded per fragment (`columns:prisma/migrations/~prisma/schema/user.prisma`) are named by the folder (`columns:prisma/migrations/~prisma/schema/`): record those decisions again under the new name. |
| Label leads grouped codes, keys and routes with labels | Only spellings of one kind group; test files and FlowGuard's generated files are left out. |
| `--all` showed this change's leads after the old ones, often in the overflow | New leads come first; `--leads` prints them all. |
| `check --base X` was titled `相对 --flowguard-base X`, and without rules it read the ledger against the task baseline | `相对 --base X`, and the ledger is read against X. |
| A vitest point no test reached read `未验证：NAME：没有测试走到（file:line）` | `未验证：NAME（file:line）：没有测试走到`, and only the points of the package the run belongs to. |
| A vitest run with the execution side on had only the project's own tests | It also has FlowGuard's project with one test case, "FlowGuard execution side", which fails on an execution-side red and passes otherwise. |
| `init` changed no `package.json` script, always said "npm test runs python -m flowguard check --static" (even when no script ran the file), wrote a test next to every `package.json` and wrote the interpreter's path into it | `init` adds the static test to one test script that runs named folders only (`test` first, then a unit script), never to a watch, debug, integration or end-to-end suite, and only to a call whose options it can read; it says which script runs the check, or what to add; it writes no test where no runner is named, and keeps the interpreter's path in the git-ignored `.flowguard/cache/python`. Running `init` again on a 4.1 project may therefore edit one script; it says so. |

## New, opt-in or automatic

- `on=update` / `on=create` after a data owner's `with=` list.
- Structure listing: never-filled tables, label tables and delete rules that differ between two Prisma schemas each close with a `[structure]` decision, which also silences the leads a change would get; the legacy fallbacks, grouped by how the catch ends, leave the list when their ledger entry gets a real reason and rule, or when the code hands the error on.
- `[tool.flowguard] archives = ["path/**", ...]` names the files no code runs against (default: under a `docs` folder).
- `show Model.field` lists `with=` candidates; `show QUERY --full`; `check --leads`.

## Known limits

- A Prisma write in a package whose schemas in use declare the field with different enums, or where a second client of its own types it as text, is not judged: FlowGuard cannot tell which client wrote it.
- A TS type imported through a barrel (`export * from`) or a `tsconfig` path alias is judged by the member's only set across the repository, not by the declaration it imports.
- A package whose own schemas are all guessed templates is judged by another package's schema in use when one defines the model.
- A provider template that a sync script copies onto `schema.prisma` and that lacks a foreign key is not reported by the onDelete comparison; the column check sees a missing column only.
