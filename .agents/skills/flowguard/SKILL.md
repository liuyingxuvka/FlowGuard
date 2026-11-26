---
name: flowguard
description: Keep recorded agreements consistent while an AI changes code. Ordinary tests check necessary copies, field agreements, independent intent rules and fallback reasons.
---

# FlowGuard

1. Start with `python -m flowguard new-task` and read its brief: the owner's current rules and the open items. It records the task's baseline.
2. Run the project's ordinary tests and read the FlowGuard block at the end; its first line counts each kind. `red` means your change broke a recorded agreement: fix the code. `before` and `known` were there before your task: after `->` each says what is known and who decides; you choose when to raise an open question with the owner. `changed` means a function returns something else for the input shown: say so if you meant it. `impact` and `not compared` are not failures; `not compared` is unverified, not success. `python -m flowguard show --last` prints every line with its details.
3. Use `python -m flowguard show "what it decides"` before changing another copy. Reuse an existing agreement rather than writing a second policy.

Mark necessary same-name copies with `flowguard: same NAME`; `same NAME ref` marks a chosen reference. Use `together A B,C` for fields written together and `writers A f,g` for allowed writers. Bare writers refer to the comment's file; other files use repository-relative `path:function`. An `except=`, a removed comment or a `.flowguard/known.toml` edit that clears a finding loosens an agreement, which is the owner's decision. Use `#` in Python and `//` in TS/JS.

An independent rule belongs in `tests/intent/` and cites the owner's actual words or an exact document sentence; its anchor is a Python function (TS/JS copies are compared by `same`). Store actual words once with `python -m flowguard req add <file|-> --id R1`, his pick among your options with `--offer FILE --picked TEXT`; never archive an AI plan. Keep `.flowguard/rules.toml` current, each rule's source quoting those words; put a problem only the owner can decide into `.flowguard/known.toml` with `act = "ask"` (`known add` writes it). Put `<!-- flowguard: about path:symbol -->` above a Markdown text that describes code; a change to that code then names the text. A text about a file or `folder/` is that module's contract: a change to a function it calls or that calls it names it too, and `python -m flowguard show PATH` lists a module's contracts and connections. A list the code already holds goes between `<!-- flowguard: generate fields Model -->` (or `values`, `functions`, `constants`) and `<!-- flowguard: end -->`; `python -m flowguard docs` writes it. Keep other context in real tests.

Register a useful agreement in the same change that discovers it. A new fallback needs a `.flowguard/ledger.toml` entry with its behavior, reason and written rule; forms the finding rejects cannot be listed. `check --all` lists open structure findings for deliberate review.

Whether anything about a project may leave it is its owner's decision; where it may, report what FlowGuard gets wrong or could do as an issue, without the project's code, names or data. FlowGuard never updates itself (reference: Feedback and new releases).

Do not model the development task. No source change stays quiet unless a constraint fails. See the [local reference](reference.md) for executable examples, the two files and supported annotations.
