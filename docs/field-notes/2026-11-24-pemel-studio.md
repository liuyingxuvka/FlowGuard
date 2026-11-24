# PEMEL Studio field notes, 2026-11-24: the 5.1.0 candidate (main 4d72073c)

Before the v5.1.0 tag, we ran FlowGuard main `4d72073c` (`v5.0.1-39-g4d72073c`) on an isolated git worktree of PEMEL Studio (`ff98023`). It had its own `.flowguard/cache`, and the running project's 5.0.1 installation was left untouched.

The full studio suite passed with no local shim: `2766 passed, 1 skipped, 3 unverified`, FlowGuard block `0 red, 2 known fixed?, 5 not compared; 71.7 s`. The installed 5.0.1 on the same copy gave `0 red, 5 not compared; 64.6 s`.

The fixtures named below are small git repositories that compare the installed 5.0.1 with this build.

## Confirmed fixed on PEMEL Studio (with evidence)

The sources are the 2026-11-17 notes ("17") and the 2026-11-23 notes, morning ("23") and afternoon ("PM").

1. **Excluded `.ts` in the change set; shim needed (17 and 23 high priority; PEMEL17-1, 23-2a): fixed.**
   - The full suite and probe A pass without the shim.
   - Fixture `logs/22`: 5.0.1 gives `check --static exit=2, pytest exit=1` (`MapError: translations/app.ts: typescript reader unavailable`); 5.1 gives `exit=0`, `exit=0`.
2. **Newly excluded file loosens its agreement (PEMEL17-3, 23-2b): fixed.** Fixture: `loosened: same RATE removed from b.py:rate (its file is now excluded by [tool.flowguard] exclude) -> name it in your report; …`. The line appears with or without the old shim.
3. **An included file without its reader keeps pytest's outcome (PEMEL17-2): fixed.** Fixture: `1 passed`, then `red: map checks: app.ts: typescript reader unavailable: missing tree-sitter -> pip install "flowguard[languages] @ …", or list it in [tool.flowguard] exclude`, exit 1.
4. **A file saved during a run ends the session (23 high priority; 23-1a/b): fixed.** Fixture `logs/23`: a test rewrites the module shorter.
   - 5.0.1: `INTERNALERROR> OSError: lineno is out of bounds`, `2 passed`, block `0 red, 1 changed`, exit 3.
   - 5.1: `3 passed`, `not compared: area (source of app/geo.py changed on disk after import)`, exit 0.
   - With lines inserted above the function, 5.0.1 said `not a function definition`.
5. **"7 still red", failed tests counted as red (PM and 17 high priority; PEMELPM-9/10/11, 17-14): fixed.**
   - After the full suite the brief has no red line. Probe B shows a failed test named apart from reds.
   - Old cache (rows 16–17): the stale rows show as `6 red in the intent results`, listed in `show --last`, and are deleted by the first complete collection (`plugin.py:2428`).
6. **pytest's outcome beside the agreements (PEMEL17-12): fixed.** `pytest: exit 0, 0 failed` and `pytest: exit 1, 1 failed`.
7. **A writers agreement on a dataclass field can never hold (PM high priority; PEMELPM-238/254): fixed.** The default now reads `declares …`, and the `before` line is gone. Both `known.toml` entries (act = leave) read `known fixed?: known.dirty-field-default: writer:Project.dirty no longer found -> … remove known.dirty-field-default and say so in your report`.
8. **The field view misses writers: `TYPE_CHECKING`, `Any`, tuples, test doubles (PEMELPM-317/318/333, 17-4): fixed**, except writes through a call receiver.
   - `TYPE_CHECKING`: 5.1 now finds `controller.task_dialog = TaskDialog(…)` in `workflows/*.py` (grep confirms 11+ sites), hence the 4 new many-writer findings.
   - Test doubles: `test fixture (not held)`.
   - Tuples, fixture: `self.task_id, self.unrelated = …` gives 5.1 `red: together Runner.task_id: runner.py:Runner.start writes Runner.task_id without Runner.operation`; 5.0.1 gives `0 red`.
9. **Reads of `self.attr` counted as 0 readers; `show` lists no reads (23 and the 11-18 note; 23-5a/b): fixed.**
   - `show Controller._closing_window`: `reads … controller.py:700 Controller.request_close`.
   - `show PaneHandle.highlighted`: `read as an attribute by 1 function (untyped reads not counted): PaneHandle.paintEvent`.
10. **The sealed run blocks builtins beside a dataclass (PM high priority; PEMELPM-13/14): fixed.** Fixture: 5.0.1 `not compared: parse (parse.py:9) (uses unavailable binding int)`; 5.1 `changed: parse (parse.py:9): (x='1') was 2, now 3`.
11. **Ledger: 53 legacy entries cannot take a reason (PEMELPM-6/7): fixed.**
    - Probe 14 above.
    - Fixture: a short `reviewed` gives `reviewed has 3 words; at least 8 are required`. A reason and rule on `except Exception` gives the red plus `or, since ledger init recorded it, keep rule = "旧账" and state the review in reviewed = "why it may stay"`.
    - Of our 53: the 16 named `suppress` can be listed with a reason; the 37 others (18 `BaseException`, 17 `Exception`, 2 warning filters) can take `reviewed`.
12. **The copies step names no route; plurals (23-15a/b): fixed.**
    - Fixture: `… they resemble (structural similarity 1.00); keeping one implementation or marking each copy same LITERAL makes them agree; whether they must stay separate is the owner's decision; if they must: python -m flowguard known add copies:_literal --act ignore --why TEXT`.
    - `before` now reads `differed from its same-named copies at task start`.
13. **init: the CI fragment runs the suite twice; a reformatted sentinel blocks init (PEMELPM-15/16/17): fixed.** Fixture: after `ruff format` of the sentinel, 5.0.1 init gives `an existing test needs merging with the intent sentinel` (exit 2); 5.1 gives `Initialized …` (exit 0) and keeps the formatted file.
14. **The Cloud skill's `read` (PEMEL17-22): fixed.** `flowguard: read was removed in 1.0 -> python -m flowguard show "words"`, exit 2. `status` → `… which prints the brief`.
15. **Fixed by the CHANGELOG, not exercised here:** moved writes on one line (17-18); a file deleted during a run (PEMELPM-c1/c2); a test that loads a module by path (PEMELPM-d2; our suite, which has such tests, ran to completion); an aborted run marked as ended early (23-1c); stacked markers (23-11).
16. **Partly fixed:**
    - Copy findings (17-20): similarity, first difference and callers are given; no package-boundary ranking.
    - Generated and data files (23-11/12): a documented marker route (an `about` marker can name any file; pytest runs map checks on any mapped file change); no `[produced]` declaration, and data files still give no `changed`.
    - Parallel agents (23-4a): the README says to use one worktree per agent; no path scope and no warning in `new-task`.

## FlowGuard 5.1 candidate (`4d72073c`) in a Python desktop project

Observed on 2026-11-24 on an isolated worktree of PEMEL Studio `ff98023`. The full suite was `2766 passed`. The fixtures are small git repositories; "5.0.1" is the installed release.

### Where it helped
- **The excluded `.ts` problem is gone.** Full suite, `.ts` probes and `check --static` all pass without the local shim.
- **Real many-writer fields surfaced.** `check --static --all`: `Controller.task_dialog has no writers agreement and 7 files write it, workflows/data_edit.py:_save among them`. These writes, typed under `TYPE_CHECKING`, were invisible to 5.0.1.
- **Stale `known.toml` entries were flagged:** `known fixed?: known.dirty-field-default: writer:Project.dirty no longer found`.
- **A failed test is named apart from reds.** `pytest: exit 1, 1 failed` in `show --last`, and the brief says `1 test failed when last run and has not run since: …`.
- **Stale reds from an old cache are listed under the brief's own words**, `red in the intent results of the complete collection at … (the brief counts these):`, and a 23 s intent-only run clears them.

### 1. The candidate says 5.0.1 while its saved formats need 5.1
- **What happened:**
  - `python -m flowguard --version` → `5.0.1`; blocks print `FlowGuard 5.0 (since ff98023)`; `show --last` prints `FlowGuard 5.0.1 last run`.
  - On the same `ledger.toml`, the real 5.0.1 prints `red: Fallback ledger entry "app/slot.py:dispatch:Exception": unknown field reviewed` and `Form cannot be registered: … contextlib.suppress silently swallows errors`; this build gives `0 red`.
  - `pip install 'flowguard @ git+…@4d72073c'` over an installed 5.0.1 resolved the commit and installed nothing; only `--force-reinstall` installed it.
- **Why it matters:** an agent and CI pinned to `v5.0.1` cannot tell from any output that they check one ledger differently.
- **What would help:** bump `__version__` and pyproject before tagging, as the CHANGELOG examples (`FlowGuard 5.1 (since …)`) assume. Consider naming the commit in `--version` for an untagged build.
- **Code involved:** `flowguard/__init__.py:3`, `pyproject.toml:7`.

### 2. `known fixed?` after an upgrade says "if you meant to fix it"
- **What happened:** after the switch with no code change, `known fixed?: known.dirty-field-default: writer:Project.dirty no longer found -> it was left on purpose: if you meant to fix it, remove known.dirty-field-default and say so in your report`. The finding vanished because 5.1 reads `dirty: bool = False` as a declaration. The brief still lists `known.dirty-field-default: left as it is`, and `show Project.dirty` prints the entry as `left as it is`.
- **What would help:** when the finding's site and code are unchanged since the task start, say that this FlowGuard no longer reports it, not that the agent fixed it. Let the brief and `show` agree with `check` on `known fixed?`.

### 3. The brief: "0 open structure issues … highest severity"
- **What happened:** `0 open structure issues (4 other fields have multiple writers and no writer agreement); highest severity: write Controller.task_dialog; write Controller.discarded_project; write Controller.project`.
- **What would help:** count those fields in the head, or drop "highest severity" when the count is 0.

### 4. The 200-character cut removes the clause that names what changed
- **What happened:** fixture, `self.task_id, self.unrelated = …`. Block: `impact: Runner.start now writes Runner.unrelated; no longer wri... 0 other writers, 0 readers (untyped reads not counted) -> check them …`. `show --last` has `no longer writes Runner.operation` (218 characters). In-project: `known fixed?: known.simulation-state-field-default: writer:Simul...longer found -> …`.
- **What would help:** cut the fixed step text and counts first, and keep the field and finding names, as 5.1 already does for moved-writes lines.

### 5. Ledger count plurals
- **What happened:** `FlowGuard fallback ledger: 1 entries (0 legacy), 2 code handlers` and `ledger init`: `2 legacy entries, 2 handlers (1 forms cannot be newly registered)`. 5.1 fixed the same kind in the brief (PEMEL23-15b).

### 6. `init` recreates `.flowguard/ci.yml` on every refresh
- **What happened:** the brief says `… rules block that differs … python -m flowguard init rewrites it`. init also writes `.flowguard/ci.yml` again, which this project deliberately never committed (it wired CI by hand). So every rules-block refresh leaves an untracked fragment to delete.
- **What would help:** an `init` that rewrites only the rules block, or no new fragment when the project's pytest already loads the plugin.

### 7. `show Class.field` puts test fixtures before the product's writers
- **What happened:** `show Project.dirty` prints 18 `test fixture (not held)` lines before `declares … (default False)` and the two agreement writers.
- **What would help:** list the declaration and held writers first, then fixtures, or behind `--full`.

### Still open from the 5.0.1 notes, re-verified on 5.1
- **Moved file and renamed class read as new.** Fixture: a pure `git mv` gives `impact: copies _literal: a.py:_literal and moved.py:_literal differ`; a class rename gives `impact: GroupedLoss.evaluate now writes Info.hits, Info.profile`.
- **A merged or moved `same` copy reads as loosened:** `loosened: same TITLE removed from ui.py:title`.
- **Reasons:** `not compared: _added (calc.py:5) (not a module-level function)` for a function new since the baseline; `not compared: Child.hello (calibration closure is unsupported)` for a method calling `super()`.
- **A changed function no test calls** is absent from block and `show --last`.
- **Alias rows as exact matches** in `show citation_text` and `show EVENT_RULES`.
- **Cache growth:** +4.1k `site_history` rows and +1.5 MB per save of `controller.py`; the live cache is 791 MB with 1.44 M rows. No pruning code.
- **Timing:** one total in the block.

### Cost
- Suite on the same tree and baseline: 5.1 758.5 s, block 71.7 s; 5.0.1 723.5 s, block 64.6 s.
- Fresh map 36.5 MB (5.0.1: 34 MB); after the suite 40.5 MB (39.7 MB).
- Cold `check --static --all` 9.3 s.
- On the old 791 MB cache the first 5.1 run rebuilt in place: intent-only run 23.5 s, file +5.4 MB.
