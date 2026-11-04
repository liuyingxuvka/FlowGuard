---
name: flowguard
description: "Start code work with `python -m flowguard status`; keep the owner's words with `req add`; find code with `where`. For flow changes, model the affected feature first, run `check` and discuss it with `show` pictures. Change code and tests together and commit in your own words. Not for: simulation or calculation results → physicsguard; causal claims → researchguard; story or plan consistency → worldguard; long texts → logicwriting."
---

# FlowGuard

## Start

Run `python -m flowguard status` first in every session and after any loss of context. Install FlowGuard only from `git+https://github.com/liuyingxuvka/FlowGuard.git@v0.74.0`.

## The owner's words

When the owner asks for something, store the owner's own words once, as received: `python -m flowguard req add <file|-> --id <id>`. It stores only words the owner wrote, byte for byte: never a plan, a list or text an AI wrote, and never edit `.flowguard/requests/`. When a new owner message replaces an earlier one, add `--supersedes <old id>`. `status` lists the newest owner words first.

## Changes to a flow

When a request adds or changes state values, actions, conditions, settings or endings, update the affected feature's model in `.flowguard/flow/` before changing the code, then run `python -m flowguard check`. Turn affected old and new requested outcomes into explicit `reach`/`progress` promises, even in the first model; shared state and new routes can affect unchanged code across modules. Code/tests, exposed behavior and composition are conceptual levels, not three required files. Other edits use the ordinary code and test steps below. The installed package's `flowguard/flow/HOWTO.md` shows an old collection goal kept alongside a new expiry route.

If a design can satisfy all requests, fix it yourself, implement it and show the before/after with `python -m flowguard show`. When requirements genuinely collide, bring the picture and the stored source words to the owner. While an answer is unavailable, take the safest reversible action that keeps things working, and label it temporary in the reply. Dead ends and never-happens behavior must be fixed in code; a temporary decision does not settle them. Repair a broken main route instead of adding a fallback.

When your reply explains a flow or how a conflict was resolved, run `show` and
embed the returned picture using `![Flow](PATH)` with its actual PNG/SVG path.
Add a few plain sentences.
`show MODEL` draws that model; `show MODEL --before REV` compares with a revision.
With no name, `show` draws conflicts or the change against HEAD.

## Find code

`python -m flowguard where NAME` shows where NAME is defined, who calls it, which component owns it and which entry routes reach it; with no NAME it gives a compact module overview. `--flow`, `--arch`, `--text` and `--keyflows` show calls, architecture, original text and shared state. Each list shows its most relevant rows and says how many it left out; `--all` prints every row. Add `--root DIR` or `--json` when needed. It runs no application, model or test.

## Change, test, commit

1. Change the code and its tests together.
2. Run the project's own test command (for example `python -m pytest -q`) and report the exact command and its result.
3. Make one commit with a message in your own words. When the change answers a stored owner request, add a line `Request: R<n>` (for example `Request: R7`).

The legacy files `.flowguard/map.json` and `.flowguard/models/` and the target commands stay usable until v1.0.0, but a change needs none of them; findings about file ownership, stale descriptions or declared dependencies are information. If a legacy model fails in CI after your change, fix the code or edit that model file directly.

## Honesty

Report the real results of what you ran. Never weaken a check or a test to make it pass. When something fails, say so and fix the cause instead of adding a second route around it.
