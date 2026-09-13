from __future__ import annotations

from pathlib import Path

from flowguard.model_path_quality import PathQualityResult
from flowguard.self_path_quality import (
    _augment_provider_gaps,
    _runner_called_owner_symbols,
)


def test_module_level_main_guard_is_projected_as_native_entrypoint(tmp_path: Path) -> None:
    runner = tmp_path / "run_checks.py"
    runner.write_text(
        "\n".join(
            (
                "from package import emit_runner",
                "import package.runtime as runtime",
                "",
                "def run_owner():",
                "    return runtime.execute()",
                "",
                "if __name__ == \"__main__\":",
                "    raise SystemExit(emit_runner(\"owner\", run_owner()))",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    assert _runner_called_owner_symbols(runner) == (
        "package.runtime:execute",
        "package:emit_runner",
    )


def test_provider_gap_promotes_triggered_result_to_deep_required() -> None:
    fingerprint = "sha256:" + ("a" * 64)
    result = PathQualityResult(
        result_id="path-quality:fixture",
        subject_fingerprint=fingerprint,
        mode="lightweight",
        trigger_ids=(),
        finding_ids=(),
        candidate_ids=(),
        rewrite_rule_ids=(),
        conclusion="single_clear_path",
        unresolved_ids=(),
        selected_candidate_id="",
        selected_candidate_lane="",
        comparison_boundary_id="",
        candidate_set_fingerprint="",
        rewrite_set_fingerprint="",
        necessity_witness_set_fingerprint=fingerprint,
        detail_evidence_fingerprint=fingerprint,
        producer_id="fixture",
        currentness_id="fixture-current",
    )

    augmented = _augment_provider_gaps(result, ("provider_gap",))

    assert augmented.conclusion == "unresolved"
    assert augmented.trigger_ids == ("missing_necessity_witness",)
    assert augmented.optimization_depth == "deep_required"
    assert augmented.unresolved_ids == ("provider_gap:provider_gap",)
