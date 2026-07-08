from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOME_SKILLS = Path.home() / ".codex" / "skills"


def _project_version() -> str:
    for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.startswith("version = "):
            return line.split("=", 1)[1].strip().strip('"')
    raise ValueError("could not read project version")


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return "$FLOWGUARD_ROOT/" + resolved.relative_to(ROOT).as_posix()
    except ValueError:
        pass
    try:
        return "$CODEX_HOME/skills/" + resolved.relative_to(HOME_SKILLS).as_posix()
    except ValueError:
        pass
    return resolved.name


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(args: list[str], cwd: Path) -> dict[str, object]:
    completed = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    return {
        "args": ["python", *args[1:]] if args and Path(args[0]).name.startswith("python") else args,
        "cwd": _display_path(cwd),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _check_version() -> dict[str, object]:
    module = importlib.import_module("flowguard")
    module_path = Path(module.__file__).resolve()
    metadata_version = importlib.metadata.version("flowguard")
    ok = metadata_version == _project_version() and module.SCHEMA_VERSION == "1.0" and ROOT in module_path.parents
    return {
        "check": "version_import_path",
        "ok": ok,
        "metadata_version": metadata_version,
        "schema_version": module.SCHEMA_VERSION,
        "module_path": _display_path(module_path),
    }


def _skill_dirs() -> list[Path]:
    return sorted(path for path in (ROOT / ".agents" / "skills").iterdir() if (path / ".skillguard" / "checks").exists())


def _check_skillguard() -> dict[str, object]:
    check_names = [
        "check_route.py",
        "check_phase_order.py",
        "check_evidence.py",
        "check_quality_floor.py",
        "check_closure.py",
    ]
    runs = []
    for skill_dir in _skill_dirs():
        for check_name in check_names:
            runs.append(_run([sys.executable, f".skillguard/checks/{check_name}"], skill_dir))
    return {"check": "source_skillguard", "ok": all(run["exit_code"] == 0 for run in runs), "runs": runs}


def _check_installed_sync() -> dict[str, object]:
    rows = []
    for source_skill in _skill_dirs():
        installed_skill = HOME_SKILLS / source_skill.name
        pairs = [
            (source_skill / "SKILL.md", installed_skill / "SKILL.md"),
            (source_skill / ".skillguard" / "work-contract.json", installed_skill / ".skillguard" / "work-contract.json"),
        ]
        for source, installed in pairs:
            rows.append(
                {
                    "source": _display_path(source),
                    "installed": _display_path(installed),
                    "ok": source.exists() and installed.exists() and _sha256(source) == _sha256(installed),
                }
            )
    return {"check": "installed_skill_sync", "ok": all(row["ok"] for row in rows), "rows": rows}


def main() -> int:
    checks = [_check_version(), _check_skillguard(), _check_installed_sync()]
    ok = all(check["ok"] for check in checks)
    print(json.dumps({"ok": ok, "checks": checks}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
