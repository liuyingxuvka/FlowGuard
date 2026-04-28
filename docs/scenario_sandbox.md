# Scenario Sandbox

The scenario sandbox is a deterministic review layer over flowguard models. It answers a different question from normal unit tests:

```text
For a human-designed scenario, did flowguard observe what we expected?
```

It is meant to validate whether the model and checks catch workflow bugs that AI coding agents often introduce: repeated side effects, missing deduplication, stale cache behavior, contradictory decisions, wrong state ownership, downstream type mismatch, and invalid starting state.

## Scenario

A `Scenario` is one exact test condition:

- `name`
- `description`
- `initial_state`
- `external_input_sequence`
- `tags`
- `expected`
- `notes`

The input sequence is exact and deterministic. It can be empty, single input, repeated input, or mixed repeated input:

```text
[job_A]
[job_A, job_A]
[job_A, job_B, job_A]
[]
```

The sandbox does not generate random data.

## Human Oracle

`ScenarioExpectation` records what a human expects before execution:

- expected status: `ok`, `violation`, `expected_violation`, `needs_human_review`, or `known_limitation`;
- expected violation names;
- required trace labels;
- forbidden trace labels;
- required evidence;
- optional custom oracle checks.

Custom checks inspect the structured `ScenarioRun`. They are useful for scenario-specific rules that are not global invariants, such as:

- low-score jobs must not create application records;
- `ScoreJob` must not write `application_records`;
- `ScoredJob.score_bucket` must match `score_cache[job_id]`;
- duplicate identical decisions are not acceptable.

## Expected vs Observed

The review result places expectation and observation side by side:

```text
Scenario: S04_high_same_job_twice
Expected: OK; no duplicate record; no repeated scoring
Observed: OK
Status: PASS
Evidence:
  - score_attempts[job_high_A] == 1
  - application_records[job_high_A] <= 1
  - observed labels: score_cached,record_already_exists
```

For broken models, an expected violation is a successful review outcome:

```text
Scenario: B01_broken_duplicate_record_repeated_high
Expected: VIOLATION no_duplicate_application_records
Observed: VIOLATION no_duplicate_application_records
Status: EXPECTED_VIOLATION_OBSERVED
```

This is the main difference from ordinary unit tests. The sandbox checks whether the model caught the expected bug.

## Status Values

- `pass`: expected OK and observed OK.
- `expected_violation_observed`: the scenario expected a violation and flowguard observed it.
- `unexpected_violation`: expected OK but observed a model violation, dead branch, or exception.
- `missing_expected_violation`: expected a violation but observed OK.
- `oracle_mismatch`: model status is not enough to satisfy the human oracle, such as missing labels or failed custom evidence.
- `needs_human_review`: current model intentionally does not claim the scenario is fully validated.
- `known_limitation`: current algorithm cannot prove or disprove the desired property honestly.

## Why Needs Human Review Is Valid

Some scenarios expose policy gaps. In job matching, the same `job_id` may arrive with conflicting features. The current model treats `job_id` as identity and uses cached score, but it does not explicitly model conflict detection. That scenario is marked `needs_human_review` rather than pretending the behavior is fully proven.

## Repeated Input Scenarios

Repeated input is essential for idempotency:

- same high job twice;
- same low job twice;
- same medium job twice;
- A/B/A order;
- triple repeated high job.

These scenarios verify that scoring is cached, records are deduplicated, and repeated decisions do not contradict earlier decisions.

## Broken Model Scenarios

The job-matching catalog includes broken variants for:

- duplicate application records;
- repeated scoring;
- low-score jobs being recorded;
- contradictory decisions;
- missing decisions after records;
- non-consumable downstream output;
- score output not cached;
- cache mismatch;
- wrong state owner;
- duplicate decisions;
- ignore-after-apply conflict;
- record without source score;
- bad projection anti-pattern.

## Avoiding Ordinary Unit Test Drift

Scenario review should not reduce to `assert report.ok`. It should assert structured review statuses and evidence:

- expected violation observed;
- missing expected violation;
- unexpected violation;
- oracle mismatch;
- needs human review;
- known limitation.

The output is human-readable, but the report is structured and testable with `to_dict()` and `to_json_text()`.
