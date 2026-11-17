# FlowGuard 5.0.1 in a Python desktop project

Observed on upstream `4807f259e07285c2a53afcd11a931a551641929e`. The project is a
Python/PySide6 application with a nested `pyproject.toml`. It runs ordinary pytest
with `-p flowguard.intent.plugin`. These notes include two failures reproduced
in a small synthetic repository and observations from application runs.

## High priority: baseline comparisons respect excluded files

Qt Linguist uses `.ts` for XML catalogues. Configure
`[tool.flowguard] exclude = ["translations/*.ts"]`, commit a file at
`translations/app.ts` containing `<TS version="2.1"></TS>`, and run
`python -m flowguard new-task`. Change the XML on disk and run
`python -m flowguard check --static` with the Python-only installation.

Actual result: exit 2, `translations/app.ts: typescript reader unavailable:
missing tree-sitter`. `show` on a Python symbol works because the current map
excludes the file. The pytest plugin can also raise `MapError` at session finish
and interrupt pytest's normal summary. Installing the readers made the Studio
run usable, but those XML files contain no TypeScript.

Expected: an excluded file is never supplied to the parser during that check.
Inspect `structure/api.py` `_file_deltas` and `_baseline_facts` together with the
current reader filters in `structure/store.py`. Test this with an excluded file
that differs from the recorded baseline and with the language extra absent.
Also test removal of an actual agreement after a file is excluded, so honoring
scope does not conceal an intentional weakening. If a genuinely included reader
is unavailable, report the affected comparison and preserve the ordinary test
outcome and diagnostics.

## High priority: Python destructuring writes participate in agreements

Put the following in `runner.py`, commit it and record a new task baseline.

```python
# flowguard: together Runner.task_id Runner.operation
class Runner:
    def __init__(self):
        self.task_id = ""
        self.operation = ""

    def start(self):
        self.task_id, self.operation = "id", "parse"
```

`show Runner.task_id` lists the constructor write and omits `start`. Change
`start` to `self.task_id, self.unrelated = "id", "parse"`.
`check --static` exits 0 with zero red findings. Changing the same body to
`self.task_id = "id"` exits 1 and reports the missing partner. Both outcomes
were reproduced on 5.0.1.

Expected: each assigned field in the tuple is recorded as a write in the same
operation. The valid tuple is accepted and the missing-partner variant is red.
A shared recursive target walker for tuple/list assignment targets would support
`together` and `writers` consistently. Test both outcomes and the `show` output.
The issue matters in an application that assigns and clears task identity,
operation and staging location together when handing work between processes.

## Make the test report easier to act on

Two local runs illustrate the timing. An early run of 426 checks took
145.79 s, including 91.7 s reported by FlowGuard. After the import regression
was corrected, 452 checks passed in 160.77 s. FlowGuard reported 98.1 s, zero
red findings, 30 impact findings and 201 unavailable comparisons. These are
observations from two different revisions of a mixed Qt and service suite.
A source-index and result-comparison timing breakdown would make a controlled
comparison easier to design.

Same-named private helpers in different modules accounted for some of the first
impact lines. For example, independent report section helpers with different
inputs and responsibilities were proposed as a copy to inspect. Such leads can
be useful, but a shared short name is weak evidence. Rank likely copies by shared
field names, signature, callers, and structural similarity, and keep weak matches
in the expanded view. Keep explicit agreements and actual red findings prominent.

The unverified count is helpful. Group it by reason, and give the developer a few
exact source sites and an action for each group directly in `show --last`. Qt
objects and filesystem transactions often cannot replay as JSON values in a
closed comparison. Show which agreement or behavior remains unverified despite a
passing ordinary test. An optional timings view split into source indexing,
observations, replay and reporting would identify where an incremental run spends
its time. Cache reusable analysis by the actual source and environment identities.
Preserve normal pytest assertions and comparisons rather than converting these
cases into exceptions to the rules.

## Connect native UI observations to code agreements

Two problems surfaced during actual desktop regression. An animation advanced
through 30-degree steps while its icon renderer accepted quarter turns. The next
timer tick passed 30 degrees to the renderer and raised inside the Qt paint
callback. The correction advances through the admitted set. A language change
also called the same flush used for leaving a page, which committed a title
being edited and stopped the pending Notes timer. The correction keeps the
existing edit buffer during presentation-only refresh. The focused regression
after these corrections passed 27 tests.

A finite-value agreement could cover the first case with little extra machinery.
The producer can name its state field and the consumer can name its admitted
values. The developer should be able to see the first reachable out-of-set
value, its write site and the call site. Start with explicitly declared small
enumerations and arithmetic transitions that can be exhausted. Report an
unresolved transition when a value comes from native code or arbitrary input.
This is an extension proposal based on the observed UI failure.

For native effects like the second case, accept small observations from the
project's existing tests. A Qt test can report whether a language refresh
retained the same editor, its pending buffer and timer. An action test can
report the command ID, task phase, enabled state, visible refusal reason and
resulting view. Let FlowGuard bind those observations to the changed code and
include the failing scenario in its summary. A desktop test already owns
widget construction, event delivery and screenshots. The map can consume its
bounded evidence and leave the test in charge of that behavior. Use stable
command IDs and state checks so a translated label or different desktop DPI
does not create a false code-change warning.

The development value here is having one place to find confirmed decisions and
check their actual writers during ordinary tests. The two reproduced fixes above
would make that workflow more reliable before adding wider review features.

## Keep application test failure visible beside agreement results

The subsequent simulation regression returned exit 1 with 12 failed and 246
passed tests. Its FlowGuard lines reported zero reds, 38 impacts and 189
unavailable comparisons. Six of the failures were on real Qt key delivery:
buttons and the context menu dispatched, while the keyboard step did not
reach the expected callback. Waiting for the active window and the focused
tree, and asserting `QShortcut.activated` separately from the command
dispatch, resolved those six failures in the next run.

When a FlowGuard summary is read on its own, preserve the scope of both
outcomes. Store the ordinary pytest exit state and completed test counts
beside the agreement counts, especially for interrupted and early-stop runs.
Link failed test IDs even when the agreement count is zero. For desktop
tests, named evidence at the input-delivery and command-admission boundaries
makes the same observation useful for refused commands: a key can be
delivered, the command can be correctly refused, and no task should start.

## Attach independent checks to generated artifacts

A Japanese report PDF rendered the heading `12,345 h` correctly on screen,
but three readers could not extract the number. A six-file Qt probe varied
the font shaping strategy and direct versus recorded painting. Both normal
painting paths lost digits from the text layer. Using the Qt style that
prefers unshaped glyphs where the script permits it preserved the digits
in both paths. The development regression now exercises mixed-script
running text and a numeric heading.

Add an optional way for an existing test to attach an artifact kind,
locale, observed property and verifier name to its result. For this case
the observed property is the exact numeric text recovered from PDF, and a
separate screenshot checks presentation. Attach a digest or a local
reference if the artifact is useful for inspection. Keep both the PDF
body and customer inputs out of the FlowGuard store. This would let one
agreement name the screen and export outcomes without making FlowGuard
render documents or interpret technical values.
