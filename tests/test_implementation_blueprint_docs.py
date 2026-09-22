from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README_EN = ROOT / "README.md"
README_ZH = ROOT / "README.zh-CN.md"
CHANGELOG = ROOT / "CHANGELOG.md"
BLUEPRINT_DOC = ROOT / "docs" / "implementation_blueprint.md"


def test_blueprint_document_explains_the_complete_claim_boundary_in_plain_language():
    text = BLUEPRINT_DOC.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    for phrase in (
        "independent implementation inventory",
        "bind both directions",
        "independent semantic references and applicable oracles",
        "BehaviorBlockContract",
        "input, state, output, effect, error, decision, order, retry, timeout, and completion",
        "StaticBlueprintReadinessReport",
        "ModelTestAlignmentReport",
        "affected owner neighborhood",
        "build, runtime, dependency, configuration, schema, data, asset, migration",
        "Test/checker execution is a separate receipt-backed status",
        "Ordinary maintenance reads only",
        "parent/child output-to-input relations",
        "native model directory",
        "safe_by_equivalence",
        "safe_by_public_facade",
    ):
        assert phrase in normalized


def test_blueprint_document_names_current_whole_affected_and_project_cli_entries():
    text = BLUEPRINT_DOC.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    assert "python -m flowguard read --root <project-root> --request read.json --json" in text
    assert "python -m flowguard change --root <project-root> --request change.json --json" in text
    assert "python -m flowguard release --root <project-root> --request release.json --json" in text
    assert "The public command surface is deliberately limited to `read`, `change`, and `release`" in normalized
    assert "callers do not submit their own pass rows" not in normalized
    assert "affected owner neighborhood" in normalized
    assert "target-system-blueprint-audit" not in text
    assert "project-blueprint-audit" not in text
    assert "flowguard-self-blueprint-check" not in text
    assert "implementation-inventory-audit" not in text


def test_readme_links_the_blueprint_in_both_language_sections():
    english = README_EN.read_text(encoding="utf-8")
    chinese = README_ZH.read_text(encoding="utf-8")

    assert english.count("docs/implementation_blueprint.md") >= 2
    assert chinese.count("docs/implementation_blueprint.md") >= 2
    assert "parent/child output-to-input relations" in english
    assert "test design stays" in english
    assert "测试设计是否齐全" in chinese


def test_readme_keeps_one_direct_first_v5_bootstrap_sequence():
    for readme in (README_EN, README_ZH):
        text = readme.read_text(encoding="utf-8")
        assert "read" in text and "change" in text and "release" in text
        assert "model-revision-intent-bootstrap" not in text
        assert "model-revision-owner-evidence" not in text


def test_patch_release_notes_include_blueprint_depth_and_exact_bindings():
    text = CHANGELOG.read_text(encoding="utf-8")
    release = text.split("## v0.68.7 - ", 1)[1].split("## v0.68.6", 1)[0]
    release_text = " ".join(release.split())

    assert "provider-neutral target blueprint" in release_text
    assert "twenty content-addressed layers" in release_text
    assert "Separated export completion from model completeness" in release_text
    assert "parent/child topology" in release_text
    assert "content-addressed affected reader" in release_text
    assert "supervised validation publication" in release_text
    assert "old public pass-receipt saver was removed" in release_text
