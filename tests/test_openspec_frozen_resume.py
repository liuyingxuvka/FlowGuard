import os
import shutil
import subprocess
import unittest


def _run_openspec(*args: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("openspec")
    if not executable:
        raise unittest.SkipTest("OpenSpec CLI is not installed")
    environment = dict(os.environ)
    environment["OPENSPEC_TELEMETRY"] = "0"
    completed = subprocess.run(
        [executable, *args],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    return completed


class OpenSpecOfficialCliCompatibilityTests(unittest.TestCase):
    def test_official_cli_exposes_validate_without_local_verify_extension(self) -> None:
        version = _run_openspec("--version")
        self.assertEqual(0, version.returncode, version.stderr)
        self.assertRegex(version.stdout.strip(), r"^1\.[6-9]\.|^[2-9]\." )

        help_result = _run_openspec("--help")
        self.assertEqual(0, help_result.returncode, help_result.stderr)
        command_lines = {
            line.strip().split()[0]
            for line in help_result.stdout.splitlines()
            if line.startswith("  ") and line.strip()
        }
        self.assertIn("validate", command_lines)
        self.assertNotIn("verify", command_lines)

        retired = _run_openspec("verify", "retired-local-extension", "--json")
        self.assertNotEqual(0, retired.returncode)
        self.assertIn("unknown command", (retired.stdout + retired.stderr).lower())


if __name__ == "__main__":
    unittest.main()
