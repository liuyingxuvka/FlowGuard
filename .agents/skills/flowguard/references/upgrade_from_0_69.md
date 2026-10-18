# Upgrade a project from FlowGuard 0.69

The current map, `.flowguard/map.json`, replaces `.flowguard/project.toml` and the
old ledger/receipt gates. Preserve old material in git history; do not turn old
results into current proof.

1. Save or commit the old project state before changing its integration.
2. Remove `.flowguard/project.toml` from the active tree (keep its git history).
3. Replace old FlowGuard/SkillGuard sections in AGENTS.md or CLAUDE.md with the six
   rules from `python -m flowguard template adoption --write .`.
4. Run `python -m flowguard map scan`, inspect `map discover` and `map digest all`,
   then describe components, owners, entrypoints, state, effects, tests and models.
5. `python -m flowguard map deps --write` keeps edges supported by actual imports, literal module
   references or explicitly justified accepted debts; unsupported declarations are removed. Follow
   `first_map.md`, fix `map check` errors, review dependencies and confirm the map.
6. Keep existing models whose declared boundary still matters. Register top-level
   contract models or the real `run_checks.py` paths; do not register nested model.py.
7. During migration run `python -m flowguard change` and its selected checks. At the
   final frozen revision run the full project suite and `python -m flowguard release`
   once, or use successful CI for that exact source SHA, before claiming completion.
8. Do not retain SkillGuard compile/owner-receipt/selfproof or authority-closure gates.
   Move any necessary business assertion to the existing native test/model runner;
   remove unconsumed projection envelopes. Code/model/test bindings remain native.

Daily commands are read, change and release. Old self-review, self-conformance,
model-impact freshness and authority snapshot APIs are retired in 0.70.0.
Component IDs select `read --component`; executable model IDs select `map models`.
`read` may update disposable caches but does not change project behavior/data.
