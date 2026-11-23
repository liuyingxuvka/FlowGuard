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
2. Run the project's ordinary tests and read the FlowGuard block after the runner's summary. Its first line counts each kind. Only `red` fails the run: your change broke a recorded agreement, so fix the code. `before` and `known` were there before the task: after `->` each line says what is known and who decides, and you choose when to raise an open question with the owner. `changed` means a function returns something else for an input a test used: say so if you meant it. `impact` and `not compared` are not failures; `not compared` is unverified, not success. `python -m flowguard show --last` prints every line of the last run with its details.
3. Use `python -m flowguard show "what it decides"` to inspect a named function, model, field or agreement before changing another copy; a name the map does not know says so.

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

`together A B,C` is directional: an operation writing A must also write B and C. `on=` limits it to `create` or `update`; `B=value` requires that value. Bare writer names refer only to the comment's file; another file uses a repository-relative position such as `src/store.py:reserve`. An exception is written `except=path:function(reason)`; adding one loosens the agreement, which is the owner's decision. Do not weaken an agreement to clear a finding.

FlowGuard 5.0 removed the 4.2 comment spellings (`sensor NAME`, `owner NAME`, `owner A with=...`, `alone=`, `owner A writers=...`): each is red at its line, and the red names the 4.3 comment to write instead.

## Rules and fallback reasons

An independent rule in `tests/intent/` states an expected answer and cites its source. Store the owner's actual words once, byte for byte, with `python -m flowguard req add <file|-> --id R1`. A document source quotes an exact sentence from a file listed in `authority_docs`. Never store an AI plan as the owner's words.

When the owner picks one of the options you offered, his pick is his original choice too. Store his reply with the options: `python -m flowguard req add reply.md --id R2 --offer options.md --picked "A. Keep one version"`. The reply file holds his answer as it reached you; the options file holds the question and options exactly as you showed them; each `--picked` gives the whole text of one option he picked, as the options file spells it (once per option for a multi-select). Add `--selected` when he clicked an option without typing. The options are kept as the agent's words in `.flowguard/requests/offers/`, never as his. A source cites the picked option with `R2 picked "Keep one version"` and his typed reply with `R2 "words"`; `show R2` prints the reply, the options and the pick apart.

`.flowguard/rules.toml` keeps the owner's current rules, each one line of text with a source that quotes the stored words or a document sentence exactly. `.flowguard/known.toml` keeps what is not settled and how to treat it: `act = "ask"` for a question only the owner can answer, `leave` for a problem left as it is on purpose, `fix` for a plain error to fix when its code changes, `ignore` for a false structure finding. `python -m flowguard known add FINDING --act leave --why TEXT` writes an entry from the places of a finding the last run reported (`show --last` names each finding). `python -m flowguard show rules` lists both, and the `new-task` brief shows the first of them; `show NAME` and `show PATH` begin with the entries, rules and flowguard comment agreements that concern that name, file or folder.

`.flowguard/ledger.toml` records exception handlers that can finish without raising, with their count, reason and written rule. `python -m flowguard ledger init` records existing handlers; `python -m flowguard ledger check` checks the ledger. A finding names the forms that cannot be listed.

The executable two-copy rule example and supported context annotations are in the [local reference](./.agents/skills/flowguard/reference.md).

## Documents tied to code

Put `<!-- flowguard: about path:symbol -->` (or a file's path) above a Markdown text that describes code. When a change edits that code and not the text, the run names the text with an `impact` line. A text about a file or `folder/` is that module's contract: a change to a function it calls, or that calls it, names it too, and `python -m flowguard show PATH` lists a module's contracts and connections; `show NAME` of a function or constant, and `show` of a document, list the texts and markers that tie them; a marker counts only where `check --static` resolves its site to that name, and a generated region that lists a file's functions or constants, or a model's fields, describes them too. A list the code already holds goes between `<!-- flowguard: generate fields Model -->` (or `values NAME`, `functions path`, `constants path`) and `<!-- flowguard: end -->`; `python -m flowguard docs` writes it. A region holds only what the map knows; prose such as a Purpose column stays outside it. `python -m flowguard show Model.field` (or its `table.column`) begins with how the Prisma schemas, SQL files and zod schemas declare the field, the field's own zod schemas first (each belongs to the longest model name its camel-case words hold); trust that over a document's table.

## Other checks and languages

Use `python -m flowguard check --static` for checks without running tests, or add `--all` to inspect the complete structure listing. `python -m flowguard check` runs affected rules and tests. Existing deep checks and finite flows are frozen; they are not part of the ordinary setup above.

The base installation reads Python. Install `flowguard[languages]` for TS/JS, Prisma, SQL and the frozen C/C++/C# readers. Vitest with ESM supports execution observations; Jest runs static checks. A function that cannot run in the closed comparison after the tests is `not compared`, with its reason. Agreement on tested inputs does not prove the intended business answer.

FlowGuard acts only inside test runs. It never runs a function a second time inside a test, and builds, the dev server and production never load it.

## Compatibility and repository

Retained older inputs and APIs continue to work; a feature 5.0 removed is refused with the step to its replacement rather than silently changing its meaning. See the [4.1 notes](./docs/upgrade-4.1.md), [4.2 notes](./docs/upgrade-4.2.md), [4.3 notes](./docs/upgrade-4.3.md), [5.0 notes](./docs/upgrade-5.0.md) and [intent guide](./docs/intent-guide.md) for existing contracts.

- `flowguard/structure/`: source facts and fixed queries.
- `flowguard/intent/`: agreements, intent rules, the ledger and test adapters.
- `flowguard/map/`: shared readers and immutable owner-word archives.
- `.agents/skills/flowguard/`: the single public skill and its local reference.
- `tests/`: ordinary tests and the project's own rules.

License: MIT
