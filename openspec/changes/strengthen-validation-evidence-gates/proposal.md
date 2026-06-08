## Why

FlowGuard already has strong route-specific evidence rules, but UI click-through,
manual review, file import/export, and AI work-package validation are not
expressed as one clear cross-route completion gate. Agents can therefore
overclaim completion from partial UI runs, prose-only manual review, or
happy-path file tests that do not exercise representative payload failures.

## What Changes

- Add a cross-route validation evidence gate for UI actions, external artifact
  payloads, and AI work packages.
- Strengthen UI implementation validation so each reachable actionable
  control/event needs real run evidence, a pure-UI classification, or a scoped
  blindspot.
- Add artifact payload contracts and evidence under Model-Test Alignment for
  file formats, import/export flows, round trips, and AI work-package payloads.
- Route large payload matrices through TestMesh child suites instead of
  flattening every payload case into one parent claim.
- Make DevelopmentProcessFlow derive minimum revalidation when changes touch
  payload schemas, import/export behavior, UI action maps, installed skills, or
  validation prompts.
- Update Codex skill guidance, templates, docs, and self-maintenance checks so
  installed prompts and generated examples teach the same evidence boundary.
- No breaking changes are intended for existing model-test-only plans. New
  gates apply when a claim explicitly includes implemented UI, artifact
  payload, work-package, or broad completion confidence.

## Capabilities

### New Capabilities
- `validation-evidence-gates`: Cross-route completion gates for UI action
  evidence, manual-check boundaries, artifact payload contracts, synthetic
  payload packs, and final confidence consumption.

### Modified Capabilities
- `flowguard-ui-flow-structure`: Require reachable actionable controls/events
  to have real run evidence, pure-UI classification, or scoped blindspots.
- `model-test-alignment`: Add artifact payload contract/evidence comparison and
  block alignment when payload evidence is missing, stale, non-passing, or
  mismatched.
- `test-evidence-mesh`: Let large payload validation matrices become child
  suite ownership surfaces with current proof artifacts.
- `development-process-flow`: Treat UI/action maps, payload schemas, package
  prompts, and installed-skill sync as freshness-sensitive validation
  boundaries.
- `plan-detailing-compiler`: Require rough plans to expose UI action,
  artifact-payload, AI work-package, manual-review, and final evidence
  surfaces before broad claims.
- `flowguard-codex-skill-satellites`: Keep installed satellite prompt guidance
  aligned with the new validation gates.
- `risk-evidence-ledger`: Require final broad confidence claims to consume the
  new UI/payload evidence rows or report scoped blindspots.

## Impact

Affected surfaces include FlowGuard public helper APIs, Codex skill guidance,
AGENTS adoption snippets, route protocols, starter templates, docs, tests,
OpenSpec artifacts, local installed skills, editable install state, and
release/version metadata. The change remains standard-library-only and does not
add a new external dependency.
