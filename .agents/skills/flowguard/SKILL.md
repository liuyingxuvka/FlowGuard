---
name: flowguard
description: Read rule status, preserve words and find decision owners. Anchors connect rules and optional small flow models for complex maintenance. Maps cover Python, JS/TS, C/C++ and C#; execution is Python only.
---

# FlowGuard

Code is the target. Anchors are observation points. A small model relates readings without repeating the implementation.

Use: read `python -m flowguard` at session start when rules exist; find code with `python -m flowguard show "what it decides"`; reuse its owner. Save actual owner words once. After changing a bound decision, run `python -m flowguard check` through ordinary pytest; CI uses `check --all --deep`. `show --full` expands metadata. Candidates are clues, not proof.

Use ordinary code and tests for ordinary edits. Do not model the development task. When a decision has copies, the owner says "everywhere", or a bug was fixed, one rule and literal regression rows in `tests/intent/` can help. Derive expectations from the requirement independently of code; rows hold literal inputs, `expect` and `why`. Connect rules through source anchors, never an adapter supplying the answer.

## Optional observations

- `python -m flowguard anchor draft module:function` proposes a comment and input bounds. Confirm meaning and units. Unknown types or bounds remain grey. Pure judgments run directly; others need an ordinary project test named by `calibrated_by`. Calibration must agree before replacement cases count.
- Sensors observe judgments, events observe calls/completion, states identify existing fields. Same-name sensors must agree. `compare A B` compares joint input classes; sourced `distinct` declares different policies.
- Checks can show changed outcome classes. Before changing a complex old judgment, adding an anchor can preserve its old behavior. These comparisons remain available; they are not a required default step.
- A complex cross-module path can use a small `flow` in `tests/intent/`: anchor nodes, edges, existing state transitions and reading relations, roughly ten nodes per layer. Reuse verified lower rules. A save call alone does not prove the current file was saved.

The optional-use trial missed its correctness/cost gate. Default use stays narrow. Retest repeated decisions and cross-session paths with independent hidden checks.

Red is a demonstrated mismatch. Grey is unverified, not success. Finite checks cover declared inputs and models; runtime edges need tests. Dynamic calls, external inputs and concurrency may remain unknown. Syntax maps do not prove foreign execution. The local [rule guide](references/rules.md) owns examples and migration.

## Original words

`python -m flowguard req add <file|-> --id R1` stores actual words byte for byte. Never archive an AI plan or edit `.flowguard/requests/`. `req list` and `show R1` retrieve originals; `--supersedes` records replacements. Commits answering saved words include `Request: R1`.
