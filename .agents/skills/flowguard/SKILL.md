---
name: flowguard
description: Compare real Python behavior before asserting rules. Ordinary tests show changed outcomes, inconsistent same-name sensors and violated independent requirements. A source map and optional small models support complex maintenance.
---

# FlowGuard

Run the project's ordinary tests with its FlowGuard plugin enabled. Read the few FlowGuard lines: what changed, what should have changed together, and which independent rule was violated. No source change stays quiet unless a constraint fails. CI uses `python -m flowguard check --all --deep`; probes and mutation checks are explicit deep work.

Code is the target. Anchors observe it. Rules and small models relate actual readings without repeating the implementation. Do not model the development task or add a second answer-producing adapter.

When copies must agree, put `# flowguard: sensor NAME` above each real judgment. `anchor draft module:function` proposes the comment and input bounds; confirm meaning and units. Inputs are varied; context objects stay in the real test context. Pure judgments run directly. Context-dependent code needs a real test named by `calibrated_by`; ambiguous or unsafe replay stays grey.

A requirement belongs in one independent `rule` in `tests/intent/`. Add literal `row` inputs, `expect` and `why` for genuine regressions. Cite only the relevant original words or authority document. Same-name sensors must agree; sourced `distinct` records genuinely different policies. Neither matching copies nor an observed change establishes the intended answer.

## Optional tools

- `python -m flowguard` reads a brief and remembers this task's baseline commit; `check --base COMMIT` overrides the comparison baseline.
- `show "what it decides"` finds existing owners. Reuse them. Copy suggestions are clues; `show --full` expands metadata.
- `show NAME` shows recorded anchor/model observations. `try NAME k=v [--grid]` explores actual inputs; grid prints every evaluated representative. `watch -- python app.py` records a real run and checks its models.
- For a complex path, `model draft NAME` proposes a small flow from recorded events. Review nodes, edges, existing state transitions and reading relations; layer large graphs. Unobserved edges stay grey. An observed save call alone does not prove the right file was saved.

Red is a demonstrated disagreement. Grey is unverified, not success. Finite checks cover declared classes and models, not every external input or concurrent execution. Non-Python readers are optional static maps, without executable observations. See [rule examples and migration](references/rules.md).

`req add <file|-> --id R1` stores actual source words byte for byte. Never archive an AI plan or edit `.flowguard/requests/`. `req list` and `show R1` retrieve originals; `--supersedes` records replacements. Commits answering saved words include `Request: R1`.
