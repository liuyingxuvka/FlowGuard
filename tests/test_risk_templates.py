import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flowguard.risk_templates import (
    TEMPLATE_LIBRARY_ENV_VAR,
    MinimumModelContract,
    RiskTemplate,
    TemplateReuseReview,
    builtin_risk_templates,
    default_local_template_library_root,
    harvest_risk_template_candidate,
    load_local_risk_templates,
    merge_risk_templates,
    review_minimum_model_contract,
    search_risk_templates,
    write_local_risk_template,
)


class RiskTemplateTests(unittest.TestCase):
    def test_builtin_templates_are_public_and_portable(self):
        templates = builtin_risk_templates()

        self.assertTrue(templates)
        self.assertIn("completion_requires_evidence", {template.template_id for template in templates})
        combined = json.dumps([template.to_dict() for template in templates])
        self.assertNotIn("C:\\Users", combined)
        self.assertTrue(all(template.source == "public" for template in templates))

    def test_default_root_uses_env_override(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {TEMPLATE_LIBRARY_ENV_VAR: directory}):
                self.assertEqual(Path(directory), default_local_template_library_root())

    def test_search_uses_public_and_local_layers(self):
        with tempfile.TemporaryDirectory() as directory:
            write_local_risk_template(
                RiskTemplate(
                    "local-completion-proof",
                    "Local completion proof",
                    workflow_families=("task",),
                    protected_error_classes=("premature_completion",),
                    required_state=("completed",),
                    required_evidence=("local_receipt",),
                    known_bad_cases=("local_ack_only",),
                    source="local",
                    status="candidate",
                ),
                root=directory,
            )

            report = search_risk_templates(
                "completion evidence",
                protected_error_classes=("premature_completion",),
                local_root=directory,
            )

        self.assertTrue(report.ok, report.format_text())
        self.assertIn("public", report.searched_layers)
        self.assertIn("local", report.searched_layers)
        self.assertTrue(any(match.layer == "local" for match in report.matches))
        self.assertTrue(any(match.layer == "public" for match in report.matches))

    def test_harvest_candidate_requires_minimum_fields(self):
        blocked = harvest_risk_template_candidate(
            template_id="too-thin",
            title="Too thin",
            protected_error_classes=("premature_completion",),
            write=False,
        )

        self.assertFalse(blocked.ok)
        self.assertIn("missing_completion_evidence", blocked.findings)
        self.assertIn("missing_known_bad_case", blocked.findings)

    def test_harvest_candidate_writes_and_loads_local_card(self):
        with tempfile.TemporaryDirectory() as directory:
            report = harvest_risk_template_candidate(
                template_id="completion-proof",
                title="Completion proof",
                protected_error_classes=("premature_completion",),
                required_state=("completed",),
                required_evidence=("receipt",),
                known_bad_cases=("ack_without_receipt",),
                local_root=directory,
            )
            loaded = load_local_risk_templates(directory)

        self.assertTrue(report.ok, report.format_text())
        self.assertTrue(report.path)
        self.assertEqual(("completion-proof",), tuple(template.template_id for template in loaded))
        self.assertEqual("candidate", loaded[0].status)

    def test_minimum_model_review_reports_missing_teeth(self):
        report = review_minimum_model_contract(
            MinimumModelContract(protected_error_classes=("premature_completion",)),
            template_reuse_review=TemplateReuseReview(no_match_reason="no similar template yet", searched_layers=("public", "local")),
        )

        self.assertEqual("pass_with_gaps", report.status)
        self.assertIn("missing_completion_evidence", report.findings)
        self.assertIn("missing_known_bad_case", report.findings)

    def test_minimum_model_review_passes_with_template_reuse(self):
        report = review_minimum_model_contract(
            MinimumModelContract(
                protected_error_classes=("premature_completion",),
                modeled_state=("completed",),
                modeled_side_effects=("write",),
                completion_evidence=("receipt",),
                known_bad_cases=("ack_without_receipt",),
            ),
            template_reuse_review=TemplateReuseReview(
                used_template_ids=("completion_requires_evidence",),
                searched_layers=("public", "local"),
            ),
        )

        self.assertEqual("pass", report.status)
        self.assertFalse(report.findings)

    def test_merge_keeps_known_bad_cases_and_sources(self):
        left = RiskTemplate(
            "left",
            "Left",
            protected_error_classes=("premature_completion",),
            required_state=("completed",),
            required_evidence=("receipt",),
            known_bad_cases=("ack_only",),
            merge_keys=("completion",),
        )
        right = RiskTemplate(
            "right",
            "Right",
            protected_error_classes=("premature_completion",),
            required_state=("done",),
            required_evidence=("artifact",),
            known_bad_cases=("no_artifact",),
            merge_keys=("completion",),
        )

        merged = merge_risk_templates((left, right), template_id="merged")

        self.assertEqual("merged", merged.template_id)
        self.assertIn("ack_only", merged.known_bad_cases)
        self.assertIn("no_artifact", merged.known_bad_cases)
        self.assertIn("left", merged.source_template_ids)
        self.assertIn("right", merged.source_template_ids)


if __name__ == "__main__":
    unittest.main()
