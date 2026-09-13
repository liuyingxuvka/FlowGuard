## Purpose

Provide portable, privacy-neutral branch knowledge that a target author can
select by exact facts and then close explicitly without inheriting another
project's model, evidence, or private provenance.

## ADDED Requirements

### Requirement: A seed has four explicit layers

A packaged template seed MUST declare a stable template ID, route IDs,
`route_scaffold`, `reusable_branch_seed`, `operator_guide`, and
`flowguard_self_model` layers. The branch layer MUST also declare exact
applicability predicates, protected error classes, required states, required
side effects, completion evidence, positive cases, known-bad cases,
false-friend cases, target fields, a non-applicable disposition, source proof
references, privacy disposition, and promotion status.

#### Scenario: Complete packaged seed is loaded

- **WHEN** a seed contains all four layers and each required branch field
  contains a non-empty value
- **THEN** the seed is eligible for exact selection

#### Scenario: Incomplete seed is encountered

- **WHEN** a seed lacks an applicability predicate, known-bad proof, or
  promotion status
- **THEN** loading blocks with a typed missing-seed-field finding

### Requirement: Selection requires exact target facts

Selection MUST compare a complete target `TaskFacts` record against every
declared predicate. A fuzzy keyword match, unknown route, or more than one
matching seed MUST never apply a seed; it MUST return a blocker and zero
selected branches.

#### Scenario: One exact route matches

- **WHEN** all required facts match exactly one promoted seed
- **THEN** the result contains that seed ID, a compact branch skeleton, and
  its required tests with `disposition=pending`

#### Scenario: Unknown or ambiguous route is requested

- **WHEN** no seed or multiple seeds match the facts
- **THEN** selection is blocked and no seed is applied

### Requirement: Pending branches require target-owned closure

Every selected pending branch MUST be resolved by the target author as either
`modeled` or `not_applicable`. The latter MUST include a current proof. A
runner MUST block while any selected branch remains pending or lacks current
proof; a seed receipt MUST NOT stand in for a target model, test, release, or
installation receipt.

#### Scenario: Target closes a modeled branch

- **WHEN** the target records the selected seed ID, target artifact, required
  checks, and current completion evidence
- **THEN** the branch becomes modeled and can participate in closure

#### Scenario: Target omits a selected branch

- **WHEN** a selected branch remains pending or has an unproved N/A
  disposition
- **THEN** the target runner blocks with pending-branch findings

### Requirement: Local candidates and private provenance stay outside runtime authority

Local harvest output MUST remain a candidate until it is reviewed and promoted
into a portable packaged seed. Consumer projections MUST omit source-project
paths, customer names, private values, SkillGuard/FlowGuard self-owner IDs, and
private receipts. Predictive-KB recommendations MAY suggest a candidate but
MUST NOT apply or authorize it.

#### Scenario: Candidate is found locally

- **WHEN** a local candidate is returned by harvest or search
- **THEN** it is recommendation-only and cannot be selected as a packaged seed

#### Scenario: Private field appears in a seed projection

- **WHEN** a candidate contains a local path or private provenance field
- **THEN** promotion blocks with a privacy finding and emits no consumer seed
