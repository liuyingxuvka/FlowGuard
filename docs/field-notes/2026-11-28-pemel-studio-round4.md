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
