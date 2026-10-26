import subprocess
import sys
import unittest
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectIntegrationTests(unittest.TestCase):
    def test_pyproject_declares_check_command_wrapper(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn('name = "flowguard"', text)
        self.assertIn("dependencies = []", text)
        self.assertIn('"flowguard*"', text)
        self.assertIn('flowguard = "flowguard.__main__:main"', text)

    def test_import_preflight_command_works_in_this_environment(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import flowguard; print(flowguard.__version__)",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertRegex(completed.stdout.strip(), r"^\d+\.\d+\.\d+$")
        expected = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
        self.assertEqual(expected, completed.stdout.strip())

if __name__ == "__main__":
    unittest.main()
