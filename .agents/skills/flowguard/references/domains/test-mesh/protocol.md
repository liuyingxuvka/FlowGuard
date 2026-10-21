# Test Mesh
Use this when the test suite is too large or slow to run in one command. FlowGuard's shard
runner collects the whole suite once, splits the exact pytest node ids into disjoint shards,
runs them in parallel with a time limit, and checks that every collected test ran exactly
once. It catches false green from large runs: a shard that died, a test that ran twice or
never, skips hidden in a green summary, a background job's progress reported as a pass.
## Use when
- The test suite is too large or slow to run whole on every change and must be split.
- Tests run in the background, in parallel shards, or with timeouts.
## Do not use when

- The test set is small and runs in one command. Just run it.
- You only need the tests `python -m flowguard change` selected. Run its printed command; the shard runner cannot run a subset.
- You need to decide which tests match which model behavior. Use model-test.
- You need to split code or models, not tests. Use code-structure or model-mesh.

## Inputs

- `python -m flowguard change`: changed files, owning components, tests and models to run.
- How long the whole suite takes, and whether some tests need a platform capability (for example symlinks on Windows).

## Steps

1. Run `python -m flowguard change` to choose the affected tests before execution.
   For a small selected set, run the exact printed commands once and stop here.
2. If the whole suite must run and it is too slow in one process, run the packaged runner:
   `python -m flowguard.pytest_shards_cli --root . --shards 4 --parallel-shards 4`.
   It prints a short summary (status, one line per shard, blockers, result directory);
   `--json` prints the full result. Open `aggregate.json` in the result directory only when
   a shard is not `pass`.
3. For a failing shard, read its `stdout.log` in the result directory, fix the cause, then rerun
   the failing test directly and the shard runner once.

## What blocks

| Status | Meaning |
| --- | --- |
| `fail` | A test failed or errored in some shard. |
| `blocked` | A shard timed out, its process cleanup was not confirmed, the shard results do not add up to the collected tests (a test ran twice or never), or a test needs a capability this machine lacks. |
| `partial` | A required test was skipped. |
| `pass` | Every collected test ran exactly once and passed. |

## Risk-specific regression examples

- A test that hangs: its shard reaches `--shard-timeout`, is killed and reported `blocked`, never `pass`.
- A test that starts a background helper and does not wait for it: the helper is killed when the
  shard ends; the shard stays `pass` and its row says `lingering_killed: true`.

## Done when

- [ ] You report only the runner's (or pytest's) actual terminal result; no second run to confirm it.
- [ ] Every selected test file is listed in some component's `tests` in map.json.
- [ ] `python -m flowguard change` shows no unmapped files and the listed tests pass.
- [ ] Report planned/executed/failed/not-run counts, what ran, what was deferred or skipped, and why.

## Limits
- The shard runner always collects the whole suite; it cannot run only the files `change`
  selected. Run those directly with pytest.
- `--resume-output` reuses a prior shard only when its inputs and environment are identical;
  never resume for a final release gate.
- A green shard run shows every test ran once and passed. It does not show the tests check the
  right behavior; pair it with model-test.
