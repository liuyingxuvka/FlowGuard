## Why

FlowGuard's model coverage and release evidence are strong, but ordinary agent
use can load nearly the full model inventory and echo large successful result
payloads. This spends substantial context and output tokens even when the
decision only needs a small owner set and a compact terminal summary.

## What Changes

- Make Existing Model Preflight select a bounded, plane-first owner set before
  materializing model details; light mode remains shallow and full mode expands
  only the selected owner closure.
- Make successful validation commands emit a compact terminal envelope by
  default while retaining complete immutable evidence in result artifacts;
  failures, skips, stale evidence, and not-run work remain visible.
- Enforce representative hot-path prompt budgets over the actual first-read
  bundle rather than isolated files alone.
- Keep WorkContext artifacts context-only unless they are explicitly admitted
  as behavior-source surfaces.
- Make Behavior Commitment Ledger discovery breadth follow its declared mode,
  so existing-project change work does not silently fall back to bootstrap-wide
  inventory.
- Require test-result reuse consumers to verify the current producer identity
  and fingerprints instead of trusting a self-reported reusable flag.
- Fold repeated always-on guidance into guaranteed-loaded shared route material
  while preserving each satellite skill's trigger, owner, gates, and claim
  boundary.
- Add deterministic token/byte telemetry for representative agent routes and
  release regressions.

## Capabilities

### New Capabilities

<!-- None. This change tightens existing FlowGuard capabilities. -->

### Modified Capabilities

- `existing-model-preflight`: bound default recall and separate shallow light
  output from selected-owner full expansion.
- `flowguard-ai-entry-simplification`: enforce combined first-read budgets,
  shared guidance loading, and representative route telemetry.
- `validation-evidence-gates`: define compact terminal output envelopes without
  discarding complete evidence.
- `work-context`: require explicit behavior admission before context artifacts
  enter behavior coverage inventory.
- `behavior-commitment-ledger`: make broad discovery conditional on the
  declared ledger mode.
- `test-result-reuse-proof`: require consumer-side identity and fingerprint
  verification.

## Impact

Affected areas include existing-model lookup, behavior/source inventory,
validation result serialization, evidence diagnostics, skill prompts and
shared references, prompt-budget tests, TestMesh reuse checks, FlowGuard models,
SkillGuard-maintained consumer distributions, installed skills, package
versioning, and release verification. The default human/AI-facing output shape
becomes smaller, but full result artifacts and failure visibility remain
available.
