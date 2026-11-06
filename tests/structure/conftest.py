import sys
import textwrap
from pathlib import Path

import pytest

from flowguard.structure import build  # noqa: E402


def write(root: Path, files: dict) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


@pytest.fixture
def repo(tmp_path):
    """A fixture repository under tmp_path/repo and a builder whose store lives outside it."""
    root = tmp_path / "repo"
    root.mkdir()

    class Repo:
        path = root

        def write(self, files: dict) -> None:
            write(root, files)

        def remove(self, rel: str) -> None:
            (root / rel).unlink()

        def build(self):
            return build(root, tmp_path / "store" / "map.sqlite")
    return Repo()
