from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"
BLUEPRINT_DOC = ROOT / "docs" / "implementation_blueprint.md"


def test_blueprint_document_explains_the_complete_claim_boundary_in_plain_language():
    text = BLUEPRINT_DOC.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    for phrase in (
        "independent implementation inventory",
        "Bind The Model And The Code In Both Directions",
        "source-independent semantic references",
        "applicable oracles",
        "BehaviorBlockContract",
        "input, state, output, effect, error, decision, order, retry, timeout, and completion",
        "StaticBlueprintReadinessReport",
        "ModelTestAlignmentReport",
        "AffectedBlueprintNeighborhood",
        "build, runtime, dependency, configuration, schema, data, asset, migration",
        "Test/checker execution remains a separate receipt-backed status",
        "Ordinary Tasks Stay Affected-Only",
        "parent/child output-to-input relations",
        "twenty project-specialized projection kinds preserve",
        "same envelope and materialization kernel",
        "Export completion means only that this exact snapshot was materialized",
        "safe_by_equivalence",
        "safe_by_public_facade",
    ):
        assert phrase in normalized


def test_blueprint_document_names_current_whole_affected_and_project_cli_entries():
    text = BLUEPRINT_DOC.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    commands = (
        "python -m flowguard target-system-blueprint-audit",
        "python -m flowguard target-system-blueprint-export",
        "python -m flowguard affected-blueprint-understanding",
        "python -m flowguard project-blueprint-audit",
        "python -m flowguard flowguard-self-blueprint-check",
        "python -m flowguard project-blueprint-candidate",
        "python -m flowguard flowguard-self-architecture-reduction-review",
        "python -m flowguard implementation-inventory-audit",
        "python -m flowguard project-blueprint-export",
    )

    for command in commands:
        assert text.count(command) == 1
    assert "callers do not submit their own pass rows" in normalized
    assert (
        "propagated parent/child, producer-consumer, delegation, support, "
        "or sibling impact"
        in normalized
    )
    assert "model-blueprint-check" not in text
    assert "model-blueprint-export" not in text
    assert "--require-reconstruction" not in text
    assert text.count("--inventory implementation-inventory.json") == 2
    assert "--output exported-blueprint" in text


def test_readme_links_the_blueprint_in_both_language_sections():
    text = README.read_text(encoding="utf-8")

    assert text.count("docs/implementation_blueprint.md") >= 4
    assert "parent/child output-to-input relations" in text
    assert "test design stays" in text
    assert "测试设计是否齐全" in text


def test_readme_keeps_one_direct_first_v5_bootstrap_sequence():
    text = README.read_text(encoding="utf-8")
    bootstrap_command = (
        "python -m flowguard model-revision-intent-bootstrap --root . "
        "--model-parent-receipt <model-parent.json> "
        "--native-owner-evidence <owner-evidence.json>"
    )
    owner_evidence_command = (
        "python -m flowguard model-revision-owner-evidence --root . "
        "--model-parent-receipt <model-parent.json>"
    )

    assert text.count(bootstrap_command) == 2
    assert text.count(owner_evidence_command) == 2
    assert text.index(owner_evidence_command) < text.index(bootstrap_command)
    assert (
        "model-revision-intent-bootstrap --root . --model-parent-receipt "
        "<model-parent.json> --revision-set-id"
        not in text
    )


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
