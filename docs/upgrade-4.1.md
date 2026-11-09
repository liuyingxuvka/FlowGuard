# Moving from FlowGuard 4.0 to 4.1

4.1 is a feature release. Source comments, rules, literal rows, sources, flows and immutable owner-word records keep their meaning and bytes; nothing needs rewriting. Some results become stricter where 4.0 quietly showed an unverified result as a pass. This page lists what you will notice.

## What changes in a test run

| 4.0 | 4.1 |
| --- | --- |
| A grey intent item was reported as PASSED | It is its own outcome: `U` with `-q`, `UNVERIFIED` with `-v`, `N unverified` in the summary. The exit status is unchanged. With `--junitxml` it carries the property `flowguard_outcome=unverified`. |
| A change that made an observed point grey went unnoticed | With a baseline commit, a point the baseline code still observes but the new code cannot is a lost observation and fails the run. Restore the observation at the named line, or list the anchor or rule under `[unverified]` in `.flowguard/ledger.toml` with a reason of at least eight words. Without a baseline (CI) nothing is lost. |
| `check --all` passed grey rules | A grey rule, flow or one-line template whose source quotes the owner's words fails `check --all` unless `[unverified]` lists it. The `--deep` mutation item alone does not make a rule grey. |
| pytest-xdist workers dropped session reds | FlowGuard stops with a usage error under `-n N` (N > 0) before any test runs; run without `-n` or with `-n 0`. |
| Replays needed a static proof of no side effects | A runtime guard refuses file, process, network, thread and sqlite writes before they happen; the static check only stops explicit writes. More calls replay, so some former greys become green or red. Uncopyable or unseen arguments stay grey with their reason. |
| Weak copy candidates in `show` | Removed. Look-alikes come from structure and behavior and are labelled `look-alike`. |
| The output listed three signals | One block, titled with its baseline commit: every red, then changes, leads and unverified within ten lines, each red and lead with a next step to copy. |

## New, opt-in or automatic

- `python -m flowguard ledger init` starts the fallback ledger; without `.flowguard/ledger.toml` nothing changes. It refuses to start a second list when the project already keeps its own handler-list test.
- `# flowguard: owner NAME` and data owners `owner Model.field writers=... with=... alone=...`; copy discovery in `check`; leads for an old value still spelled elsewhere and for a copy changed while its rule was not.
- `fields name=expression` on an anchor reads rule fields from the call's context.
- Value gates (`states`, enums, Prisma enums, SQL `CHECK`), deletes that leave restricting children, schema gaps, label drift and the structure listing with `[structure]` decisions.
- `precedes`, `guarded_by`, `transitions` and `checks` relation templates.
- TS/JS: `python -m flowguard check --static`, wired into `npm test` by `init`; vitest projects (ESM) also get the before/after comparison. jest stays static.
- `init` writes three project rules in place of the four, and replaces the owner's older level-one rules block.

## What stays

`flow_paths` and `check_flow(static=...)` stay frozen: the engine never runs them, and their direct helpers keep their narrower source scope. The C, C++ and C# readers stay frozen. Python 3.11 has no per-function monitoring, so a changed project with anchors runs slower there than on 3.12 and later.
