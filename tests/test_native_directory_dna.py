"""The repository's native model directory is the only FlowGuard DNA carrier."""

import pytest

from flowguard.__main__ import main


@pytest.mark.parametrize(
    "command",
    (
        "flowguard-self-blueprint-portable-export",
        "flowguard-self-blueprint-directory-export",
        "project-blueprint-export",
        "project-blueprint-portable-export",
        "target-system-blueprint-export",
        "portable-blueprint-verify",
        "portable-blueprint-directory-verify",
    ),
)
def test_standalone_dna_routes_are_retired(command):
    with pytest.raises(SystemExit):
        main([command])


def test_portable_blueprint_module_is_not_a_public_authority():
    with pytest.raises(ModuleNotFoundError):
        __import__("flowguard.portable_blueprint")
