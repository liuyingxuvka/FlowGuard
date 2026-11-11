---
name: flowguard
description: Keep recorded agreements consistent while an AI changes code. Ordinary tests check necessary copies, field agreements, independent intent rules and fallback reasons.
---

# FlowGuard

1. Start with `python -m flowguard new-task` and read its brief. It records the task's baseline; commits during the task keep it.
2. Run the project's ordinary tests and read the FlowGuard block. Follow each finding's next step; tell the owner when it asks you to. Grey is unverified, not success.
3. Use `python -m flowguard show "what it decides"` before changing another copy. Reuse an existing agreement rather than writing a second policy.

Mark necessary same-name copies with `flowguard: same NAME`; `same NAME ref` marks a chosen reference. Use `together A B,C` for fields written together and `writers A f,g` for allowed writers. Bare writers refer to the comment's file; other files use repository-relative `path:function`. Exceptions need the owner's agreement. Use `#` in Python and `//` in TS/JS.

An independent rule belongs in `tests/intent/` and cites the owner's actual words or an exact document sentence. Store actual words once with `python -m flowguard req add <file|-> --id R1`; never archive an AI plan. Keep other context in real tests.

Register a useful agreement in the same change that discovers it. A new fallback needs a `.flowguard/ledger.toml` entry with its behavior, reason and written rule; forms the finding rejects cannot be listed. `check --all` lists open structure findings for deliberate review.

Do not model the development task. No source change stays quiet unless a constraint fails. See the [local reference](reference.md) for executable examples and supported annotations.
