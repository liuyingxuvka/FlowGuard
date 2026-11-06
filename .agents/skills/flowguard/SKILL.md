---
name: flowguard
description: Navigate code and connect source anchors to rules or small flow models. Use for complex maintenance, repeated decisions and cross-session commitments. Maps cover Python, JS/TS, C/C++ and C#; execution is Python only.
---

# FlowGuard

Code is the target. Anchors are observation points. A small model relates their readings; it does not repeat the implementation.

When rules already exist, `python -m flowguard` reads their cached status. `python -m flowguard show "what it decides"` finds existing owners and possible copies. Reuse the owner where possible. Candidates are navigation clues, not semantic proof. `show --full` expands metadata.

Use ordinary code and tests for ordinary edits. Do not model the development task. When a decision has copies, the owner says "everywhere", or a bug was fixed, one rule and literal regression rows in `tests/intent/` can help. Write expectations from the requirement, independently of the code. Rows contain literal inputs, `expect` and `why`.

## Available observations

- `python -m flowguard anchor draft module:function` proposes a source comment and input bounds. Confirm its meaning and units. Unknown types or bounds remain grey.
- Sensor anchors observe real judgments; event anchors observe calls and completion; states anchors identify existing state fields. Pure functions run directly. Other functions need an ordinary project test selected by `calibrated_by`; calibration must agree before replacement cases count.
- `python -m flowguard check` checks commitments and shows changed outcome classes using ordinary pytest. CI uses `check --all`. `compare A B` compares two anchors on their joint input classes. Same-name sensors must agree; different policies can use sourced `distinct` declarations.
- For a complex cross-module path, a small `flow` in `tests/intent/` has only anchor nodes, edges, state transitions and reading relations. Keep roughly ten nodes per layer. Reuse verified lower rules. Observe actual identity and successful completion: a save call alone does not prove a current file was saved.

Red is a demonstrated mismatch. Grey is an unverified boundary, not success. Finite checks cover the declared inputs and model; runtime edges need real tests. Syntax maps do not prove foreign-language execution. Dynamic calls, external inputs and concurrent traces can remain unknown.

The local [rule guide](references/rules.md) owns examples and migration. Connect through source anchors; do not write an adapter that supplies an answer or another model of the same code.

## Original words

Save an actual new owner message once, byte for byte: `python -m flowguard req add <file|-> --id R1`. Never archive an AI plan as owner words or edit `.flowguard/requests/`. `req list` and `show R1` retrieve originals; `--supersedes` records replacements. Commits answering a saved message include `Request: R1`.
