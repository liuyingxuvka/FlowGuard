"""The repository's native model directory is the only FlowGuard DNA carrier."""

import pytest

from flowguard.__main__ import main


def test_standalone_dna_routes_are_absent_from_the_current_cli(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    help_text = capsys.readouterr().out
    for retired in (
        "flowguard-self-blueprint-portable-export",
        "flowguard-self-blueprint-directory-export",
        "project-blueprint-export",
        "project-blueprint-portable-export",
        "portable-blueprint-verify",
        "portable-blueprint-directory-verify",
    ):
        assert retired not in help_text
    assert "flowguard-self-blueprint-check" in help_text


def test_portable_blueprint_module_is_not_a_public_authority():
    with pytest.raises(ModuleNotFoundError):
        __import__("flowguard.portable_blueprint")
