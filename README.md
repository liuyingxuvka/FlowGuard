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

`init` connects the project's tests, writes its FlowGuard rules block and adds a CI fragment. For a Vitest or Jest project, it also writes a static check test and reports which npm script runs it; Vitest gets the execution adapter. Use the project's ordinary test command after setup.

`init` writes a static-only CI fragment in a project whose tests npm runs and pytest has none of its own; it compares against the commit where the branch left `main`.

`new-task` records the task's baseline commit. Commits during the task keep that baseline. A first test run records it too when none exists. Without intent rules, a check prints:

```text
FlowGuard 4.3 (since 99f025e): 0 red; 0.2 s
```

## Daily use

1. Start the task with `python -m flowguard new-task` and read the brief.
2. Run the project's ordinary tests and read the FlowGuard block after the runner's summary. Red findings fail the run; changes, leads and unverified observations explain what was checked. Follow the next step, and tell the owner when the output asks you to. Grey is unverified, not success.
3. Use `python -m flowguard show "what it decides"` to inspect a named function, field or agreement before changing another copy.

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

`together A B,C` is directional: an operation writing A must also write B and C. `on=` limits it to `create` or `update`; `B=value` requires that value. Bare writer names refer only to the comment's file; another file uses a repository-relative position such as `src/store.py:reserve`. Exceptions use `except=path:function(reason)` and need the owner's agreement. Do not weaken an agreement to clear a finding.

The old comment spellings remain accepted with a deprecation notice. The internal registration and saved inputs keep their existing meaning.

## Rules and fallback reasons

An independent rule in `tests/intent/` states an expected answer and cites its source. Store the owner's actual words once, byte for byte, with `python -m flowguard req add <file|-> --id R1`. A document source quotes an exact sentence from a file listed in `authority_docs`. Never store an AI plan as the owner's words.

`.flowguard/ledger.toml` records exception handlers that can finish without raising, with their count, reason and written rule. `python -m flowguard ledger init` records existing handlers; `python -m flowguard ledger check` checks the ledger. A finding names the forms that cannot be listed.

The executable two-copy rule example and supported context annotations are in the [local reference](./.agents/skills/flowguard/reference.md).

## Other checks and languages

Use `python -m flowguard check --static` for checks without running tests, or add `--all` to inspect the complete structure listing. `python -m flowguard check` runs affected rules and tests. Existing deep checks and finite flows are frozen; they are not part of the ordinary setup above.

The base installation reads Python. Install `flowguard[languages]` for TS/JS, Prisma, SQL and the frozen C/C++/C# readers. Vitest with ESM supports execution observations; Jest runs static checks. Unavailable or unsupported observations stay unverified. Agreement on tested inputs does not prove the intended business answer.

## Compatibility and repository

Retained older inputs and APIs continue to work; deprecated features give a removal notice rather than silently changing their meaning. See the [4.1 notes](./docs/upgrade-4.1.md), [4.2 notes](./docs/upgrade-4.2.md) and [intent guide](./docs/intent-guide.md) for existing contracts.

- `flowguard/structure/`: source facts and fixed queries.
- `flowguard/intent/`: agreements, intent rules, the ledger and test adapters.
- `flowguard/map/`: shared readers and immutable owner-word archives.
- `.agents/skills/flowguard/`: the single public skill and its local reference.
- `tests/`: ordinary tests and the project's own rules.

License: MIT
