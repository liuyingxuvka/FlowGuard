# Tree operations

An operation is one target edit: `python -m flowguard target start "<goal>"`, then `python -m flowguard target add <id>` for every node to change.
Edit `.flowguard/target/` until `python -m flowguard target check` reports no ERROR and only TO-DO remains.
Write the code and tests until the same check reports no TO-DO.
Run `python -m flowguard target promote`, then `python -m flowguard map confirm <listed components>` and `python -m flowguard change`; run its selected checks.
