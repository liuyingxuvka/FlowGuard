# Field notes: PEMEL Aging Studio, round 4 (FlowGuard 5.1.0)

Date: 2026-11-28. The FlowGuard root is the app folder. The lead ran `new-task` once (baseline 288a3e8). Six agents then worked in one tree at the same time:
- two UI lanes that changed code in sequence: Home and navigation, then the project tree and the figure window;
- one lane that changed the figure style;
- three lanes that wrote documents only.

Each point was tested against "What it is for". Points marked *checked in source* were traced in the 5.1.0 code; the others are observations with their command and output.

## Where it helped

1. **The ledger followed a move.** Five fallback handlers moved from `dialogs/projects.py` to `shell/home.py`, and the focused run said exactly that:
   - `red: ledger: Code disappeared: ledger entry "…:BaseException" records 1 handlers, but none remain`;
   - `python -m flowguard ledger check` named the key to remove.

   Writing the new entries made the agent restate each reason.
2. **An about-marker sent an agent to the right document.** `impact: docs/ARCHITECTURE.md:232 describes …figure_rendering.py, whose … calls figures/__init__.py:figure_svg, which this change edits -> reread that text`. The agent corrected that paragraph; without the marker nobody would have looked at it.
3. **Impact lines confirmed a removal.** `impact: ProjectTree.__init__ no longer writes ProjectTree.outside_valid_range; 0 other writers, 0 readers` confirmed that no reader was left, so the old route was gone.
4. **`show <module path>` gave the blast radius.** `show src/pemel_service/figures/__init__.py` (18.5 s) listed every caller of the figure owner before a layout change. `show next_cue` named the cue owner's one caller.

## Where it fell short of its own purpose

1. **The pytest plugin crashed and ended the run** (*checked in source*).
   - Command: `pytest tests/studio/commands/test_registry_contracts.py`, after one entry was removed from the shortcut list in `MainWindow`.
   - Output: `INTERNALERROR> ValueError: <Token var=<ContextVar name='flowguard_transport_code'…> was created in a different Context`, then `run ended early (exit 3): 60 of 77 selected tests ran`.
   - Source: `intent/sites.py` sets and resets `_TRANSPORT` and `_INSTALLED` with tokens inside generator context managers (lines 55–59 and 497–505). The intercepted method connects Qt callbacks that run later from the event loop inside `qtbot.waitSignal`, so the exit can happen in a different `Context`, and `ContextVar.reset` then raises.
   - A crash in the checker should not end the product's test run. It could report the function as "not compared" and go on.
   - With the plugin off (`-o addopts=-ra`) the same tests pass.
   - Also: `-p no:flowguard` does not turn the plugin off here, because it is loaded as `-p flowguard.intent.plugin` in `addopts`. Only `-o addopts=-ra` works, and the brief does not say so.
2. **A full run with a moved code base became very slow.** With the baseline 28 commits back, the full suite reached 16 % in about 25 minutes, against about 20 minutes for the whole suite at the baseline commit. The lead stopped it and ran the suite without the plugin. *Observed; the time was not profiled.*
3. **The block does not separate several agents' work.**
   - All 11 `red` lines in one agent's run were another agent's unfinished ledger work: `ledger: Code disappeared: …dialogs/projects.py…` and `New unregistered fallback: home.py:290`.
   - The block compares the working tree with the baseline. In a shared tree every agent sees every other agent's red and impact lines and must sort them by path by hand.
   - Suggestion: a filter for files in the agent's own diff, or a per-line path prefix that can be grepped.
4. **An intended return change was invisible.**
   - The public `figure_size` changed for every kind on purpose: 773 × 480 became 658 × 278 px.
   - The block said only `not compared: figure_size (…style.py:335)`, with reasons `uses attribute plot_sizes` and `no comparable JSON result`.
   - The function returns a tuple of two ints. A `changed` line, or "new body, not compared", would make an intended visual change visible to the reviewer.
   - New functions and not-comparable functions share one wording.
5. **A changed stylesheet was not compared.** `not compared: stylesheet (theme/__init__.py:250) (uses unavailable binding normalize_appearance)`. The string changed on purpose, so a regression there would pass silently too.
6. **A real copy went unrecorded.** The project list existed twice with two sources: a dialog read the workspace index, and the start panel read `settings.recent_projects`. That divergence is the owner's bug "dead recent entries". No `same` mark existed, and `check --static` has no hint for two widgets listing one domain collection from different stores.
7. **`show` output was dominated by aliases or word matches.**
   - `show "project stack"` printed 40 alias lines and none of the owners.
   - `show reopen_last` did not find the dataclass field default.
   - `show UI_HINTING` did not find the constant or its two uses.
   - `show EMPTY_LABELS` listed 9 unrelated `*_LABELS` aliases first.
   - `show "pemel_studio.commands.rules:simulations"` said "called by no function": the real caller dispatches through a dict.
   - `show crossover_level_factor` returned only noise.
8. **Documents outside the root cannot be tied to code.** Meeting material in a sibling folder copies equations and parameter roles from the manual and the code. `show` on such a path gave unrelated matches and did not say that the path is outside the root.

## What it cost

- Small focused runs: the block took 11–13 s on 14–19 s of pytest, which roughly doubles them.
- A 683-test run: 44.9 s of 196.7 s (23 %).
- A 391-test run: 47.3 s.
- `show` took 0.8–18.5 s and printed 40–70 lines per phrase query.

## Follow-up: full baseline verification

The exact baseline was checked in three serial, fresh pytest processes. The collected node lists were compared as a multiset: together they covered all 3,951 nodes exactly once. The final pytest summaries were 230 passed, 1,018 passed, and 2,681 passed plus 22 unverified intent probes. All exited 0 and FlowGuard reported zero red. Keep the unverified count distinct from passed tests.

- **Good diagnostic for shared worktrees.** An agent wrote a separate source file during a focused pytest collection. FlowGuard reported `project source changed during pytest verification; start a fresh verification process` and refused to run. The participating agents stopped all writes before the retry. In `intent/imports.py:prepare`, the finder re-hashes loaded application files and prevents reusing a host or active cohort after a change. This prevents an apparently successful test from claiming to verify a mixture of two source snapshots. The diagnostic could list the first few changed paths, which the code already computes, before suggesting a fresh process.
- **An exact locator works better than a dotted name.** `show src/pemel_studio/documents/figure_rendering.py:_svg_key` gave the architecture section, exact signature and one caller. `show pemel_studio.documents.figure_rendering._svg_key` fell back to word matching and reported 3,375 further lines, 3,341 sharing a word only. In `intent/cli.py:show` the exact graph-node path returns before ranking broader candidates. For a dotted Python function spelling that almost matches, a hint using the supported `path:symbol` form would make the existing capability easier to discover.
- **A decorated-case marker affected unrelated intent flows.** The test for portable executable source paths passed its ordinary assertions, but `show --last --full` repeated `test_export_implementation_members_live_in_the_outer_packages: runtime source position does not identify one anchor` under seven flows. In `intent/flow.py:_callback` an event anchor is only selected when `anchor.line <= frame.f_code.co_firstlineno <= anchor.target_line`. Python reported that decorated function's first source line as 47; its marker was at line 57, between the closing decorator and `def`. The project fix moves the same marker above the decorator and leaves the test and owner rule intact. FlowGuard could detect this placement statically, print the actual source positions, and attribute the issue to the affected case rather than repeating it under unrelated flows.
- **Keep the difference between a refusal and a failed behavioral test visible.** The complete remainder of the suite said `not compared: RECORD_PASSES … uses attribute ceil` for a calculation that the ordinary `test_record_passes_copies_agree` checked directly. The isolated evaluator in `intent/runtime.py` refuses unsupported attribute resolution. The line is helpful as a scope limit; listing the passing ordinary regression next to it when the link is known would reduce manual searches. No evaluator restriction or project agreement was loosened.
- **Separate a native failure from a suspected checker failure.** An earlier, single-process exhaustive run stopped in native Qt during a global stylesheet refresh. Both variants of the triggering test later passed alone, and the entire documents group passed with FlowGuard enabled. There is no evidence that FlowGuard caused that native crash. Preserve the full collection, isolate test processes if needed, and report separately which intent probes were actually verified.

## Follow-up: PDF naming and stack editing

- Exact `show` queries for `report_request` and `start_export_task` identified the shared export entry points and the publication closure. The new PDF naming rule uses the same report-subject resolution as worker serialization. Portable filenames still use the earlier R38 owner. The rule's scope excludes localized PDFs as the new product specification requires, and the prior source quotation and tests stay intact.
- `show src/pemel_studio/dialogs/forms.py:ReportPdfDialog._browse` located the only remaining inference of file-replacement confirmation from file existence. The verified implementation asks once at the existing workflow and publishes an unconfirmed file exclusively. The later FlowGuard impact lines named both removed `overwrite_confirmed` writers and found zero remaining readers. This matched source review and the late-collision regression.
- An independent check of the newly reachable stack editor found a pre-existing edit that rounded fields the user did not touch. The actual dialog edit regression now checks that an unchanged area and a default flag stay exact. FlowGuard's resulting impact line identified the new `StackDialog._original` field and its two readers. A regular pytest assertion checks the value and the flag.
- The C2 tests ran from a frozen, detached source snapshot while another report area was still being edited. Its final annotated suite had 77 passed, no failed tests and zero red findings. The checkout copies were compared byte for byte before committing. There were three expected impact lines and 14 comparison limitations, with no unexpected `changed` result. The tool's snapshot refusal in the shared checkout was useful protection; moving this verification to a separate working directory let development continue.

## Follow-up: report figures and saved evidence

- The integrated report check passed 555 tests. FlowGuard reported zero red,
  15 impact lines and 110 comparison limits in 73.6 s, with no `changed`
  lines. The field lines named the new calibration scan and band aggregators
  and their readers. The architecture impact led to updating the SVG cache
  description to include the screen/page frame in its key. Ordinary tests
  separately verified actual rendering and archival data limits.
- An exact locator can fail **after** displaying the correct signature and
  caller. `python -m flowguard show src/pemel_studio/documents/figure_window.py:FigureWindow._fit_to_screen`
  printed the method and the `FigureWindow.__init__` caller, then exited 2
  with `max() iterable argument is empty`. Calling the same `show` API without
  the CLI's graceful exception formatting produced a traceback through
  `intent/cli.py:1349`, `structure/api.py:1694`, and
  `structure/homes.py:201`. The old-group path can carry an empty parsed
  `sigs` set from `site_history`; `site_homes` assumes each group is nonempty
  when it computes `max(weight(t) for t in g["sigs"])`. The current-site
  collector filters empty sets. Apply the same eligibility check to historical
  groups and keep the already valid locator and caller information if the
  optional copy search cannot proceed. A useful regression would seed a
  historical empty signature set and call the ordinary exact-locator CLI.

## Follow-up: calibration setup and worker lifetime

- The setup tests verified the two activation rows, unchanged saved choices,
  exclusive selections, and an information control exercised by click and
  keyboard focus. All 254 ordinary assertions passed with zero red findings.
  The Qt tests and screenshots provide the visual evidence. `show` resolved
  `describe_prescribed_coverage` to its exact definition and `refresh_summary`
  caller, then printed 76 approximate lines. The exact setup information
  method also found its direct caller before listing 782 word-only matches.
  Keeping approximate expansion out of the default exact view would preserve
  the useful owner/caller result in a compact form.
- The first worker-lifetime run passed all 225 ordinary tests but correctly
  exited 1. `ledger check` pointed to two stale entries on
  `CalibrationJobStore.launch`: `BaseException` and `suppress(OSError)`.
  Source review showed that the new grant/reap path always raises a failed
  launch and has no best-effort observation write. Removing just those two
  obsolete entries made `ledger check` clean. The same 225 tests then passed
  with exit 0 and no red. Keep showing the removed site and the exit code even
  when the ordinary assertion count is green.
- The final `show --last --full` reported `_desktop_worker` writers and
  readers on `launch`, `stop_for_exit`, `has_desktop_worker` and construction.
  These pointers helped check that the app's process handle belongs to one
  owner. The exact stop, attach refusal and crash behavior were verified
  separately by subprocess tests. A previously decided aging-fit advisory
  remained `known`; the lifetime change did not alter that numerical choice.

## Follow-up: interrupted import and source stack review

- The import publication fix passed 157 targeted tests. The separate import
  review fix passed 262. Both exited 0 with zero red findings. The C7 lookup
  of `start_import.perform_import` located the direct caller in the existing
  confirmation workflow. The retry tests confirm that a library item already
  saved is kept and can be added to the project without importing it again.
- The C6 impact result listed `_geometry_origin` writers in the initializer,
  `_mark_geometry_edited` and `_set_geometry`, and the reader `_paint_geometry`.
  In the actual widget review, an invalid manual edit had left the original
  number labelled as manually entered. The fixed widget shows the validation
  error inline, with an ordinary Qt test asserting the incorrect value is
  absent. `intent/ledger.py:fallbacks` and `check` verify the exception's
  scope and named written rule. The widget test supplies the visual behavior
  evidence.
- `show --last --full` described `_scan_time_span` as `not compared: not a
  module-level function`. The refusal in `intent/runtime.py` is an explicit
  evaluator boundary. A path to the applicable ordinary Qt test in that
  output, if the mapping is known, would make it easier to distinguish a
  checked UI state from an uncovered one.

## Follow-up: saved comparison evidence

- Exact `show` on `common_curves` listed the request builder and the report
  reader. `show` also confirmed that the superseded curve parser had no
  remaining resolved call. The regression preserves original saved current
  grids at matching conditions. The worker still uses an exact shared grid
  for newly computed common-condition curves.
- `ledger check` identified the three new non-propagating handlers by the
  precise command or nested publication function. The reviewed entries name
  the displayed error and the exact saved-result check that may accept an
  uncertain write. A later check found zero red. In the separate actual
  adapter tests, all five passed, including exact saved states at a second
  condition without a time replay and rejection of a changed endpoint.
- The 274-test comparison and UI suite passed with zero red and no `changed`.
  `field_impact` named the new member error's `selection_key` as having zero
  counted readers. The code reads `exc.selection_key` in `ComparisonDialog`
  after `isinstance(exc, ComparisonMemberError)`. `intent/owners.py` documents
  that the field query counts `self`, annotations and declared field types.
  Recognizing that simple local type narrowing would add a real reader edge.
  The ordinary Qt test checks that the refusal appears on the affected row.
- The verbose report printed 172 `no comparable JSON result` entries. The
  predicate in `intent/plugin.py` adds that note for a due comparison with
  no sample to compare. It is separate from the ordinary pytest outcome. An
  optional grouped view by reason and owner could make first-pass review
  faster while retaining one exact location for each unchecked point.

## Follow-up: case labels and individual rises

- `req add` preserved the UTF-8 source of both owner messages, and `show rules`
  displayed the two named rules. The request map reads the stored request
  bytes, and the strict source check resolves the quoted fragment at the
  selected commit. The exact owner wording stays in the project request
  files, with only the agreed behavior summarized here.
- `new-task` disclosed the new baseline and explicitly named the older range
  it would no longer compare. It also listed the count of tests that had not
  rerun since a failure. `show --last --full` named both tests, so we included
  them in the next suite instead of assuming the count was a current failure.
- The first expanded check had two ordinary failures and zero red findings.
  One was a genuine PDF continuation defect: the longer case label could wrap
  into two words and disappear on the following page. The other was an old
  test's unsplit activation row expectation. The revised suite passed all
  523 tests with zero red and no `changed` lines. Its three impacts led to
  reviewing the case-choice row, both reorder controls and the exact-state
  adapter's existing input contract. The 92 not-compared lines remain tool
  scope limits. The real comparison, PDF and click tests provide the evidence
  for these visible changes.

## Follow-up: managed project copies

- The targeted project, Home and workflow suite passed 362 tests with zero
  red and no `changed` lines. Project paths in these tests were temporary
  synthetic workspaces. The app opened a managed copy, kept the external
  original, and enforced the copy's exact deletion identity. The one-time
  settings upgrade reset project reopening.
- FlowGuard's field impact named the removed `Settings.recent_projects`
  writers and distinguished two baseline readers. A source check found that
  the remaining settings occurrences read the historical schema and remove
  the field during upgrade. `WorkspaceIndex.recent_projects` is a separate
  index query. Showing baseline-only and current readers separately would
  reduce follow-up when a field is retired. The existing wording and map
  already provided enough locations to verify the distinction manually.
- The document impact linked the project export adjustment to a description
  of shared staged-file publication. The staged PDF and calibration write
  contract still holds. The impact was a prompt to inspect a real dependency,
  with no need for a duplicate architecture note.

## Follow-up: time-point input and crossover documentation review

- The first time-point run reported zero FlowGuard red findings and had ordinary
  test failures. Saving a project tried to rewrite immutable, unchanged time
  points while walking numerical references. The two walkers now retain
  unchanged field values and continue to replace relocated references. The next
  focused run passed 227 tests, including save and reopen, exact rebasing,
  CSV and HDF5 agreement, and the editor's time-point rules. `show --last --full`
  included six reviewed impacts and no `changed` lines. The larger regression
  run is tracked independently.
- `ledger check` identified the relocated calibration-data filter and the
  editor's new validation handler. The first reuses the saved-record rejection
  rule. The second continues to show the time error in the existing preview.
  The reviewed ledger check reached zero red findings. This helped distinguish
  an intentional, visible invalid-input check from an unreported fallback.
- Exact `show` lookups for the model library listed their real callers before
  the shared-word section. The library-list query had 431 extra word-only hits
  out of 433 additional hits. `intent/cli.py` deliberately appends these below
  resolved matches using the ranking threshold. A concise exact-query mode could
  leave those word matches behind `--full` while preserving the caller and reader
  context. The exact callers helped distinguish opening a saved project from
  starting with a model library alone.

### Completed affected time-point run

- The broad run executed 1,524 tests. Pytest reported 1,514 passes and 10
  failures. The FlowGuard block reported 0 red, 6 impacts and 128 points not
  compared. `show --last --full` reported the pytest exit code and all ten
  failing nodes separately. The post-correction group passed 147 tests, with
  0 red, 6 impacts, 77 not compared and no `changed` lines. This was useful
  evidence that the agreement checks and test outcomes were separate.
- Verified against `flowguard/intent/plugin.py:session_outcome` and
  `flowguard/intent/cli.py:_run_lines`. The plugin records pytest's outcome,
  and the CLI renders it above the full report. The short terminal block still
  begins with agreement counts. A compact pointer to the failed-test count
  when ordinary pytest fails alongside zero red would reduce misreading in
  streamed agent logs. The full view already shows the correct information.
- The profile and data preview changes retained the immutable original
  source. One follow-up caught the static curve cache format and verified both
  cache versions through the same publication owner. Those format and
  four-language PDF checks were ordinary regressions and therefore were not
  expected from the recorded agreements.

## Follow-up: common tree status column

- The exact stored request bytes matched the request digest, and
  `show rules` resolved the quoted text. `show project_rows` identified the
  resolved caller `tree_snapshot`, and `show ProjectTreeDelegate` listed the
  delegate's fields. That was sufficient to split the state projection from
  drawing the existing status glyph.
- All 158 targeted tests passed with 0 red, five not compared and no
  `changed` lines. The unrecorded results were the GUI projection, aggregate
  progress and delegate calls. Separate native Qt synthetic captures at two
  widths validated the accessible status text and actual painted badges.
  The rule's holding source and the report's not-compared entries correctly
  describe different facts. No broader GUI coverage is implied by that
  report alone.

## Follow-up: short-pass axes and an interface call

- The short-pass figure checks passed 124 tests with 0 red, no `changed`
  lines and three report producers listed as not compared. The native Qt
  captures independently checked the four-second jump and the 300-second
  final point. The more informative boundary assertion came from the report
  tests and did not rely on a JSON replay of the figure-producing call.
- While locating the crossover owner, `show crossover_law` named the adapter
  and its protocol but reported no resolved caller for either. The service
  visibly calls `bindings.crossover_law` through the injected protocol; the
  interface import is guarded by `TYPE_CHECKING`. The wording in
  `flowguard/intent/cli.py` already qualifies the claim as resolved calls.
  Showing the statically attributable protocol call with a distinct confidence
  marker would help when using the map to check an adapter boundary.

## Follow-up: released model code and older project display

- The first packaged-candidate group reported 483 passes, nine failures and
  eleven unverified intent cases in a partial collection. FlowGuard reported
  zero red. The two field impacts led to checking the fitted evidence readers
  and the default model selection when a project is upgraded. The other
  default writers handle explicit model selection and deletion. The new
  writer replaces only the identity of the model converted during a project
  open. The final 274-test retry recorded 0 red, no `changed` lines, the same
  two reviewed impacts, and one unchanged owner-known item.
- An actual open-and-autosave test found a broken read-only model label for
  older projects. The code map exposed the factory lookup and installed-code
  check as distinct operations. Test results and source review established
  that display can recognize the exact historical record while it remains
  excluded from current execution. The independent tests retained the package,
  application installation and historical measurement evidence identity.
- `show` on a model-manual JSON source explicitly says that the map reads
  neither that file nor a Markdown document there. The existing limitation is
  honest. A link from the generated document contract to a JSON authoring
  path would help find the proper editing surface in projects that build
  their documentation from catalogues. Actual generator `--check` and
  manual tests continue to verify the files.
