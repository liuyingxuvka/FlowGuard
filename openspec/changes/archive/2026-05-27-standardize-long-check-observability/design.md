## Context

FlowGuard already emits bounded progress from direct `Explorer(...)` runs, but the skill does not tell agents how to manage long checks when they run in background processes. Some project runners also bypass direct Explorer progress and only write final reports. The missing convention creates avoidable ambiguity: an agent may inspect a task-local file, miss a fixed log directory, or claim a check passed without exit-code evidence.

## Goals / Non-Goals

**Goals:**
- Give FlowGuard skill users a stable default for background log artifacts.
- Make final reports evidence-backed by path, exit status, timestamp, and proof-reuse status.
- Keep stdout report pipelines stable by treating progress as stderr-only observability.
- Make the distinction between direct Explorer progress and legacy/custom final-only runners explicit.

**Non-Goals:**
- No new FlowGuard subprocess runner in this change.
- No change to Explorer pass/fail semantics.
- No requirement that every project use the same directory when a repository-local rule is stricter.
- No GitHub publication until the user explicitly approves the push phase.

## Decisions

- Use `tmp/flowguard_background/` as the default project-local directory because it is easy to inspect, safe to ignore in source control, and already matches the user's requested convention.
- Define five artifacts for each long check: `.out.txt`, `.err.txt`, `.combined.txt`, `.exit.txt`, and `.meta.json`. This keeps machine status separate while preserving a single human-readable combined log.
- Put the convention in the skill and `docs/agents_snippet.md`, with tests that assert the important phrases remain present.
- Do not add core API behavior for custom runners. A custom runner must either call Explorer or implement its own stderr progress while preserving FlowGuard's evidence rules.

## Risks / Trade-offs

- [Risk] Agents may treat progress lines as proof of success. -> Mitigation: the skill must state that progress is only liveness evidence; pass/fail still comes from executable checks and exit status.
- [Risk] Projects with existing log directories could be forced into churn. -> Mitigation: allow stricter repository-local conventions when the actual path is reported.
- [Risk] Documentation-only changes may drift. -> Mitigation: add focused doc tests for the long-check evidence contract.
