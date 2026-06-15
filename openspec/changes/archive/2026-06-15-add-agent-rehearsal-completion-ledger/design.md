## Overview

Keep AgentWorkflowRehearsal as a pre-execution route, but add a report-level
ledger that makes "what is planned, what is blocked, what was skipped, what
needs recheck, and what can be claimed" explicit.

## Decisions

- Derive ledger fields from existing `AgentWorkflowPlan` and findings instead
  of adding a new route or second checker.
- Keep `completed_steps` empty for ordinary pre-execution rehearsal unless a
  future caller explicitly models completed handoff steps elsewhere. Rehearsal
  is not execution proof.
- Treat blocked finding step ids as `blocked_steps`.
- Treat skipped candidate skills as `skipped_steps`.
- Treat all non-info findings as `required_rechecks`.
- Use produced, continue, and final evidence ids as `handoff_points`.

## Non-Goals

- Do not execute workflow steps.
- Do not replace DevelopmentProcessFlow or RiskEvidenceLedger.
- Do not require a new CLI template in this change.
