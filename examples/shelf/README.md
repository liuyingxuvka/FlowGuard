# shelf: a small model tree, a target and the code after the change

A tiny lending library with its own FlowGuard map (`.flowguard/map.json`), one contract
model (`.flowguard/models/lending.py`), a target that adds holds (`target/`) and the code
and tests that implement it (`after/`). The project is this directory without `target/` and `after/`.

1. `mkdir /tmp/shelf && cd <repo>/examples/shelf && cp -r .flowguard shelf tests /tmp/shelf/ && cd /tmp/shelf`
2. `git init -q && git add . && git commit -qm "shelf baseline"`
3. `python -m flowguard map confirm all` and `python -m flowguard map models --tests`: the current tree passes.
4. `cp -r <repo>/examples/shelf/target .flowguard/target` (the target: `loans` gains
   `LoanService.hold`, the state "holds per book in order", and `lending` the rule
   `no_idle_copy_while_held` with the known-bad variant `return_ignores_holds`).
5. `python -m flowguard target check`: only TO-DO lines (the code and test are not written yet; exit 3).
6. `cp -r <repo>/examples/shelf/after/. .` (the new `LoanService.hold`, the hand-over in `give_back` and its test).
7. `python -m flowguard target check`: clean (exit 0).
8. `python -m flowguard target promote`, then `python -m flowguard map confirm loans`.

The target is kept in `target/`, not `.flowguard/target/`, so that this example has no unfinished
target; FlowGuard's own map ignores `examples/shelf/**`.


## Port change

The desk consumes lending's two-way `answer` and prints refusals. In an open
target, add `waitlisted` to lending's `OUTPUTS["answer"]`, then run
`python -m flowguard target check`. It names
`port changed: lending out +waitlisted -> verify desk (parent)` and
`port_changed_parent_missing`. Add `desk` with `python -m flowguard target add desk`.
Its own run then reports `handoff_output_unhandled` until a real desk trace receives
`waitlisted` into `answer` and replies to it. Declaring the new value alone does not
implement a waiting list; the target must describe and replay that behavior.
