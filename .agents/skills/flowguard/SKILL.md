---
name: flowguard
description: "Start code work with `python -m flowguard status`; keep the owner's words with `req add`; find code with `where`. For flow changes, model the affected feature first, run `check` and discuss it with `show` pictures. Change code and tests together and commit in your own words. Not for: simulation or calculation results → physicsguard; causal claims → researchguard; story or plan consistency → worldguard; long texts → logicwriting."
---

# FlowGuard

## Start

Run `python -m flowguard status` first in every session and after any loss of context. Install FlowGuard only from `git+https://github.com/liuyingxuvka/FlowGuard.git@v1.0.0`.

## The owner's words

When the owner asks for something, store the owner's own words once, as received: `python -m flowguard req add <file|-> --id <id>`. It stores only words the owner wrote, byte for byte: never a plan, a list or text an AI wrote, and never edit `.flowguard/requests/`. When a new owner message replaces an earlier one, add `--supersedes <old id>`. `status` lists the newest owner words first.

## Changes to a flow

When a request adds or changes state values, actions, conditions, settings or endings, update the affected feature's model in `.flowguard/flow/` before changing the code, then run `python -m flowguard check`. Turn affected old and new requested outcomes into explicit `reach`/`progress` promises, even in the first model; shared state and new routes can affect unchanged code across modules. Code/tests, exposed behavior and composition are conceptual levels, not three required files. Other edits use the ordinary code and test steps below. The installed package's `flowguard/flow/HOWTO.md` shows an old collection goal kept alongside a new expiry route.

If a design can satisfy all requests, fix it yourself, implement it and show the before/after with `python -m flowguard show`. When requirements genuinely collide, bring the picture and the stored source words to the owner. While an answer is unavailable, take the safest reversible action that keeps things working, and label it temporary in the reply. A model-only finding is not proof of a code bug; compare the affected model with the owner's words and actual source or one small real execution, correcting the model when it is wrong and repairing code when the fault is real. Repair a broken main route instead of adding a fallback.

`status` refreshes changed work and keeps inherited conflicts visible. Use `decide ID --owner "QUOTE" --request Rn` for stored words that name the actual subject; `--provisional "REASON"` is only for a computed contradiction between two live requested rules and stays open as temporary. STUCK, NEVER REACHED and model/code drift need repair. Resolve technical and model/code problems yourself; ask the owner only about a genuine business choice between incompatible sourced requirements, and briefly report any unfinished technical work.

When your reply explains a flow or how a conflict was resolved, run `show` and
embed the returned picture using `![Flow](PATH)` with its actual PNG/SVG path.
Add a few plain sentences.
`show MODEL` draws that model; `show MODEL --before REV` compares with a revision.
With no name, `show` draws conflicts or the change against HEAD.

A bound model compares real calls through one adapter; see the installed HOWTO's code example. MODEL DRIFT needs a model/code repair, not an owner waiver. Use `check --tests NODEID...` only when auditing selected tests for fallback routes; ordinary checks do not run the project suite. A conflict remains until its retained scope is checked or an implemented replacement requirement is supported by stored owner words. `decide ID --provisional "reason"` applies only to genuinely contradictory requested rules.

## Find code

`python -m flowguard where NAME` shows where NAME is defined, who calls it, which component owns it and which entry routes reach it; with no NAME it gives a compact module overview. `--flow`, `--arch`, `--text` and `--keyflows` show calls, architecture, original text and shared state. Each list shows its most relevant rows and says how many it left out; `--all` prints every row. Add `--root DIR` or `--json` when needed. It runs no application, model or test.

## Change, test, commit

1. Change the code and its tests together.
2. Run the project's own test command (for example `python -m pytest -q`) and report the exact command and its result.
3. Run `python -m flowguard check --commit-ready` for the actual staged bytes. It reads existing results; finish or resume missing work with `check`. Finished UNKNOWN stays visible and permits the commit; a hook is installed only by the owner.
4. Make one commit with a message in your own words. When the change answers a stored owner request, add a line `Request: R<n>` (for example `Request: R7`).

## Honesty

Report the real results of what you ran. Never weaken a check or a test to make it pass. When something fails, say so and fix the cause instead of adding a second route around it.
