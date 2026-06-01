# Add Model Topology Hazard Review

## Why

FlowGuard already checks finite model behavior, state closure, tests, and
process evidence. A model can still look locally green while its topology
implies future-use risks that an experienced engineer would notice: repeatable
side effects, broad success states, old/new compatibility paths, external
confirmation boundaries, shared state writers, or parent/child compression.

This change makes that experienced-engineer review automatic and topology
grounded. It must not become a generic checklist of possible risks. A concern
can affect confidence only when it names the concrete state, edge, side effect,
terminal, compatibility path, or boundary that caused the concern.

## What Changes

- Add a public Model Topology Hazard Review helper with topology digest,
  usage intent, hazard candidates, report objects, inference, review logic, and
  a starter template.
- Run the review automatically from `run_model_first_checks(...)` so agents
  do not skip it as an optional AI pack.
- Route unresolved topology hazards to model maturation, model-test alignment,
  DevelopmentProcessFlow, Architecture Reduction, or Risk Evidence Ledger based
  on the hazard disposition.
- Extend maintenance scan and Risk Evidence Ledger so topology-hazard gaps stay
  visible before broad done, release, publish, archive, or full-confidence
  claims.
- Add a directly invokable Codex skill and prompt protocol for topology-based
  future-use risk inference.

## Impact

- New API: `UsageIntent`, `TopologyDigest`, `TopologyNode`, `TopologyEdge`,
  `TopologyLandmark`, `TopologyHazardCandidate`,
  `TopologyHazardReviewPlan`, `TopologyHazardReport`,
  `infer_usage_intent(...)`, `infer_topology_digest(...)`,
  `infer_topology_hazard_plan(...)`, and `review_topology_hazards(...)`.
- Runner summaries gain a `topology_hazard` section.
- Maintenance scan gains `MAINTENANCE_SIGNAL_TOPOLOGY_HAZARD_GAP`.
- Risk Evidence Ledger rows can require a current topology hazard review id.
- Codex skills gain `flowguard-model-topology-hazard-review`.
- Version, local editable install, shadow workspace, installed skills, adoption
  records, local commit, and local tag are synchronized after validation.
