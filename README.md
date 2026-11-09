# FlowGuard

<p align="center"><img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" /></p>

[中文说明](./README.zh-CN.md)

FlowGuard keeps a project consistent while a coding AI changes it. Type checkers, linters and tests check that one place is written correctly; FlowGuard checks what they cannot see across the project. It guards four things:

1. **One owner per decision or field.** A judgment or a piece of data has one owner. Other places call it, are registered copies locked to it, or are pointed out.
2. **The owner's rules run.** A rule written from the owner's own words is red when the code breaks it, and a lead appears when the requirement changed but the rule did not.
3. **New structural problems show up.** New fallback branches, values outside a declared set, writes outside an owner, a field written without its partner, deletes that leave children, diverging copies and new spellings of a label. Only what this change adds is reported; old problems stay in a listing you can read.
4. **Surprising behavior changes are told.** Where a call can be replayed safely, the old and new code are compared class by class.

It does not catch everything: requirements nobody wrote down, visual style, concurrency and external services are out of scope. Grey means unverified, never passed.

## Start

Install from this repository; the similarly named PyPI project is different. Python 3.11 or newer is required.

```bash
python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git"
cd your-project
python -m flowguard init
python -m pytest
```

`init` enables the pytest plugin, adds the collection sentinel, a CI fragment and three project rules. In a project with `package.json` it adds a vitest (or jest) test that runs `python -m flowguard check --static`, so the results appear in `npm test`; for vitest it also wires the execution side. Without rules, a check is quiet:

```text
FlowGuard check: no intent rules.
```

## What a test run ends with

After the tests, FlowGuard prints one block. Its title names the baseline commit of the task. Four kinds of lines follow, in this order: red, changes, leads, unverified. Every red is printed; changes, leads and unverified share at most ten lines; names and places are never shortened. Each red and each lead ends with the next step to copy: an owner comment, a ledger entry, the rule line to change, or a question for the owner. A grey test item is shown as `U` (`UNVERIFIED` with `-v`) and counted as `N unverified`, not as passed; the exit status is unchanged. A replay that the baseline code could still observe but the new code cannot is a lost observation and fails the run.

## The four things

### One owner, locked copies

Put `# flowguard: owner NAME` above the owner and `# flowguard: sensor NAME` above every copy that must agree; differing copies are red. A data owner lists who may write it and what must change with it:

```python
# flowguard: owner hires.reserved writers=shop.store:reserve with=hires.updated_at
```

`check` also runs look-alikes of each owner on its classes and groups them as copies, forked copies or similar code. Without any registration, a function this change touched that used to behave like others still unchanged gives a lead. `show "what it decides"` finds the existing owner before another one is written.

### Rules from the owner's words

A rule in `tests/intent/` states the expected answer independently of the code, keeps literal regression rows and cites its source: the owner's words, stored once and byte for byte with `python -m flowguard req add <file|-> --id R1`. Fields hidden in the context are read on the anchor with `fields name=expression`. When a constant changes from 14 to 21, a lead lists the rules and decisions still holding 14.

### New structural problems

`.flowguard/ledger.toml` lists every exception handler that can end without raising, with its count, its reason and the written rule it serves; `python -m flowguard ledger init` records the existing ones as legacy. A bare `except`, `except Exception`, `contextlib.suppress`, warning filters, an exit from `finally` and a truthy `__exit__` cannot be listed. Values written outside a declared set (`states`, enums, Prisma enums, SQL `CHECK`), writes outside a data owner and pair violations are red; deletes that leave children, columns one schema description lacks and new label spellings are leads. When a change touches an open structure problem, the output says to tell the owner; the owner's decision is recorded under `[structure]` and stops the reminder.

### Before and after

A changed function and every anchored point are replayed on their case classes with the baseline code swapped in. A guard refuses file, process, network and database writes before they happen; a refused, uncopyable or unseen call stays grey with its reason. A changed anchor whose fingerprint did not change reuses its last comparison.

## Languages

The base installation maps Python. Install `flowguard[languages]` for the other readers.

| source | what FlowGuard does |
| --- | --- |
| Python | Everything above, inside ordinary pytest |
| TS/TSX, JS/JSX | Static checks (map queries, Prisma writes, `catch` fallbacks, literals, declared sets, shapes) in `check --static` and `npm test`; with vitest (ESM) also the before/after comparison and same-name copies; jest runs the static part only |
| Prisma schema, SQL files | Models, tables, columns (`@map`, `@@map`, `[bracketed]`), relations with `onDelete`, `CHECK` sets |
| C, C++, C# | Frozen map readers: declarations, calls, assignments |

FlowGuard's core stays in Python; another language gets only the thin interface it needs.

## Daily commands

| command | purpose |
| --- | --- |
| `python -m pytest` | Run the tests and read the FlowGuard block. |
| `python -m flowguard` | A short brief that remembers this task's baseline commit. |
| `python -m flowguard show "what it decides"` | Find the owner, writers, readers, copies and rules. |
| `python -m flowguard check` | Recheck affected rules and tests; copy discovery runs here. |
| `python -m flowguard check --static` | Map checks without tests; exit 1 on red. |
| `python -m flowguard check --all --deep` | Everything, with probes and mutation checks, in CI. |
| `python -m flowguard ledger check` | List every difference between the ledger and the code. |
| `python -m flowguard try ACCEPT days=4` | Explore one input of an anchor in its real test context. |
| `python -m flowguard model draft PUBLISH` | Draft a small flow from recorded paths. |
| `python -m flowguard req list` | List the owner's stored words. |

## Boundaries and migration

Behavior is compared only in the contexts the tests reach, and the output names the test. Similar code and new spellings are leads, not proof. Consistent copies do not prove the intended answer; a rule with a source does. Version 4.1 keeps every 4.0 comment, rule and saved input; see [the 4.1 notes](./docs/upgrade-4.1.md) and the [intent guide](./docs/intent-guide.md).

## Repository

- `flowguard/structure/`: the code map and its fixed queries.
- `flowguard/intent/`: rules, anchors, the ledger, owners, the pytest plugin and the vitest side.
- `flowguard/map/`: shared readers and immutable owner records.
- `.agents/skills/flowguard/`: the single public skill.
- `tests/`: ordinary tests and the project's own rules.

License: MIT
