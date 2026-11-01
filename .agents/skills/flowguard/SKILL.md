---
name: flowguard
description: "Start every code change with `python -m flowguard status`; keep the owner's own words with `req add`; find code with `where`; change code and tests together, run the project's tests and commit in your own words. Use it for any change to code, its behaviour or its structure. Not for: simulation or calculation results → physicsguard; causal claims → researchguard; story or plan consistency → worldguard; long texts → logicwriting."
---

# FlowGuard

## Start

Run `python -m flowguard status` first in every session and after any loss of context. Install FlowGuard only from `git+https://github.com/liuyingxuvka/FlowGuard.git@v0.71.1`.

## The owner's words

When the owner asks for something, store the owner's own words once, as received: `python -m flowguard req add <file|-> --id <id>`. It stores only words the owner wrote, byte for byte: never a plan, a list or text an AI wrote, and never edit `.flowguard/requests/`. When a new owner message replaces an earlier one, add `--supersedes <old id>`. `status` lists the newest owner words first.

## Find code

`python -m flowguard where NAME` shows where NAME is defined, who calls it, which component owns it and which entry routes reach it; with no NAME it gives a compact module overview. `--flow`, `--arch`, `--text` and `--keyflows` show calls, architecture, original text and shared state. Each list shows its most relevant rows and says how many it left out; `--all` prints every row. Add `--root DIR` or `--json` when needed. It runs no application, model or test.

## Change, test, commit

1. Change the code and its tests together.
2. Run the project's own test command (for example `python -m pytest -q`) and report the exact command and its result.
3. Make one commit with a message in your own words. When the change answers a stored owner request, add a line `Request: R<n>` (for example `Request: R7`).

The legacy files `.flowguard/map.json` and `.flowguard/models/` and the target commands stay usable until v1.0.0, but a change needs none of them; findings about file ownership, stale descriptions or declared dependencies are information. If a legacy model fails in CI after your change, fix the code or edit that model file directly.

## Honesty

Report the real results of what you ran. Never weaken a check or a test to make it pass. When something fails, say so and fix the cause instead of adding a second route around it.
