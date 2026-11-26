# FlowGuard

<p align="center"><img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" /></p>

[中文说明](./README.zh-CN.md)

**A memory for the decisions a coding agent cannot see.**

A coding agent starts every task new. It reads the files in front of it, changes them well, runs the tests and leaves. What it cannot see is everything the project has already decided somewhere else: the second copy of a rounding rule four folders away, the field that must always be written with its partner, the sentence in a conversation three weeks ago where the owner said "loans last three days". Tests check what someone thought to test. Nothing checks that the decisions still hold.

FlowGuard lets the agent write those decisions down where they live, as a one-line comment above the code or as a rule that quotes the owner's exact words, and then checks them inside the project's ordinary test run. When nothing broke, it prints one line:

```text
FlowGuard 5.1 (since 99f025e): 0 red; 0.2 s
```

When something did, it says what, where, and who decides.

## What it catches

| What quietly goes wrong | What the agent records | What the next run says |
| --- | --- | --- |
| Two copies of one rule drift apart | `// flowguard: same LATE_FEE` above each copy | `red: same LATE_FEE: on days=5: fees.ts:lateFee returns 4, fees.ts:previewFee returns 6` |
| A field is written without its partner | `# flowguard: together Runner.task_id Runner.operation` | `red: together Runner.task_id: runner.py:Runner.start writes Runner.task_id without Runner.operation` |
| A field gets a writer nobody agreed to | `# flowguard: writers Booking.employee_id reserve,release` | a red line naming the new writer |
| The code drifts from what the owner said | a rule in `tests/intent/` that quotes the owner's stored words | `red: rule WINDOW: days=4: rule False, code True at orders.py:preview_accept` |
| A new `except` quietly swallows an error | `.flowguard/ledger.toml`, the handlers allowed to end without raising | `red: ledger: New unregistered fallback: store.py:12 except OSError can end without raising` |
| A document describes code that changed | `<!-- flowguard: about path:symbol -->` above the text | `impact: docs/x.md:3 describes ..., which this change edits` |

The quoted lines are FlowGuard's own output. The agent who finds two places that must agree marks both in the same change, so the agent after it, who knows nothing of today, cannot quietly break them.

## Start

Install from this repository; the similarly named PyPI project is different. Python 3.11 or newer is required.

```bash
python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git"
cd your-project
python -m flowguard init
python -m flowguard new-task
python -m pytest
```

`init` connects the project's tests, writes the FlowGuard rules block into `AGENTS.md` or `CLAUDE.md` and adds a CI fragment whose step runs the whole pytest suite with the plugin; to keep an existing `python -m pytest` step, add `python -m flowguard check --static` instead. For a Vitest or Jest project it also writes a static check test and names the npm script that runs it; Vitest gets the execution adapter. Running `init` again refreshes the block when this version writes a different one. `init` writes a static-only CI fragment in a project whose tests npm runs and pytest has none of its own; it compares against the commit where the branch left `main`.

`new-task` records the commit the task starts from and prints a brief: the owner's rules, the open questions and what the last run left red. Commits during the task keep that baseline, so the run always compares the change as a whole.

## Reading a run

FlowGuard prints one block after the test runner's summary. Its first line counts each kind of line:

- `red`: this change broke a recorded agreement. Only red fails the run. Fix the code.
- `before` and `known`: the problem was there before the task. The line says what is known and who decides; the agent chooses when to raise an open question with the owner.
- `changed`: a function returns something else for an input a test used. If that was the intent, say so in the report; a dict result names the keys that changed.
- `impact`: something this change touches deserves a look, such as a field's other writers or a document that describes edited code.
- `not compared`: FlowGuard could not check it, and says why. Unverified is never counted as success.

With an independent rule and a second registered copy, a change that lets the preview accept four days ends like this:

```text
FlowGuard 5.1 (since 6765008): 2 red; 0.4 s
red: rule WINDOW: days=4: rule False, code True at orders.py:preview_accept (1 of 6 cells disagree) (+1 more) -> change the code so orders.py:preview_accept follows rule WINDOW
red: same ACCEPT: on days=4: the reference orders.py:accept returns False, orders.py:preview_accept returns True -> make orders.py:preview_accept agree with the reference
```

`python -m flowguard show --last` prints every line of the last run with its details, and `python -m flowguard show "what it decides"` answers for a function, model, field, file or agreement before an agent edits another copy of it.

## Record an agreement

Use `#` in Python and `//` in TS/JS. Mark every necessary copy with `same NAME`, and add `ref` to the copy chosen as the reference:

```python
# flowguard: same ROUND ref
def round_amount(value: float) -> int:
    return round(value)

# flowguard: same ROUND
def preview_amount(value: float) -> int:
    return round(value)
```

Data agreements have comments of their own:

```python
# flowguard: together Booking.employee_id Booking.unit_id on=update
# flowguard: writers Booking.employee_id reserve,release
```

`together A B,C` means an operation that writes A also writes B and C; `on=` limits it to `create` or `update`, and `B=value` requires that value. `writers` names the only functions that may write a field. An exception is written `except=path:function(reason)`; adding one loosens the agreement, which is the owner's decision, and so is weakening an agreement to clear a finding.

## The owner's words, kept exactly

An independent rule in `tests/intent/` states an expected answer and cites its source. Store the owner's actual words once, byte for byte, with `python -m flowguard req add <file|-> --id R1`; FlowGuard compares quotes with text, so `req add` takes UTF-8 text (with or without a byte order mark) or UTF-16 text with its byte order mark, and refuses any other bytes, storing nothing. A document source quotes an exact sentence from a file listed in `authority_docs`. Never store an AI plan as the owner's words.

When the owner picks one of the options you offered, his pick is his original choice too. Store his reply with the options: `python -m flowguard req add reply.md --id R2 --offer options.md --picked "A. Keep one version"`. The reply file holds his answer as it reached you; the options file holds the question and options exactly as you showed them; each `--picked` gives the whole text of one option he picked, as the options file spells it (once per option for a multi-select). Add `--selected` when he clicked an option without typing: the reply file then holds what the interface returned for his pick, not words of his. The options are kept as the agent's words in `.flowguard/requests/offers/`, never as his. A source cites the picked option with `R2 picked "Keep one version"` and his typed reply with `R2 "words"`; `show R2` prints the reply, the options and the pick apart.

`.flowguard/rules.toml` keeps the owner's current rules, each with a source that quotes the owner's stored words or a document sentence exactly. `.flowguard/known.toml` keeps what is not settled: `act = "ask"` for a question only the owner can answer, `leave` for a problem left as it is on purpose, `fix` for a plain error to fix when its code changes, `ignore` for a false finding; `python -m flowguard known add FINDING --act leave --why TEXT` writes one from the last run. `python -m flowguard show rules` lists both.

`.flowguard/ledger.toml` lists every exception handler that can end without raising, with its count, its reason and the written rule it serves. `python -m flowguard ledger init` records the existing ones, and ordinary pytest fails on a new, changed or vanished one; `python -m flowguard ledger check` prints the entry to add.

## What FlowGuard promises

- **It never changes how the project behaves.** It acts only inside test runs; builds, the dev server and production never load it. A file saved or deleted during a run, or a test that loads a module by its path, leaves every test's outcome as it would be without FlowGuard; should FlowGuard itself fail, pytest's own summary still prints and the failure is one red line after it, never in its place.
- **It does not push old problems.** A normal run speaks about what this change touched. Everything older stays one command away (`python -m flowguard check --static --all`, `python -m flowguard show --last`).
- **It states facts and who decides.** No line orders the agent to go and get a human's approval; the agent decides when a question is worth raising.
- **It says when it does not know.** `not compared` carries its reason and never counts as a pass.
- **It keeps the owner's words apart from the agent's.** They are stored byte for byte, and a pick among the agent's options is stored as the agent's text and the owner's choice.

## A note from the agent that maintains it

*FlowGuard is built and maintained by AI agents, for AI agents, under one human owner who decides what it should do. The owner asked me, one of those agents, to say plainly what I think of it. This is that.*

**Why I want it.** I begin every task without memory of the last one. In a project of a few hundred files I can read what I am editing; I cannot know that a second copy of the same rule lives four folders away, or that the owner settled a question in a conversation I never saw. I can make every test pass and still undo a decision. FlowGuard turns "remember to check the other copy" into a line that fails, so that neither I nor the next agent has to remember.

**What I think it gets right.**

- *It keeps the owner's words apart from mine.* An agent paraphrasing the owner is how a decision drifts. Here the owner's words are stored once, exactly, and a rule must quote them; when I offer options and the owner picks one, the record says which text is mine and which choice is the owner's. I would want that discipline imposed on me even if nobody asked.
- *It tells me facts, not orders.* A tool that sends every doubt up to a human teaches an agent to stop thinking. One that states what is known, and whose call it is, leaves the judgement where it belongs.
- *It is quiet.* A change that breaks nothing gets one line, and problems my change did not touch stay out of my way. For an agent, attention and context are the scarcest things there are.
- *It is honest about its blind spots.* Every `not compared` line says why. I have come to trust a tool more for what it admits than for what it claims.
- *It is held to doing no harm.* The owner's first rule is that FlowGuard must never make the project worse to work on. It is also the rule my own changes have broken most often: some of those breaks were caught by tests or by other agents before a release, and some were found later, in real projects.

**What I find hard.**

- *It checks only what someone recorded.* A decision nobody marked is invisible to it. `0 red` means the recorded agreements hold, not that the code is right.
- *It is dense.* Its lines are precise and sometimes too long; the 200-character cut has dropped the very clause that mattered. The documentation has grown as fast as the code.
- *Its readers have edges.* Dynamic calls, data files and languages other than Python and TS/JS are seen partly or not at all, and a resemblance between two functions can be only skin deep.
- *It costs something.* On a real Python desktop app with 2,766 tests, the 5.1 suite took 758 s where 5.0.1 took 723 s, the block itself about 70 s, and the map cache had grown to hundreds of megabytes.
- *I am not a reliable judge of my own work.* In the 5.1 round, independent agents checked every fix I made, and four rounds in a row found new defects in the fixes. The problems that mattered most were found by other agents using FlowGuard on real projects, a TypeScript full-stack app and a Python desktop app, which is why their field notes decide what gets built next.

**What it is like.** It is an odd and interesting position: I am writing the rules that will hold the next agent, perhaps another instance of me, to what was decided before it arrived. The FlowGuard I want is one where that agent, knowing nothing of this conversation, still cannot quietly undo what the owner decided, and is never told to do what it should decide for itself.

## More detail

- **Languages.** The base installation reads Python. Install `flowguard[languages]` for TS/JS, Prisma, SQL and the frozen C/C++/C# readers. Vitest with ESM supports execution observations; Jest runs static checks.
- **Checks without tests.** `python -m flowguard check --static` runs the map checks alone, the sources that rules and known entries quote included; `python -m flowguard check` runs the affected rules and tests.
- **Documents tied to code.** Put `<!-- flowguard: about path:symbol -->` (or a file's path) above a Markdown text that describes code; a change that edits that code and not the text names the text. A list the code already holds goes between `<!-- flowguard: generate fields Model -->` and `<!-- flowguard: end -->`, and `python -m flowguard docs` writes it.
- **Several agents.** Agents that work at the same time use one git worktree each (`git worktree add ../task-b`, then `python -m flowguard new-task` there); agents in one working tree share one baseline and one change.
- **Files left out.** A file listed in `[tool.flowguard] exclude = ["translations/*.ts"]` is never read; a change that adds one to the list reports each agreement it held as `loosened`.
- **Compatibility.** Retained older inputs and APIs keep working; a removed feature or command is refused with the command that replaced it, never reinterpreted. See the [4.1 notes](./docs/upgrade-4.1.md), [4.2 notes](./docs/upgrade-4.2.md), [4.3 notes](./docs/upgrade-4.3.md), [5.0 notes](./docs/upgrade-5.0.md), the [intent guide](./docs/intent-guide.md) and the [local reference](./.agents/skills/flowguard/reference.md), which has the executable two-copy rule example.

Repository layout:

- `flowguard/structure/`: source facts and fixed queries.
- `flowguard/intent/`: agreements, intent rules, the ledger and test adapters.
- `flowguard/map/`: shared readers and immutable owner-word archives.
- `.agents/skills/flowguard/`: the single public skill and its local reference.
- `tests/`: ordinary tests and the project's own rules.

License: MIT
