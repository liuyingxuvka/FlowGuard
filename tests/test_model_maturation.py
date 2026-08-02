import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from flowguard import (
    COVERAGE_DISPOSITION_SATISFIED,
    MATURITY_ACTION_ADD_MODEL_OBLIGATION,
    MATURITY_ACTION_ADD_STATE_FIELD,
    MATURITY_ACTION_DOWNGRADE_CLAIM,
    MATURITY_ACTION_REFRESH_EVIDENCE,
    MODEL_MATURATION_DECISION_CLOSED_FOR_TASK,
    MODEL_MATURATION_DECISION_EXTERNAL_INPUT_REQUIRED,
    MODEL_MATURATION_DECISION_ITERATION_LIMIT,
    MODEL_MATURATION_DECISION_PROGRESS_STALLED,
    MODEL_MATURATION_DECISION_SCOPE_EXCLUDED,
    MODEL_MATURATION_DECISION_UPGRADE_REQUIRED,
    MODEL_MATURATION_PLAN_SCHEMA_VERSION,
    MODEL_MATURATION_RECEIPT_STATUS_PASS,
    MODEL_MATURATION_RESOLUTION_EVIDENCE_ACQUISITION,
    MODEL_MATURATION_RESOLUTION_EXTERNAL_INPUT_REQUIRED,
    MODEL_MATURATION_RESOLUTION_MODEL_EDIT,
    MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED,
    MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION,
    MODEL_MATURATION_SIGNAL_STATE_TOO_COARSE,
    ModelMaturationGapResolutionReceipt,
    ModelMaturationCoverageContribution,
    ModelMaturationIntake,
    ModelMaturationPlan,
    ModelMaturationSignal,
    OwnerCoverageResolution,
    ProofArtifactRef,
    compile_model_maturation_plan,
    review_model_maturation_loop,
    review_model_maturation_session,
    CoverageRule,
    TASK_FACT_SOURCE_CURRENT_MODEL,
    TASK_FACT_SOURCE_LIFECYCLE,
    TASK_FACT_SOURCE_PUBLIC_SURFACE,
    TASK_FACT_SOURCE_REQUEST,
    TaskFactSourceSnapshot,
    TaskFacts,
    compile_task_coverage_demand,
)
from flowguard.__main__ import main


def _fingerprint(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _complete_source_snapshots():
    return tuple(
        TaskFactSourceSnapshot(
            source_plane,
            f"artifact:{source_plane}",
            "sha256:" + source_plane.encode("utf-8").hex().ljust(64, "0")[:64],
        )
        for source_plane in (
            TASK_FACT_SOURCE_REQUEST,
            TASK_FACT_SOURCE_CURRENT_MODEL,
            TASK_FACT_SOURCE_PUBLIC_SURFACE,
            TASK_FACT_SOURCE_LIFECYCLE,
        )
    )


def _plan(**overrides):
    strong_material = overrides.pop("_strong_material", True)
    values = {
        "plan_id": "maturation-checkout",
        "task_id": "task-checkout",
        "task_purpose": "predict checkout failure behavior before release",
        "model_id": "checkout",
        "risk_id": "risk-checkout",
        "coverage_universe_id": "checkout-obligations-v1",
        "coverage_demand_fingerprint": "sha256:task-demand",
        "coverage_owner": "existing-model-preflight",
        "coverage_source_refs": ("model:checkout@base-1", "code-map:checkout@code-1"),
        "coverage_ids": ("checkout.failure",),
        "required_probe_ids": ("probe.checkout.failure",),
        "base_model_fingerprint": "model-base-1",
        "candidate_model_fingerprint": "model-candidate-1",
        "evidence_fingerprint": "evidence-1",
    }
    values.update(overrides)
    plan = ModelMaturationPlan(**values)
    if "coverage_universe_fingerprint" not in overrides:
        plan = replace(plan, coverage_universe_fingerprint=plan.expected_coverage_fingerprint())
    if strong_material and plan.coverage_ids:
        resolution = OwnerCoverageResolution(
            "resolution:model-miss-review",
            task_id=plan.task_id,
            demand_id=plan.coverage_universe_id,
            demand_fingerprint=plan.coverage_demand_fingerprint,
            owner_route="model_miss_review",
            disposition=COVERAGE_DISPOSITION_SATISFIED,
            obligation_ids=plan.coverage_ids,
            evidence_ids=("proof:model-miss-review",),
            evidence_fingerprints=("sha256:native-evidence",),
        )
        proof = ProofArtifactRef(
            "proof:model-miss-review",
            producer_route="model_miss_review",
            command="python -m pytest tests/test_model_maturation.py -q",
            result_path="tmp/model-maturation.json",
            result_status="passed",
            exit_code=0,
            started_at="2026-08-02T00:00:00+00:00",
            finished_at="2026-08-02T00:00:01+00:00",
            subject_id=resolution.resolution_id,
            subject_fingerprint=resolution.resolution_fingerprint,
            artifact_fingerprints={"candidate": "sha256:native-evidence"},
            covered_obligation_ids=plan.coverage_ids,
        )
        contribution = ModelMaturationCoverageContribution(
            "contribution:model-miss-review",
            owner_route="model_miss_review",
            task_id=plan.task_id,
            coverage_ids=plan.coverage_ids,
            evidence_ref=proof,
            owner_resolution=resolution,
            candidate_model_fingerprint=plan.candidate_model_fingerprint,
            subject_fingerprints={"candidate": "sha256:native-evidence"},
        )
        plan = replace(
            plan,
            owner_resolution_ids=(resolution.resolution_id,),
            owner_resolution_fingerprints=(resolution.resolution_fingerprint,),
            owner_resolution_owner_ids=(resolution.owner_route,),
            owner_resolution_contributions=(contribution,),
        )
    return plan


def _open_signal(**overrides):
    values = {
        "signal_id": "gap-checkout-failure",
        "signal_type": MODEL_MATURATION_SIGNAL_STATE_TOO_COARSE,
        "source_route": "model_miss_review",
        "coverage_id": "checkout.failure",
        "probe_id": "probe.checkout.failure",
        "resolution_class": MODEL_MATURATION_RESOLUTION_MODEL_EDIT,
        "prediction": "the candidate represents the payment-decline branch",
        "falsifier": "a decline trace reaches an unmodeled state",
        "evidence_id": "trace-decline-1",
        "evidence_fingerprint": "trace-fingerprint-1",
        "current": True,
    }
    values.update(overrides)
    return ModelMaturationSignal(**values)


def _verified_signal(plan, **overrides):
    values = {
        "resolved": True,
        "receipt_id": "receipt-checkout-1",
        "receipt_fingerprint": "receipt-fingerprint-1",
        "receipt_status": MODEL_MATURATION_RECEIPT_STATUS_PASS,
        "receipt_task_id": plan.task_id,
        "receipt_probe_id": "probe.checkout.failure",
        "receipt_candidate_fingerprint": plan.candidate_model_fingerprint,
        "receipt_coverage_fingerprint": plan.coverage_universe_fingerprint,
        "receipt_evidence_fingerprint": "trace-fingerprint-1",
        "receipt_owner_route": "model_miss_review",
    }
    values.update(overrides)
    return _open_signal(**values)


def _gap_receipt(plan, gap, **overrides):
    values = {
        "receipt_id": "gap-receipt-2",
        "receipt_fingerprint": "gap-resolution-receipt-2",
        "gap_fingerprint": gap,
        "task_id": plan.task_id,
        "candidate_fingerprint": plan.candidate_model_fingerprint,
        "coverage_fingerprint": plan.coverage_universe_fingerprint,
        "evidence_fingerprint": plan.evidence_fingerprint,
        "owner_route": "model_miss_review",
        "status": MODEL_MATURATION_RECEIPT_STATUS_PASS,
        "current": True,
    }
    values.update(overrides)
    return ModelMaturationGapResolutionReceipt(**values)


class ModelMaturationTests(unittest.TestCase):
    def _demand(self, *owner_ids):
        rules = tuple(
            CoverageRule(
                f"rule:{owner}",
                owner,
                (f"demand:{owner}",),
                f"{owner} is required by this test task",
                always_for_non_trivial=True,
            )
            for owner in owner_ids
        )
        return compile_task_coverage_demand(
            TaskFacts(
                "task-compile",
                "compile independent pre-code coverage",
                source_snapshots=_complete_source_snapshots(),
            ),
            rules=rules,
        )

    def _contribution(self, contribution_id="requirements", **overrides):
        values = {
            "contribution_id": contribution_id,
            "owner_route": "existing_model_preflight",
            "task_id": "task-compile",
            "coverage_source_refs": ("spec:task-compile",),
            "coverage_ids": ("requirement:submit",),
            "required_probe_ids": ("probe:submit",),
            "subject_fingerprints": {"candidate": "sha256:candidate-compile"},
            "evidence_ref": ProofArtifactRef(
                f"proof:{contribution_id}",
                producer_route="existing_model_preflight",
                command="python -m pytest tests/test_model_maturation.py -q",
                result_path=f"tmp/{contribution_id}.json",
                result_status="passed",
                exit_code=0,
                started_at="2026-08-02T00:00:00+00:00",
                finished_at="2026-08-02T00:00:01+00:00",
                artifact_fingerprints={"candidate": "sha256:candidate-compile"},
                covered_obligation_ids=("requirement:submit",),
            ),
        }
        values.update(overrides)
        return ModelMaturationCoverageContribution(**values)

    def _intake(self, *contributions, **overrides):
        required_owner_ids = overrides.pop(
            "required_owner_ids",
            tuple(dict.fromkeys(item.owner_route for item in contributions)),
        )
        demand = self._demand(*required_owner_ids)
        canonical: list[ModelMaturationCoverageContribution] = []
        for contribution in contributions:
            proof = contribution.evidence_ref
            assert proof is not None
            demanded = tuple(
                coverage_id
                for row in demand.rows
                if row.triggered and row.owner_route == contribution.owner_route
                for coverage_id in row.coverage_ids
            )
            obligations = tuple(dict.fromkeys(contribution.coverage_ids + demanded))
            evidence_fingerprints = tuple(proof.artifact_fingerprints.values())
            resolution = OwnerCoverageResolution(
                f"resolution:{contribution.contribution_id}",
                task_id="task-compile",
                demand_id=demand.demand_id,
                demand_fingerprint=demand.fingerprint,
                owner_route=contribution.owner_route,
                disposition=COVERAGE_DISPOSITION_SATISFIED,
                obligation_ids=obligations,
                evidence_ids=(proof.artifact_id,),
                evidence_fingerprints=evidence_fingerprints,
            )
            canonical_proof = replace(
                proof,
                command=proof.command or "python -m pytest tests/test_model_maturation.py -q",
                result_path=proof.result_path or f"tmp/{contribution.contribution_id}.json",
                started_at=proof.started_at or "2026-08-02T00:00:00+00:00",
                finished_at=proof.finished_at or "2026-08-02T00:00:01+00:00",
                subject_id=resolution.resolution_id,
                subject_fingerprint=resolution.resolution_fingerprint,
                covered_obligation_ids=obligations,
            )
            canonical.append(
                replace(
                    contribution,
                    evidence_ref=canonical_proof,
                    owner_resolution=resolution,
                    candidate_model_fingerprint="candidate-compile",
                    subject_fingerprints=dict(canonical_proof.artifact_fingerprints),
                )
            )
        values = {
            "intake_id": "intake-compile",
            "plan_id": "plan-compile",
            "task_id": "task-compile",
            "task_purpose": "compile independent pre-code coverage",
            "model_id": "submit-model",
            "risk_id": "risk-submit",
            "base_model_fingerprint": "base-compile",
            "candidate_model_fingerprint": "candidate-compile",
            "coverage_demand": demand,
            "contributions": tuple(canonical),
        }
        values.update(overrides)
        return ModelMaturationIntake(**values)

    def test_pre_code_intake_compiles_independent_coverage_and_exact_evidence(self):
        requirement = self._contribution()
        bcl = self._contribution(
            "behavior",
            owner_route="behavior_commitment_ledger",
            coverage_source_refs=("bcl:submit",),
            coverage_ids=("behavior:submit",),
            required_probe_ids=("probe:behavior:submit",),
            evidence_ref=ProofArtifactRef(
                "proof:behavior",
                producer_route="behavior_commitment_ledger",
                result_status="passed",
                exit_code=0,
                artifact_fingerprints={"candidate": "sha256:candidate-compile"},
                covered_obligation_ids=("behavior:submit",),
            ),
        )
        plan = compile_model_maturation_plan(self._intake(requirement, bcl))
        report = review_model_maturation_loop(plan)

        self.assertEqual(
            set(plan.coverage_ids),
            {
                "requirement:submit",
                "behavior:submit",
                "demand:existing_model_preflight",
                "demand:behavior_commitment_ledger",
            },
        )
        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(report.coverage_demand_fingerprint, plan.coverage_demand_fingerprint)
        self.assertEqual(report.candidate_model_fingerprint, "candidate-compile")

    def test_missing_or_stale_contribution_remains_an_open_gap(self):
        for owner in ("behavior", "model_angle", "ui", "field", "test"):
            with self.subTest(owner=owner):
                missing_plan = compile_model_maturation_plan(
                    self._intake(
                        self._contribution(),
                        required_owner_ids=("existing_model_preflight", owner),
                    )
                )
                missing = review_model_maturation_loop(missing_plan)
                self.assertFalse(missing.ok)
                self.assertIn(f"missing-contribution:{owner}", missing_plan.coverage_ids)

        stale = self._contribution(current=False)
        stale_report = review_model_maturation_loop(
            compile_model_maturation_plan(self._intake(stale))
        )
        self.assertFalse(stale_report.ok)
        self.assertIn(
            "model_maturation_signal_stale",
            {finding.code for finding in stale_report.findings},
        )

    def test_low_risk_intake_does_not_invent_untriggered_specialists(self):
        plan = compile_model_maturation_plan(
            self._intake(self._contribution(), required_owner_ids=("existing_model_preflight",))
        )
        self.assertEqual(
            set(plan.coverage_ids),
            {"requirement:submit", "demand:existing_model_preflight"},
        )
        self.assertFalse(any(source.startswith("ui:") for source in plan.coverage_source_refs))

    def test_duplicate_contribution_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            self._intake(self._contribution(), self._contribution())

    def test_empty_legacy_shape_is_blocked_instead_of_current(self):
        report = review_model_maturation_loop(ModelMaturationPlan(plan_id="shallow"))

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)
        self.assertIn("missing_task_id", {finding.code for finding in report.findings})
        self.assertTrue(report.open_gap_fingerprints)

    def test_current_task_closes_only_with_exact_native_receipt(self):
        plan = _plan()
        report = review_model_maturation_loop(replace(plan, signals=(_verified_signal(plan),)))

        self.assertTrue(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_CLOSED_FOR_TASK)
        self.assertEqual(report.terminal_reason, MODEL_MATURATION_DECISION_CLOSED_FOR_TASK)
        self.assertEqual(report.iteration_record.native_receipt_fingerprints, ("receipt-fingerprint-1",))

    def test_raw_hand_filled_signal_cannot_close_broad_maturation(self):
        plan = _plan(_strong_material=False)
        report = review_model_maturation_loop(
            replace(plan, signals=(_verified_signal(plan),))
        )

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)
        self.assertIn(
            "missing_owner_resolution_material",
            {finding.code for finding in report.findings},
        )

    def test_caller_resolved_boolean_is_not_evidence(self):
        plan = _plan()
        signal = _open_signal(resolved=True)
        report = review_model_maturation_loop(replace(plan, signals=(signal,)))

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)
        self.assertEqual(report.terminal_reason, "")
        codes = {finding.code for finding in report.findings}
        self.assertIn("unverified_signal_resolution", codes)
        self.assertIn(MATURITY_ACTION_REFRESH_EVIDENCE, report.recommended_actions)

    def test_wrong_receipt_bindings_cannot_close(self):
        for field, value in (
            ("receipt_task_id", "another-task"),
            ("receipt_probe_id", "another-probe"),
            ("receipt_candidate_fingerprint", "another-candidate"),
            ("receipt_coverage_fingerprint", "another-universe"),
            ("receipt_evidence_fingerprint", "another-evidence"),
            ("receipt_owner_route", "another-owner"),
            ("receipt_status", "failed"),
        ):
            with self.subTest(field=field):
                plan = _plan()
                report = review_model_maturation_loop(
                    replace(plan, signals=(_verified_signal(plan, **{field: value}),))
                )
                self.assertFalse(report.ok)
                self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)

    def test_required_contract_fields_and_independent_coverage_are_enforced(self):
        cases = (
            ("task_purpose", "", "missing_task_purpose"),
            ("coverage_source_refs", (), "missing_coverage_source_refs"),
            ("coverage_ids", (), "missing_coverage_universe"),
            ("required_probe_ids", (), "missing_required_probes"),
        )
        for field, value, expected in cases:
            with self.subTest(field=field):
                plan = _plan(**{field: value})
                report = review_model_maturation_loop(plan)
                self.assertIn(expected, {finding.code for finding in report.findings})
                self.assertFalse(report.ok)

    def test_coverage_inventory_cannot_be_silently_rewritten(self):
        plan = _plan(coverage_universe_fingerprint="caller-kept-old-fingerprint")
        report = review_model_maturation_loop(replace(plan, signals=(_verified_signal(plan),)))

        self.assertFalse(report.ok)
        self.assertIn(
            "coverage_universe_fingerprint_mismatch",
            {finding.code for finding in report.findings},
        )

    def test_every_required_probe_must_have_a_bound_signal(self):
        plan = _plan(required_probe_ids=("probe.checkout.failure", "probe.checkout.timeout"))
        signal = _verified_signal(plan)
        report = review_model_maturation_loop(replace(plan, signals=(signal,)))

        self.assertFalse(report.ok)
        self.assertIn("missing_required_probe_signal", {finding.code for finding in report.findings})

    def test_open_addressable_gap_requires_another_iteration_not_terminal_stop(self):
        plan = _plan(signals=(_open_signal(),))
        report = review_model_maturation_loop(plan)

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)
        self.assertEqual(report.terminal_reason, "")
        self.assertIn(MATURITY_ACTION_ADD_STATE_FIELD, report.recommended_actions)

    def test_external_stop_requires_exact_input_owner_and_claim_boundary(self):
        complete = _open_signal(
            resolution_class=MODEL_MATURATION_RESOLUTION_EXTERNAL_INPUT_REQUIRED,
            required_input="provider decline trace with correlation id",
            owner_boundary="payment-provider",
            affected_claim_scope="provider-decline recovery only",
        )
        report = review_model_maturation_loop(_plan(signals=(complete,)))
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_EXTERNAL_INPUT_REQUIRED)
        self.assertEqual(report.terminal_reason, MODEL_MATURATION_DECISION_EXTERNAL_INPUT_REQUIRED)

        incomplete = replace(complete, owner_boundary="")
        report = review_model_maturation_loop(_plan(signals=(incomplete,)))
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)
        self.assertIn("incomplete_external_input_boundary", {finding.code for finding in report.findings})

    def test_scope_exclusion_is_visible_and_never_full_closure(self):
        signal = _open_signal(
            in_scope=False,
            resolution_class=MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED,
            affected_claim_scope="legacy provider behavior",
        )
        report = review_model_maturation_loop(_plan(signals=(signal,)))

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_SCOPE_EXCLUDED)
        self.assertIn(MATURITY_ACTION_DOWNGRADE_CLAIM, report.recommended_actions)

    def test_prior_gap_cannot_disappear_without_a_resolution_receipt(self):
        first = review_model_maturation_loop(_plan(signals=(_open_signal(),)))
        prior_gap = first.open_gap_fingerprints[0]
        second_plan = _plan(
            iteration=1,
            prior_iteration_fingerprint=first.iteration_record.fingerprint(),
            prior_candidate_fingerprint="model-candidate-1",
            prior_gap_fingerprints=first.open_gap_fingerprints,
            base_model_fingerprint="model-candidate-1",
            candidate_model_fingerprint="model-candidate-2",
            evidence_fingerprint="evidence-2",
        )
        second_signal = _verified_signal(
            second_plan,
            receipt_id="receipt-checkout-2",
            receipt_fingerprint="receipt-fingerprint-2",
        )
        report = review_model_maturation_loop(replace(second_plan, signals=(second_signal,)))

        self.assertFalse(report.ok)
        self.assertIn(prior_gap, report.open_gap_fingerprints)
        self.assertIn("gap_deleted_without_resolution_receipt", {finding.code for finding in report.findings})

    def test_two_iteration_session_preserves_gap_and_closes_with_receipts(self):
        first_plan = _plan(signals=(_open_signal(),))
        first = review_model_maturation_loop(first_plan)
        prior_gap = first.open_gap_fingerprints[0]
        second_plan = _plan(
            iteration=1,
            prior_iteration_fingerprint=first.iteration_record.fingerprint(),
            prior_candidate_fingerprint="model-candidate-1",
            prior_gap_fingerprints=first.open_gap_fingerprints,
            base_model_fingerprint="model-candidate-1",
            candidate_model_fingerprint="model-candidate-2",
            prior_evidence_fingerprint="evidence-1",
            evidence_fingerprint="evidence-2",
        )
        second_plan = replace(
            second_plan,
            resolved_gap_receipts={prior_gap: _gap_receipt(second_plan, prior_gap)},
        )
        second_signal = _verified_signal(
            second_plan,
            receipt_id="receipt-checkout-2",
            receipt_fingerprint="receipt-fingerprint-2",
        )
        second_plan = replace(second_plan, signals=(second_signal,))
        session = review_model_maturation_session((first_plan, second_plan), session_id="session-checkout")

        self.assertTrue(session.closed)
        self.assertEqual(len(session.iterations), 2)
        self.assertIn(prior_gap, session.iterations[1].resolved_gap_fingerprints)

    def test_untyped_or_wrong_gap_resolution_receipt_is_rejected(self):
        first = review_model_maturation_loop(_plan(signals=(_open_signal(),)))
        gap = first.open_gap_fingerprints[0]
        with self.assertRaises(ValueError):
            _plan(resolved_gap_receipts={gap: "caller-says-fixed"})

        second = _plan(
            iteration=1,
            prior_iteration_fingerprint=first.iteration_record.fingerprint(),
            prior_candidate_fingerprint="model-candidate-1",
            prior_gap_fingerprints=first.open_gap_fingerprints,
            base_model_fingerprint="model-candidate-1",
            candidate_model_fingerprint="model-candidate-2",
            evidence_fingerprint="evidence-2",
        )
        wrong = _gap_receipt(second, gap, task_id="another-task")
        signal = _verified_signal(second, receipt_id="receipt-2", receipt_fingerprint="receipt-fp-2")
        report = review_model_maturation_loop(
            replace(second, signals=(signal,), resolved_gap_receipts={gap: wrong})
        )
        self.assertFalse(report.ok)
        self.assertIn("gap_deleted_without_resolution_receipt", {item.code for item in report.findings})

    def test_evidence_acquisition_advances_without_pretending_to_close(self):
        first = review_model_maturation_loop(
            _plan(
                signals=(
                    _open_signal(
                        resolution_class=MODEL_MATURATION_RESOLUTION_EVIDENCE_ACQUISITION,
                    ),
                )
            )
        )
        second = _plan(
            iteration=1,
            prior_iteration_fingerprint=first.iteration_record.fingerprint(),
            prior_candidate_fingerprint="model-candidate-1",
            prior_gap_fingerprints=first.open_gap_fingerprints,
            base_model_fingerprint="model-candidate-1",
            candidate_model_fingerprint="model-candidate-1",
            prior_evidence_fingerprint="evidence-1",
            evidence_fingerprint="evidence-2",
        )
        progress_signal = _verified_signal(
            second,
            resolved=False,
            resolution_class=MODEL_MATURATION_RESOLUTION_EVIDENCE_ACQUISITION,
            evidence_id="trace-2",
            evidence_fingerprint="trace-fingerprint-2",
            receipt_evidence_fingerprint="trace-fingerprint-2",
            receipt_id="progress-receipt-2",
            receipt_fingerprint="progress-receipt-fp-2",
        )
        second = replace(second, signals=(progress_signal,))
        report = review_model_maturation_loop(second)
        self.assertTrue(report.progressed)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)
        self.assertEqual(report.terminal_reason, "")

    def test_introduced_gap_remains_visible_during_candidate_progress(self):
        coverage = ("checkout.failure", "checkout.timeout")
        probes = ("probe.checkout.failure", "probe.checkout.timeout")
        base = _plan(coverage_ids=coverage, required_probe_ids=probes)
        timeout_pass = _verified_signal(
            base,
            signal_id="gap-checkout-timeout",
            coverage_id="checkout.timeout",
            probe_id="probe.checkout.timeout",
            receipt_probe_id="probe.checkout.timeout",
            receipt_id="receipt-timeout-1",
            receipt_fingerprint="receipt-timeout-fp-1",
        )
        first_plan = replace(base, signals=(_open_signal(), timeout_pass))
        first = review_model_maturation_loop(first_plan)
        old_gap = first.open_gap_fingerprints[0]

        second = _plan(
            coverage_ids=coverage,
            required_probe_ids=probes,
            iteration=1,
            prior_iteration_fingerprint=first.iteration_record.fingerprint(),
            prior_candidate_fingerprint="model-candidate-1",
            prior_gap_fingerprints=first.open_gap_fingerprints,
            base_model_fingerprint="model-candidate-1",
            candidate_model_fingerprint="model-candidate-2",
            prior_evidence_fingerprint="evidence-1",
            evidence_fingerprint="evidence-2",
        )
        resolved_failure = _verified_signal(second, receipt_id="receipt-failure-2", receipt_fingerprint="receipt-failure-fp-2")
        new_timeout = _open_signal(
            signal_id="gap-checkout-timeout",
            coverage_id="checkout.timeout",
            probe_id="probe.checkout.timeout",
            prediction="timeout returns to the retryable state",
            falsifier="timeout reaches an absorbing unmodeled state",
            evidence_id="trace-timeout-2",
            evidence_fingerprint="trace-timeout-fp-2",
        )
        second = replace(
            second,
            signals=(resolved_failure, new_timeout),
            resolved_gap_receipts={old_gap: _gap_receipt(second, old_gap)},
        )
        report = review_model_maturation_loop(second)
        self.assertFalse(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)
        self.assertTrue(report.iteration_record.introduced_gap_fingerprints)

    def test_three_iteration_session_closes_only_on_final_candidate(self):
        first_plan = _plan(signals=(_open_signal(),))
        first = review_model_maturation_loop(first_plan)
        gap = first.open_gap_fingerprints[0]
        second_plan = _plan(
            iteration=1,
            prior_iteration_fingerprint=first.iteration_record.fingerprint(),
            prior_candidate_fingerprint="model-candidate-1",
            prior_gap_fingerprints=first.open_gap_fingerprints,
            base_model_fingerprint="model-candidate-1",
            candidate_model_fingerprint="model-candidate-2",
            prior_evidence_fingerprint="evidence-1",
            evidence_fingerprint="evidence-2",
        )
        second_signal = _verified_signal(
            second_plan,
            resolved=False,
            evidence_id="trace-2",
            evidence_fingerprint="trace-fingerprint-2",
            receipt_evidence_fingerprint="trace-fingerprint-2",
            receipt_id="progress-receipt-2",
            receipt_fingerprint="progress-receipt-fp-2",
        )
        second_plan = replace(second_plan, signals=(second_signal,))
        second = review_model_maturation_loop(second_plan)
        third_plan = _plan(
            iteration=2,
            prior_iteration_fingerprint=second.iteration_record.fingerprint(),
            prior_candidate_fingerprint="model-candidate-2",
            prior_gap_fingerprints=second.open_gap_fingerprints,
            base_model_fingerprint="model-candidate-2",
            candidate_model_fingerprint="model-candidate-3",
            prior_evidence_fingerprint="evidence-2",
            evidence_fingerprint="evidence-3",
        )
        third_signal = _verified_signal(
            third_plan,
            evidence_id="trace-3",
            evidence_fingerprint="trace-fingerprint-3",
            receipt_evidence_fingerprint="trace-fingerprint-3",
            receipt_id="receipt-3",
            receipt_fingerprint="receipt-fp-3",
        )
        third_plan = replace(
            third_plan,
            signals=(third_signal,),
            resolved_gap_receipts={gap: _gap_receipt(third_plan, gap)},
        )
        session = review_model_maturation_session((first_plan, second_plan, third_plan))
        self.assertTrue(session.closed)
        self.assertEqual(len(session.iterations), 3)

    def test_session_rejects_predecessor_or_model_chain_mismatch(self):
        first_plan = _plan(signals=(_open_signal(),))
        first = review_model_maturation_loop(first_plan)
        second = _plan(
            iteration=1,
            prior_iteration_fingerprint="wrong-predecessor",
            prior_candidate_fingerprint="model-candidate-1",
            prior_gap_fingerprints=first.open_gap_fingerprints,
            base_model_fingerprint="wrong-base",
            candidate_model_fingerprint="model-candidate-2",
            signals=(_open_signal(),),
        )
        session = review_model_maturation_session((first_plan, second))

        self.assertFalse(session.closed)
        self.assertIn("session_predecessor_mismatch", {finding.code for finding in session.findings})

    def test_session_rejects_task_purpose_drift(self):
        first_plan = _plan(signals=(_open_signal(),))
        first = review_model_maturation_loop(first_plan)
        second = _plan(
            task_purpose="a different task was substituted",
            iteration=1,
            prior_iteration_fingerprint=first.iteration_record.fingerprint(),
            prior_candidate_fingerprint="model-candidate-1",
            prior_gap_fingerprints=first.open_gap_fingerprints,
            base_model_fingerprint="model-candidate-1",
            candidate_model_fingerprint="model-candidate-2",
            signals=(_open_signal(),),
        )
        session = review_model_maturation_session((first_plan, second))
        self.assertIn("session_identity_mismatch", {finding.code for finding in session.findings})

    def test_no_progress_and_iteration_limit_are_terminal(self):
        first = review_model_maturation_loop(_plan(signals=(_open_signal(),)))
        common = {
            "iteration": 1,
            "prior_iteration_fingerprint": first.iteration_record.fingerprint(),
            "prior_candidate_fingerprint": "model-candidate-1",
            "prior_gap_fingerprints": first.open_gap_fingerprints,
            "base_model_fingerprint": "model-candidate-1",
            "candidate_model_fingerprint": "model-candidate-1",
            "prior_evidence_fingerprint": "evidence-1",
            "evidence_fingerprint": "evidence-1",
            "signals": (_open_signal(),),
        }
        stalled = review_model_maturation_loop(_plan(**common))
        self.assertEqual(stalled.decision, MODEL_MATURATION_DECISION_PROGRESS_STALLED)
        self.assertEqual(stalled.terminal_reason, MODEL_MATURATION_DECISION_PROGRESS_STALLED)

        limited = review_model_maturation_loop(_plan(**{**common, "max_iterations": 1}))
        self.assertEqual(limited.decision, MODEL_MATURATION_DECISION_ITERATION_LIMIT)

    def test_repeated_candidate_evidence_and_gap_state_is_oscillation(self):
        first = review_model_maturation_loop(_plan(signals=(_open_signal(),)))
        repeated_state = _fingerprint(
            {
                "candidate": "model-candidate-1",
                "evidence": "evidence-1",
                "open_gaps": sorted(first.open_gap_fingerprints),
            }
        )
        report = review_model_maturation_loop(
            _plan(
                iteration=1,
                prior_iteration_fingerprint=first.iteration_record.fingerprint(),
                prior_candidate_fingerprint="model-candidate-1",
                prior_gap_fingerprints=first.open_gap_fingerprints,
                prior_state_fingerprints=(repeated_state,),
                base_model_fingerprint="model-candidate-1",
                candidate_model_fingerprint="model-candidate-1",
                prior_evidence_fingerprint="evidence-1",
                evidence_fingerprint="evidence-1",
                signals=(_open_signal(),),
            )
        )
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_PROGRESS_STALLED)
        self.assertIn("model_maturation_oscillation", {item.code for item in report.findings})

    def test_self_reported_understanding_is_rejected(self):
        report = review_model_maturation_loop(
            _plan(signals=(_open_signal(metadata={"understood": True, "understanding_level": "deep"}),))
        )
        self.assertIn("self_report_not_evidence", {finding.code for finding in report.findings})
        self.assertIn(MATURITY_ACTION_ADD_MODEL_OBLIGATION, report.recommended_actions)

    def test_gap_identity_does_not_change_when_evidence_changes(self):
        before = _open_signal(evidence_id="trace-1", evidence_fingerprint="evidence-1")
        after = replace(before, evidence_id="trace-2", evidence_fingerprint="evidence-2")
        self.assertEqual(before.gap_fingerprint(), after.gap_fingerprint())

    def test_current_schema_round_trips_and_former_payload_is_rejected(self):
        plan = _plan(signals=(_open_signal(),))
        self.assertEqual(ModelMaturationPlan.from_dict(plan.to_dict()), plan)
        former = dict(plan.to_dict())
        former.pop("schema_version")
        with self.assertRaises(ValueError):
            ModelMaturationPlan.from_dict(former)
        disguised_former = dict(plan.to_dict())
        disguised_former["claim_scope"] = "full"
        with self.assertRaises(ValueError):
            ModelMaturationPlan.from_dict(disguised_former)

    def test_resolution_class_cannot_hide_in_metadata(self):
        report = review_model_maturation_loop(
            _plan(
                signals=(
                    _open_signal(
                        resolution_class="",
                        metadata={"resolution_class": MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED},
                    ),
                )
            )
        )
        self.assertIn("invalid_resolution_class", {item.code for item in report.findings})
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)

    def test_cli_reports_current_result_and_rejects_old_payload(self):
        plan = _plan()
        plan = replace(plan, signals=(_verified_signal(plan),))
        with tempfile.TemporaryDirectory() as tmp:
            current_path = Path(tmp) / "current.json"
            current_path.write_text(json.dumps(plan.to_dict()), encoding="utf-8")
            self.assertEqual(main(["model-maturation-review", "--plan", str(current_path), "--json"]), 0)

            old_path = Path(tmp) / "old.json"
            old_path.write_text(json.dumps({"plan_id": "old"}), encoding="utf-8")
            self.assertEqual(main(["model-maturation-review", "--plan", str(old_path), "--json"]), 1)

    def test_signal_can_override_the_default_model_action(self):
        report = review_model_maturation_loop(
            _plan(
                signals=(
                    _open_signal(
                        signal_type=MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION,
                        suggested_actions=(MATURITY_ACTION_ADD_STATE_FIELD,),
                    ),
                )
            )
        )
        self.assertIn(MATURITY_ACTION_ADD_STATE_FIELD, report.recommended_actions)

    def test_coverage_fingerprint_helper_matches_runtime_contract(self):
        plan = _plan()
        expected = _fingerprint(
            {
                "coverage_universe_id": plan.coverage_universe_id,
                "coverage_demand_fingerprint": plan.coverage_demand_fingerprint,
                "coverage_owner": plan.coverage_owner,
                "coverage_source_refs": list(plan.coverage_source_refs),
                "coverage_ids": list(plan.coverage_ids),
                "required_probe_ids": list(plan.required_probe_ids),
            }
        )
        self.assertEqual(plan.coverage_universe_fingerprint, expected)


if __name__ == "__main__":
    unittest.main()
