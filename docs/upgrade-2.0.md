# Moving from FlowGuard 1.x

FlowGuard now has one narrow purpose: find an existing decision and keep necessary copies consistent. This is a source/API change; old flow models are not executed by a compatibility path.

1. Keep `.flowguard/requests/` unchanged. `req add`, `req list` and `show R1` retain the original-byte archive.
2. Read the old contracts and their parametrized tests before deleting anything. Carry each still-useful requirement into a literal row, a bound rule, a state declaration or an ordinary test. Record the correspondence in the change description; do not reduce behavior merely because the new representation is shorter.
3. Run `python -m flowguard init`. Merge its four project rules and CI fragment with the project rules. Fetch complete history in CI so no-shrink comparisons can read their base.
4. Bind actual implementations. One rule covers every necessary copy; an adapter calls the real function. Keep ordinary tests for behavior that does not need a shared rule. Use the shared structure queries for source scans rather than copying the scanner.
5. Run affected `check` and the project's normal full pytest suite. CI uses `python -m flowguard check --all`, which invokes ordinary pytest once. Fix red findings and explain genuinely unverified boundaries.
6. Remove migrated `.flowguard/flow/`, self-models and old migration scaffolding after their useful contracts have a verified home. The old `status`, `where`, top-level `draft`, `decide` and `release` commands have no aliases. Use the default screen, `show`, `show --draft`, `check` and ordinary project release automation instead.

There are no background workers, leases, execution receipts, model-only machine walks, pictures or a second test runner. Candidate lists are static leads: bind a candidate explicitly when it represents the same decision. The tool does not run automatic sandbox comparisons or record boundary values. Complete `check --all` retains test-to-code links as an incremental baseline; local `check` refreshes selected tests. With plain pytest, unmarked ordinary tests avoid general tracing; marked guards still record their code links. Keep these real links when they are needed, while reporting their collection cost.

A library adopting the new rule API may update its FlowGuard test dependency once the official release exists. A new FlowGuard release alone is no reason to change another library's dependency or publish it. Skill publication and installation remain separate from building and testing the Python package.
