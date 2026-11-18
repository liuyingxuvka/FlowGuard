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

The same approach covers two later failures. A simulation saved as stopped
still looked active to the workspace index because its accepted state set
lacked `stopped`. A zoomed chart also showed a negative measurement that
the overview masked because its bounded read skipped the observation mask.
The corrected regressions compare the stored terminal state after reopening
and require the same validity mask through overview and zoom. FlowGuard
could link those assertions to their expected consumers and show the
specific transition or read path that disagrees.

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

## High priority: make task handoffs point to the evidence they count

FlowGuard's task baseline helped us separate a completed Simulation change from
the next Comparison change. The final focused run on 5.0.1 passed 41 pytest
cases. FlowGuard reported zero red agreements, 38 impacts and 129 unavailable
comparisons in 14.5 seconds. The handoff then recorded a new baseline and
reported `6 still red: python -m flowguard show --last`. The stored last-run
result still contained the zero-red summary. All six items came from older
ordinary test readings, outside the focused run. One was a deliberately
deselected real-engine test. We kept the older failures as follow-up evidence.

The counts come from two stores. In `intent/cli.py`, `_brief` combines
`_brief_reds` from the retained readings with `_last_reds` from the most
recent result. `show_last` displays only that recent result. Give the two
counts distinct labels, and give each a route that shows exactly the items
counted. For retained failures, show the test ID, last observed outcome,
baseline or source identity when available, and whether the latest run
selected it. Keep the recently completed run's agreement outcome visible.
An interrupted run should carry its own completion status. A filtered run
should leave unselected outcomes historical, and a complete collection of
an edited file can retire removed test IDs.

A small regression fixture can reproduce the handoff without Qt. Record a
failed ordinary test, run a passing subset from a different file, make a
commit and call `new-task`. The brief should still point to the recorded
failure, under a historical label. Its advertised detail view should show the
failed test and state that this test was outside the last selection. Then
rerun it successfully or complete a collection with the old test ID removed,
and check that its current-failure count clears. Keep the original observation
available for audit.

## Next: check the boundary between opening a dialog and starting work

A native Comparison test clicked Run and held the first synthetic member
active. Its first assertion expected the data-import entry to turn off and
failed when the entry remained available. The desktop design intentionally
allows opening the dialog during an ordinary heavy task and refuses actions
that start another task. Calibration has a distinct rule that also refuses
opening the import dialog. The corrected assertion pairs the available entry
with refused worker admission and a refused independent simulation in the
same active-batch state.

Start with a small, opt-in acceptance pattern for existing intent tests.
Record the owning task state, boundary identifier, allow/refuse decision,
reason key and whether a new worker started. Bind opening the import dialog
and starting an import to separate anchors while keeping their shared
admission owner visible. A focused test should detect both over-blocking a
safe entry and admitting a second worker. The Qt test can retain ownership
of clicks and widgets. FlowGuard can report the exact boundary on which the
decision disagreed with the cited rule.

## Use measured report geometry as a small acceptance observation

The Comparison regression passed with the correct run keys, out-of-range
flag and five member results in memory. Review of actual Qt captures at the
approved client sizes found three presentation defects. A narrow swatch
column hid the run key, a wrapped name cut off the warning below it, and the
generic table height added a second scroll area that concealed the fifth row
in the full report capture. The comparison now measures the key and warning
and gives the document scroll ownership of all five rows. The capture checks
both widget bounds and the last row's rectangle against the table viewport.

Extend the optional artifact observation with a stable widget role, layout
profile, measured bounds and an asserted relationship. Existing tests can
supply an example such as 'final member row lies inside the table viewport'
for a view that assigns scrolling to the surrounding document. An independent
pixel review can still catch missing paint when those geometric relationships
hold. FlowGuard can bind the assertion and its reproduction route to the
layout owner. Keep capture and measurement in the Qt harness, and store only
small numeric observations and hashes in the agreement result.

## Observe the state that was accepted after a confirmation

The model picker and file import run a native confirmation between reading an
item and saving it. The Step 9 tests changed the active project, changed the
library, replaced a selected file, and changed the content behind an existing
revision during that interval. The tests verify that confirmation rechecks the
relevant identities and leaves both stores untouched on refusal. An ordinary
successful add and a repeat add have separate assertions for their effects.

FlowGuard can make this coverage visible through two named observation points
in the existing test. At review time, record opaque identities for the owner
and candidate. At confirmation, record which identities still match, whether
the write happened, and whether the target state was preserved. Reuse the same
check for modal dialogs and asynchronous document previews. Start with an
explicit opt-in helper and a synthetic paired test. The report can flag a
confirmed write after an identity change without needing paths, input bytes,
native event replay, or project contents.

## Make moved writes and unsupported observations easier to read

An affected run passed 276 pytest cases. FlowGuard reported zero red
agreements, five impacts and 42 unavailable comparisons in 24.2 seconds.
Two first impacts covered the same default-model update: writing the fields
moved from a public function into its new private helper. The linked readers
and other writers were useful to review. A single paired finding could show
both functions, the unchanged call path, and the additional callers now
sharing the helper. Retain the independent writer findings when the call
path cannot be established or the mutation moved across a condition.

The same run showed "calibration closure is unsupported" against ordinary
Qt dialog constructors. The observer means a Python function with free
variables in `intent/sites.py`. The wording confused that instrumentation
step with the application's own calibration. Describe the missing
observation in Python terms, and make the affected test and field easy
to identify. The ordinary pytest outcome can still be shown alongside it.

## Show what makes a copy finding actionable

A later desktop run passed 142 focused tests in 38.74 seconds. FlowGuard
spent 17.0 seconds and reported zero red agreements, 10 impacts and 88
unavailable comparisons. Its first impact grouped three private AST helpers.
Inspection confirmed that they walk the same assignment pattern. Their
failure text belongs to three different callers: a build script, the
application's reader for user-supplied model files, and its reader for an
installed resource. The finding led us to check whether the helpers could
share an owner. The one-line summary showed the matching names and paths,
but left the relevant difference and package boundaries to manual inspection.

Keep the structural copy discovery. On demand, show the matched body regions,
the small differences, the known callers and whether all members have a legal
common import owner. Mark uncertainty when the package graph cannot establish
that. Give the summary lower urgency when it only establishes resemblance.
A recorded agreement or different results on a shared input would justify
stronger wording. An isolated build script and a runtime package are a useful
synthetic example for exercising the distinction.

## Let a bounded integration check carry its own evidence

In a separate presentation utility outside the instrumented application test
run, five synthetic checks passed before the first actual invocation failed
at its JSON reader: the caller used the wrong keyword for a size limit. The
failure occurred before the utility loaded its larger inputs. A sixth test
called the real reader with a tiny local JSON file and checked both the exact
bound and the rejected over-bound call. This caught the missing interface
coverage without a full run or access to the real inputs.

A focused check could distinguish a caller exercised against a fake from the
same caller exercised against the real bounded reader. Let teams bind that
existing test to the call boundary and show its exact test result alongside
the static finding. The observation can record the operation name, code
identity, input size category and outcome without retaining input content.
Keep this optional and bounded by the changed call; broad automatic execution
would add cost and could start operations that the task does not own.

## Check Cloud skill commands against the released CLI

The Cloud skill available in this session tells agents to start with
`python -m flowguard read` and to locate an owner with
`python -m flowguard read --find <words>`. The installed CLI identified itself
as 5.0.1, which was also the latest stable GitHub release at the time of the
check. `python -m flowguard read --find 'bounded validation'` returned exit 2:
the parser does not have a `read` command. Its help lists `show`, `check`,
`init`, `new-task`, `ledger`, `req`, `docs` and `known`. The developer could
proceed with the actual `new-task` and `show` commands after checking help.

Give the skill a CLI compatibility range and publish a small command index
from the same release metadata as the parser. A release test can extract each
recommended top-level command and flag from the skill's examples and verify
that CLI parsing accepts it with a synthetic local fixture. A Cloud wrapper
could report its own skill and CLI versions together before recommending
commands. Keep maintenance notes and copied skill bundles easy to identify
when they are older than the installed tool.

## Show an untyped integration boundary as a coverage gap

In the first installed-engine acceptance, the production adapter stopped
before any forward evaluation. The caller still used a private parameter
factory name from an older adapter. Its receiver was typed as `Any`, so the
normal type check could pass. The preceding 90 affected application tests had
passed, and FlowGuard reported zero red agreements, 32 impacts and 63
unavailable comparisons. Those tests covered the application callbacks and
synthetic state transitions. The failing call needed the actual installed
adapter. The repair switched both call sites to the current factory and used
the real adapter type at the two integration boundaries.

When a changed production call crosses an `Any` or dynamically loaded boundary,
show whether the callee could be resolved and whether a registered test used
the installed implementation. A small fixture can remove or rename a factory
while leaving a passing fake in the earlier test. The report should then point
to the unverified receiving type and the nearest existing smoke test. This
would help an agent choose one real call and avoid rerunning a large workload.

The Japanese GUI review also found a program-owned failure message with no
catalogue entry. Static agreement and ordinary test success covered a different
boundary. Teams could register a narrow link from message descriptor producers
to their existing catalogue checks. Preserve user-entered text as opaque. The
tool can flag a missing installed-language key without storing document content
or trying to translate it.

## Put the test result beside instrumentation coverage

An early global-window run exited with four failed tests and two fixture
teardown errors. FlowGuard appended "0 red, 28 impact, 94 not compared". That
line describes instrumented agreements. The ordinary pytest failures covered
native widget visibility, a return command, and synthetic fixtures that had
not met the normal persisted-input contract. The process exit and pytest
summary were the evidence for the failing test run.

Keep the independent counts and label them on the same line when the plugin
has both outcomes. For example, show "pytest failed: 4 failures, 2 errors"
next to "FlowGuard agreements: 0 red, 28 changed, 94 not compared". Save the
pytest exit classification with the reading identity so a later
`show --last` call can carry both. A two-test plugin fixture can reproduce
an unobserved ordinary failure with zero changed red agreements, then
assert that the final summary still identifies the run as failed.

## Observe queued GUI events after a successful command

A native Qt journey saved a new version of a generated record. The project
and library both held the correct version. The completion callback also
selected the new version and showed its report. The next queued focus event
went to a tree button, selected that button's group, and replaced the report.
The defect appeared after the command had returned. Checking only the write
and the first selection would have missed it.

A bounded diagnostic observed command entry and return, task-owner release,
the selected domain key, the current tree item, and the visible document key.
It also observed the first normal stable point after queued Qt events. The
app repair kept keyboard focus on the selected tree row. The same real
journey then kept all four selection identities aligned in English and
Japanese at both reviewed scales. The focused regression suite passed
18 tests.

Offer an opt-in pair of observations around an existing toolkit-specific
settle step. At the first point, record the command's stored identity and
the expected visible owner. At the second, record whether focus, navigation,
or a newer user action changed that owner. An example can reproduce this
with a tiny Qt tree and an embedded button. Keep data payloads and widget
contents out of the record. A conflicting user click should be visible in
the comparison so the tool does not confuse intentional navigation with a
queued callback that overrode the command.
