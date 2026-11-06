---
name: flowguard
description: Find an existing decision before adding code; bind necessary copies to one executable rule so later changes cannot silently make them disagree. Use for Python code maintenance, not for every edit.
---

# FlowGuard

Keep a decision in one place. Where copies must exist, check them together.

## Two moments

- Before writing or changing a decision, run `python -m flowguard show "what it decides"`. Reuse the owner; candidates are leads, not semantic proof.
- Only when a decision has copies, the owner says "everywhere", or a bug was fixed: write one rule in `tests/intent/`, bind every real copy as a home, and add a literal row explaining the regression. Otherwise use ordinary code and tests. Do not model the development task.

When the project already has rules, read `python -m flowguard` at session start. It shows cached facts without running project code or tests. Use `show RULE` for details. With no rules, stay quiet.

## Small, real checks

Before writing the first rule, read the local [rule guide](references/rules.md): complete inputs, source, literal row and real-home example.

Write the rule from the requirement, not from the implementation. A home adapter builds inputs and calls real code; it never computes the expected answer. Rows have literal inputs, `expect` and `why`. Cite `source="owner R1"` or agreed document words. An assumption is not authority.

After a bound decision changes, run `python -m flowguard check`. It uses ordinary pytest; selected tests refresh their code links. CI uses `check --all` for complete links. Red needs repair; grey names an unverified boundary, not success. Green covers the declared inputs and homes. Change code and its real tests together; report actual commands and results.

Use `python -m flowguard init` once to add the pytest sentinel, CI fragment and four project rules. Install the engine from `git+https://github.com/liuyingxuvka/FlowGuard.git`; the similarly named PyPI project is different.

## Original words

Store a new owner message once with `python -m flowguard req add <file|-> --id <id>`, byte for byte. Never store an AI plan as owner words or edit `.flowguard/requests/`. Use `--supersedes` for a replacement; `req list` and `show R1` retrieve it. Commits answering it include `Request: R1`.
