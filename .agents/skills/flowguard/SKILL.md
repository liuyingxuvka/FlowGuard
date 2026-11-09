---
name: flowguard
description: Keep a project consistent while an AI changes it. Ordinary tests (and npm test) print FlowGuard's red lines, changes, leads and unverified items - inconsistent same-name copies, violated owner rules, new fallbacks, writes outside an owner, changed behavior - each with the next step.
---

# FlowGuard

1. Run the project's ordinary tests (`python -m pytest`, or `npm test` in a TS project) and read the FlowGuard block: red, then changes, leads and unverified. Every red and lead ends with the next step; do it. When it says to tell the owner, tell the owner before changing the structure. Grey is unverified, not success. No source change stays quiet unless a constraint fails. The block compares with the task's baseline commit, which commits made during the task keep; start the next task with `python -m flowguard new-task`.
2. A judgment or a field that must agree everywhere has one owner: `# flowguard: owner NAME` above the owner, `# flowguard: sensor NAME` above each same-name copy, and `writers=` (with `with=` for a field that must change with it) on a data owner. Before adding a judgment, run `python -m flowguard show "what it decides"` and reuse its existing owner.
3. A rule the owner set that must keep holding goes into `tests/intent/` as an independent rule. Its source is the owner's words, stored once and byte for byte with `python -m flowguard req add <file|-> --id R1`; never store an AI plan. Fields the parameters lack come from the anchor's `fields name=expression`; other context stays in the real tests.

Do not model the development task. A new fallback needs an entry in `.flowguard/ledger.toml` with what it does, why it may stay and the written rule it serves; the forms the red line names cannot be listed. See [rules, anchors and the ledger](references/rules.md).
