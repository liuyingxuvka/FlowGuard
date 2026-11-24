# FlowGuard

<p align="center"><img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" /></p>

[中文说明](./README.zh-CN.md)

FlowGuard keeps recorded agreements consistent while a coding AI changes a project. Register the copies that must agree, the fields that must be written together, and the functions allowed to write a field. Ordinary tests check those agreements, independent intent rules and the fallback ledger.

Finding a problem still takes careful review. Once found, register the agreement in the same change so later work cannot quietly break it. FlowGuard does not supply missing business decisions; the owner makes those decisions.

## Start

Install from this repository; the similarly named PyPI project is different. Python 3.11 or newer is required.

```bash
python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git"
cd your-project
python -m flowguard init
python -m flowguard new-task
python -m pytest
```

`init` connects the project's tests, writes its FlowGuard rules block and adds a CI fragment. When the block in `AGENTS.md` or `CLAUDE.md` differs from the one this version writes, the brief says so; running `init` again rewrites it. For a Vitest or Jest project, it also writes a static check test and reports which npm script runs it; Vitest gets the execution adapter. Use the project's ordinary test command after setup.

`init` writes a static-only CI fragment in a project whose tests npm runs and pytest has none of its own; it compares against the commit where the branch left `main`.

`new-task` records the task's baseline commit. Commits during the task keep that baseline. A first test run records it too when none exists. Without intent rules, a check prints:

```text
FlowGuard 5.0 (since 99f025e): 0 red; 0.2 s
```

## Daily use

1. Start the task with `python -m flowguard new-task` and read the brief.
2. Run the project's ordinary tests and read the FlowGuard block after the runner's summary. Its first line counts each kind, and says when a pytest run ended before its selected tests had all run (`run ended early (exit 3): 2 of 3 selected tests ran, the rest not checked`). Only `red` fails the run: your change broke a recorded agreement, so fix the code. `before` and `known` were there before the task: after `->` each line says what is known and who decides, and you choose when to raise an open question with the owner. `changed` means a function returns something else for an input a test used: say so if you meant it; a dict result names the keys that changed (`now adds demandPeriodConvention='legacy-half-open' (3 other keys equal)`). `impact` and `not compared` are not failures; `not compared` is unverified, not success, and a vitest run whose map checks did not report says so on a `not compared` line of its own. `python -m flowguard show --last` prints every line of the last run with its details: one last run per vitest package and one for pytest, `check` and `check --static`, with pytest's own exit and failed count, and the failed tests the brief counts.
3. Use `python -m flowguard show "what it decides"` to inspect a named function, model, field or agreement before changing another copy; a name the map does not know says so. For a field of a Python class, `show Settings.appearance` lists its writes and the functions that read it through `self`, an annotated name or a declared field (asdict and vars of it too), which an `impact` line counts (`5 readers (untyped reads not counted)`): a read through a name nothing types is not counted. A field this change stopped writing lists the writes and reads of the task start that no function has now.

Agents that work at the same time use one git worktree each (`git worktree add ../task-b`, then `python -m flowguard new-task` there): each worktree has its own `.flowguard/cache`, task baseline and change set. Agents in one working tree share them: one agent's `new-task` moves every agent's baseline, and each agent's uncommitted edits are part of the others' change.

## Record an agreement

Use `#` in Python and `//` in TS/JS. Mark every necessary copy with `same NAME`; add `ref` to the reference copy when one has been chosen:

```python
# flowguard: same ROUND ref
def round_amount(value: float) -> int:
    return round(value)

# flowguard: same ROUND
def preview_amount(value: float) -> int:
    return round(value)
```

Data agreements have separate comments:

```python
# flowguard: together Booking.employee_id Booking.unit_id on=update
# flowguard: writers Booking.employee_id reserve,release
```

`together A B,C` is directional: an operation writing A must also write B and C. `on=` limits it to `create` or `update`; `B=value` requires that value, and a bool or null is the same value in either language's spelling (`=true` and `=True`, `=false` and `=False`, `=null` and `=None`). Each name of a Python tuple or list assignment (`self.a, self.b = ...`, nested and starred ones too) and of a `for` or `with ... as` target is a write of its own. `together` checks which fields one write holds, and `B=value` one fixed value; a value that depends on a condition (both fields null when the manager is missing) is a test's job, and `0 red` says nothing about it. Bare writer names refer only to the comment's file; another file uses a repository-relative position such as `src/store.py:reserve`. An exception is written `except=path:function(reason)`; adding one loosens the agreement, which is the owner's decision. Do not weaken an agreement to clear a finding.

FlowGuard 5.0 removed the 4.2 comment spellings (`sensor NAME`, `owner NAME`, `owner A with=...`, `alone=`, `owner A writers=...`): each is red at its line, and the red names the 4.3 comment to write instead.

## Rules and fallback reasons

An independent rule in `tests/intent/` states an expected answer and cites its source. Store the owner's actual words once, byte for byte, with `python -m flowguard req add <file|-> --id R1`. A document source quotes an exact sentence from a file listed in `authority_docs`. Never store an AI plan as the owner's words.

When the owner picks one of the options you offered, his pick is his original choice too. Store his reply with the options: `python -m flowguard req add reply.md --id R2 --offer options.md --picked "A. Keep one version"`. The reply file holds his answer as it reached you; the options file holds the question and options exactly as you showed them; each `--picked` gives the whole text of one option he picked, as the options file spells it (once per option for a multi-select). Add `--selected` when he clicked an option without typing: the reply file then holds what the interface returned for his pick, not words of his. The options are kept as the agent's words in `.flowguard/requests/offers/`, never as his. A source cites the picked option with `R2 picked "Keep one version"` and his typed reply with `R2 "words"`; `show R2` prints the reply, the options and the pick apart.

`.flowguard/rules.toml` keeps the owner's current rules, each one line of text with a source that quotes the stored words or a document sentence exactly. `.flowguard/known.toml` keeps what is not settled and how to treat it: `act = "ask"` for a question only the owner can answer, `leave` for a problem left as it is on purpose, `fix` for a plain error to fix when its code changes, `ignore` for a false structure finding. `python -m flowguard known add FINDING --act leave --why TEXT` writes an entry from the places of a finding the last run reported (`show --last` names each finding). Whether same-named functions that resemble each other must stay separate, as a build script that must not import the app, is the owner's decision: a copies line says how they resemble and names `known add copies:NAME --act ignore --why TEXT`, which records every copy's site and takes the finding out of the brief's count; `show --last` adds each copy's signature and callers and the first line where they differ. `python -m flowguard show rules` lists both, and the `new-task` brief shows the first of them; `show NAME` and `show PATH` begin with the entries, rules and flowguard comment agreements that concern that name, file or folder.

`.flowguard/ledger.toml` records exception handlers that can finish without raising, with their count, reason and written rule. `python -m flowguard ledger init` records existing handlers; `python -m flowguard ledger check` checks the ledger. A finding names the forms that cannot be listed.

The executable two-copy rule example and supported context annotations are in the [local reference](./.agents/skills/flowguard/reference.md).

## Documents tied to code

Put `<!-- flowguard: about path:symbol -->` (or a file's path) above a Markdown text that describes code. When a change edits that code and not the text, the run names the text with an `impact` line. The site may be any file of the repository, a data file or a checked-in generated one too: a ZIP or JSON file holds no marker, so list the generated files in a Markdown text, each under markers for the function that produces it and for each file it is made from (markers stacked above one line all describe that line), with the command that regenerates it; a data file a function reads goes under a marker for itself and one for that function. A change to such a file (`src/app/resources/model.json`, `docs/manual.txt`) then names its line, in pytest as in `check --static`. A text about a file or `folder/` is that module's contract: a change to a function it calls, or that calls it, names it too while the call is there (that a route calls its owner function is a test's job: a change in another file that removes its call into the module names nothing), and `python -m flowguard show PATH` lists a module's contracts and connections; `show NAME` of a function or constant, and `show` of a document, list the texts and markers that tie them; a marker counts only where `check --static` resolves its site to that name, and a generated region that lists a file's functions or constants, or a model's fields, describes them too. A list the code already holds goes between `<!-- flowguard: generate fields Model -->` (or `values NAME`, `functions path`, `constants path`) and `<!-- flowguard: end -->`; `python -m flowguard docs` writes it. A region holds only what the map knows; prose such as a Purpose column stays outside it. `python -m flowguard show Model.field` (or its `table.column`) begins with how the Prisma schemas, SQL files and zod schemas declare the field, the field's own zod schemas first (each belongs to the longest model name its camel-case words hold); trust that over a document's table.

## Other checks and languages

Use `python -m flowguard check --static` for checks without running tests; it checks the sources that rules and known entries quote too, so they need no long suite, and `python -m flowguard show rules` says whether each source holds. Add `--all` to inspect the complete structure listing. `python -m flowguard check` runs affected rules and tests. Existing deep checks and finite flows are frozen; they are not part of the ordinary setup above.

The base installation reads Python. Install `flowguard[languages]` for TS/JS, Prisma, SQL and the frozen C/C++/C# readers. Vitest with ESM supports execution observations; Jest runs static checks. A function that cannot run in the closed comparison after the tests is `not compared`, with its reason, and so is a call its task-start version would take as other parameters (a required parameter inserted first); a trailing parameter added with a default keeps the call compared. Same-name copies that take different parameters are one red as such, naming each copy's parameters and declared return type: check whether they are copies of one decision. JS/TS copies, or Python copies with value-type annotations, are that one red in `check --static` (and so in pytest and vitest); unannotated Python copies are compared when pytest runs them. It is `before` where every copy is the same copy as at the task start: the same file (or its Git rename), the same function name, and the same parameter names and mapping under a mark of that name, whatever else the change edits in their files; writing `ref` on a mark does not make the copy new. Any other change makes it red, for example a parameter added or renamed, a mark written on another function, a function renamed or a file moved without Git, and so does a run without a baseline. A rule bound to their anchor follows the same judgement. A Python copy can map its parameter names (`same NAME(days=overdue_days)`); a TS/JS comment names no parameters, and TS/JS copies are compared by position. Agreement on tested inputs does not prove the intended business answer.

A SQL file kept in the repository, such as a database package installed by hand, describes the tables it creates and is compared with the Prisma schema; one that only alters a table describes none. A description left out of date on purpose is recorded by naming a table of one of its files: `python -m flowguard known add columns:prisma/migrations/~prisma/schema.prisma --site prisma/migrations/20240101_init/migration.sql:central_employees --act leave --why TEXT`.

A file listed in `[tool.flowguard] exclude = ["translations/*.ts"]` (paths from the project root, `**` across folders) is never read, at the task start either, and its reader need not be installed; a change that adds one to the list makes each agreement it held a `loosened` line, and a baseline pyproject.toml that does not parse, or whose `exclude` there has another type (`exclude = 5`), makes those files one `not compared` line. Every reader of the baseline's pyproject.toml judges only the keys it reads, never with a traceback: a baseline `authority_docs` that cannot be read leaves a document source `not compared`, and the project's own such file is refused with its text, which names the file. An included file whose reader is not installed stops `check --static` with its error (exit 2) and is one red `map checks` line after pytest's own summary.

FlowGuard acts only inside test runs. It never runs a function a second time inside a test, and builds, the dev server and production never load it. A source file saved during a run, by another agent or by a test, has its functions recorded no further: they are `not compared`, and every test runs as without FlowGuard. Several runs may share one repository at once, such as the checks of two packages or a vitest run beside `check --static`: each waits only for another's short write to the cache, and says so on stderr after 5 s; a vitest run says it in its first line (`waited 9 s for .flowguard/cache/map.sqlite`).

## Compatibility and repository

Retained older inputs and APIs continue to work; a feature 5.0 removed is refused with the step to its replacement rather than silently changing its meaning, and so is a top-level command of FlowGuard 0.70 to 1.4: `flowguard: read was removed in 1.0 -> python -m flowguard show "words"`, exit 2. See the [4.1 notes](./docs/upgrade-4.1.md), [4.2 notes](./docs/upgrade-4.2.md), [4.3 notes](./docs/upgrade-4.3.md), [5.0 notes](./docs/upgrade-5.0.md) and [intent guide](./docs/intent-guide.md) for existing contracts.

- `flowguard/structure/`: source facts and fixed queries.
- `flowguard/intent/`: agreements, intent rules, the ledger and test adapters.
- `flowguard/map/`: shared readers and immutable owner-word archives.
- `.agents/skills/flowguard/`: the single public skill and its local reference.
- `tests/`: ordinary tests and the project's own rules.

License: MIT
