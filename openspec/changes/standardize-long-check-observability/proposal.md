## Why

Long-running FlowGuard checks now have core progress output, but project agents can still lose observability when logs are scattered, only final reports are inspected, or completion is claimed without exit-code evidence. The skill needs a small, explicit convention so agents know where to write background logs and what evidence to report.

## What Changes

- Add a default long-check log convention for FlowGuard skill users.
- Require long-running checks to record stdout, stderr, combined output, exit status, and metadata when they are run in the background.
- Require final reports to name the log path, exit code, last update time, and whether a prior proof/result was reused.
- Clarify that Explorer progress lines are observability only, while pass/fail still comes from executable checks and reports.
- Clarify that legacy or custom runners may only emit a final report unless they are adapted to emit progress.
- Keep project-specific stricter conventions allowed when they are explicitly reported.

## Capabilities

### New Capabilities
- `long-check-observability`: Standard evidence and reporting rules for long-running FlowGuard checks.

### Modified Capabilities
- None.

## Impact

- Updates the `model-first-function-flow` Codex skill source.
- Updates the installable agent snippet so repository `AGENTS.md` excerpts can carry the same convention.
- Adds tests that keep the skill documentation from regressing.
