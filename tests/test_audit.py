import json
import unittest

from flowguard import Invariant, InvariantResult, Workflow
from flowguard.audit import audit_model
from flowguard.checks import cache_matches_source
from flowguard.risk import RiskProfile, SkippedCheck


class GoodBlock:
    name = "GoodBlock"
    reads = ("records",)
    writes = ("records",)

    def apply(self, input_obj, state):
        return ()


class MissingMetadataBlock:
    def apply(self, input_obj, state):
        return ()


class OddMetadataInvariant:
    name = "custom_rule"
    description = "custom rule with malformed metadata"
    metadata = ("not-a-pair",)


def always_ok(state, trace):
    return InvariantResult.pass_()


class ModelQualityAuditTests(unittest.TestCase):
    def test_empty_workflow_is_hard_audit_error(self):
        report = audit_model(workflow=Workflow(()), invariants=(Invariant("ok", "ok", always_ok),))

        self.assertFalse(report.ok)
        self.assertEqual("failed", report.status)
        self.assertIn("workflow_without_blocks", [finding.category for finding in report.findings])
        self.assertIn("ERROR: workflow_without_blocks", report.format_text())

    def test_repeated_input_gaps_are_warnings_not_failures(self):
        report = audit_model(
            workflow=Workflow((GoodBlock(),)),
            invariants=(),
            external_inputs=("job_1",),
            max_sequence_length=1,
            scenarios=(),
            conformance_status="not_run",
            declared_risk_classes=("deduplication", "side_effect"),
        )

        self.assertTrue(report.ok)
        self.assertEqual("pass_with_gaps", report.status)
        categories = [finding.category for finding in report.findings]
        self.assertIn("missing_repeated_input", categories)
        self.assertIn("missing_invariant", categories)
        self.assertIn("missing_conformance", categories)
        self.assertTrue(any("skipped is not pass" in finding.message for finding in report.findings))

    def test_missing_block_metadata_is_warning(self):
        report = audit_model(
            workflow=Workflow((MissingMetadataBlock(),)),
            invariants=(Invariant("hard_property", "hard property", always_ok),),
            external_inputs=("x",),
            scenarios=(object(),),
        )

        self.assertTrue(report.ok)
        self.assertEqual("pass_with_gaps", report.status)
        warnings = [finding for finding in report.findings if finding.severity == "warning"]
        self.assertTrue(any("does not declare reads" in finding.message for finding in warnings))
        self.assertTrue(any("does not declare writes" in finding.message for finding in warnings))

    def test_cache_risk_uses_invariant_name_heuristic(self):
        invariant = cache_matches_source(
            name="cache_matches_source_scores",
            description="cache/source consistency",
            cache_selector=lambda state: (),
            source_selector=lambda state: (),
            key=lambda item: item,
            value=lambda item: item,
        )

        report = audit_model(
            workflow=Workflow((GoodBlock(),)),
            invariants=(invariant,),
            external_inputs=("job_1",),
            max_sequence_length=1,
            scenarios=(object(),),
            declared_risk_classes=("cache",),
            conformance_status="skipped_with_reason",
        )

        self.assertTrue(report.ok)
        self.assertFalse(any("cache risk is declared" in finding.message for finding in report.findings))
        self.assertIn("missing_conformance", [finding.category for finding in report.findings])

    def test_invariant_property_metadata_satisfies_dedup_risk_without_name_guessing(self):
        invariant = Invariant(
            "job_records_are_valid",
            "records have the right shape",
            always_ok,
            metadata={"property_classes": ("deduplication",)},
        )

        report = audit_model(
            workflow=Workflow((GoodBlock(),)),
            invariants=(invariant,),
            external_inputs=("job_1", "job_2"),
            max_sequence_length=2,
            scenarios=(object(),),
            declared_risk_classes=("deduplication",),
        )

        self.assertTrue(report.ok)
        self.assertFalse(
            any(
                finding.category == "missing_invariant"
                and "deduplication risk" in finding.message
                for finding in report.findings
            )
        )

    def test_invariant_name_fallback_still_satisfies_dedup_risk(self):
        invariant = Invariant("no_duplicate_job_records", "records are valid", always_ok)

        report = audit_model(
            workflow=Workflow((GoodBlock(),)),
            invariants=(invariant,),
            external_inputs=("job_1", "job_2"),
            max_sequence_length=2,
            scenarios=(object(),),
            declared_risk_classes=("deduplication",),
        )

        self.assertTrue(report.ok)
        self.assertFalse(
            any(
                finding.category == "missing_invariant"
                and "deduplication risk" in finding.message
                for finding in report.findings
            )
        )

    def test_unknown_invariant_metadata_is_not_a_hard_audit_failure(self):
        invariant = Invariant(
            "custom_rule",
            "domain-specific rule",
            always_ok,
            metadata={"property_classes": ("custom_domain_rule",)},
        )

        report = audit_model(
            workflow=Workflow((GoodBlock(),)),
            invariants=(invariant,),
            external_inputs=("x",),
            scenarios=(object(),),
        )

        self.assertTrue(report.ok)
        self.assertNotIn("failed", report.status)

    def test_malformed_duck_typed_invariant_metadata_is_ignored(self):
        report = audit_model(
            workflow=Workflow((GoodBlock(),)),
            invariants=(OddMetadataInvariant(),),
            external_inputs=("job_1", "job_2"),
            max_sequence_length=2,
            scenarios=(object(),),
            declared_risk_classes=("deduplication",),
        )

        self.assertTrue(report.ok)
        self.assertEqual("pass_with_gaps", report.status)

    def test_suggestions_do_not_change_pass_status(self):
        report = audit_model(
            workflow=Workflow((GoodBlock(),)),
            invariants=(Invariant("hard_property", "hard property", always_ok),),
            external_inputs=("x",),
            max_sequence_length=1,
            scenarios=(object(),),
        )

        self.assertTrue(report.ok)
        self.assertEqual("pass", report.status)
        self.assertEqual(["suggestion"], [finding.severity for finding in report.findings])
        self.assertEqual("pass", json.loads(report.to_json_text())["status"])

    def test_skipped_steps_are_explicit_gaps(self):
        report = audit_model(
            workflow=Workflow((GoodBlock(),)),
            invariants=(Invariant("hard_property", "hard property", always_ok),),
            external_inputs=("x",),
            scenarios=(object(),),
            skipped_steps=("production replay unavailable",),
        )

        self.assertTrue(report.ok)
        self.assertEqual("pass_with_gaps", report.status)
        self.assertTrue(any(finding.category == "skipped_step" for finding in report.findings))

    def test_risk_profile_drives_conformance_and_skipped_gap_warnings(self):
        profile = RiskProfile(
            modeled_boundary="job matching production path",
            risk_classes=("retry", "side_effect", "custom_risk"),
            confidence_goal="production_conformance",
            skipped_checks=(SkippedCheck("conformance_replay", "adapter not written", "not_feasible"),),
        )

        report = audit_model(
            workflow=Workflow((GoodBlock(),)),
            invariants=(Invariant("hard_property", "hard property", always_ok),),
            external_inputs=("job_1",),
            max_sequence_length=1,
            scenarios=(),
            risk_profile=profile,
        )

        self.assertTrue(report.ok)
        self.assertEqual("pass_with_gaps", report.status)
        categories = [finding.category for finding in report.findings]
        self.assertIn("risk_profile_warning", categories)
        self.assertIn("missing_repeated_input", categories)
        self.assertIn("missing_conformance", categories)
        self.assertIn("skipped_step", categories)
        self.assertTrue(any("production confidence goal" in finding.message for finding in report.findings))

    def test_declared_conformance_risk_has_specific_gap_message(self):
        profile = RiskProfile(
            modeled_boundary="helper architecture",
            risk_classes=("conformance",),
            confidence_goal="model_level",
        )

        report = audit_model(
            workflow=Workflow((GoodBlock(),)),
            invariants=(Invariant("hard_property", "hard property", always_ok),),
            external_inputs=("x",),
            scenarios=(object(),),
            risk_profile=profile,
        )

        self.assertTrue(report.ok)
        self.assertEqual("pass_with_gaps", report.status)
        messages = [finding.message for finding in report.findings]
        self.assertTrue(any("declared conformance risk" in message for message in messages))
        self.assertFalse(any("for a production confidence goal" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
