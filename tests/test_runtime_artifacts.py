import pytest

from flowguard.runtime_artifacts import classify_runtime_artifact


def test_author_request_is_an_exact_runtime_prefix():
    prefix = ".agents/skills/flowguard/.skillguard/"
    request = classify_runtime_artifact(prefix + "runtime-requests/full-author-assurance/run.json")
    assert request is not None and request.non_authority
    for source in (
        "skill_contract.json", "compiled-checks.json", "check-manifest.json",
        "runtime-requests/full-author-assurance-extra/run.json", "runtime-requests/other/run.json",
    ):
        assert classify_runtime_artifact(prefix + source) is None
    assert classify_runtime_artifact(".agents/skills/other/.skillguard/runtime-requests/full-author-assurance/run.json") is None


def test_author_request_classification_never_normalizes_parent_escape():
    with pytest.raises(ValueError, match="safe repository-relative"):
        classify_runtime_artifact(".agents/skills/flowguard/.skillguard/runtime-requests/full-author-assurance/../skill_contract.json")
