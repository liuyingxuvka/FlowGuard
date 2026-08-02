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
        "build, runtime, dependency, configuration, schema, data, asset, migration",
        "static_status=complete",
        "empirical_status=not_run",
        "blueprint complete; reconstruction not verified",
        "Ordinary Tasks Stay Affected-Only",
        "never launches reconstruction",
        "safe_by_equivalence",
        "safe_by_public_facade",
    ):
        assert phrase in normalized


def test_blueprint_document_names_exactly_the_four_current_cli_entries():
    text = BLUEPRINT_DOC.read_text(encoding="utf-8")
    commands = (
        "python -m flowguard flowguard-self-blueprint-check",
        "python -m flowguard implementation-inventory-audit",
        "python -m flowguard model-blueprint-check",
        "python -m flowguard model-blueprint-export",
    )

    for command in commands:
        assert text.count(command) == 1
    assert "--require-reconstruction" in text
    assert text.count("--inventory implementation-inventory.json") == 3
    assert "--output exported-blueprint" in text


def test_readme_links_the_blueprint_in_both_language_sections():
    text = README.read_text(encoding="utf-8")

    assert text.count("docs/implementation_blueprint.md") >= 4
    assert "Static `complete` and reconstruction `not_run` remain separate" in text
    assert "静态\n`complete` 和重建 `not_run` 永远分开" in text


def test_patch_release_notes_include_blueprint_without_claiming_automatic_rebuild():
    text = CHANGELOG.read_text(encoding="utf-8")
    release = text.split("## v0.68.5 - 2026-08-02", 1)[1].split("## v0.68.4", 1)[0]

    assert "independent implementation and reconstruction-resource inventory" in release
    assert "Static completion" in release
    assert "affected-only" in release
    assert "no blueprint command launches reconstruction automatically" in release
    assert "current equivalence evidence" in release
