"""Run the installed SkillGuard project-adoption audit without mutating the repository.

The wrapper keeps OpenSpec verification contracts portable: callers do not need to
embed a user-home path to ``skillguard.py`` and receive one canonical JSON document
on stdout.  SkillGuard remains the authority for the audit decision.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


Runner = Callable[..., subprocess.CompletedProcess[str]]
DEFAULT_TIMEOUT_SECONDS = 120
FROZEN_ROOT_PREFIX = "openspec-frozen-"


def resolve_skillguard_cli(value: str, *, codex_home: Path | None = None) -> Path:
    """Resolve an explicit CLI or the installed SkillGuard CLI under CODEX_HOME."""

    if value != "all":
        return Path(value).expanduser().resolve()
    if codex_home is None:
        configured = os.environ.get("CODEX_HOME", "").strip()
        codex_home = Path(configured).expanduser() if configured else Path.home() / ".codex"
    return codex_home.resolve() / "skills" / "skillguard" / "scripts" / "skillguard.py"


def _blocked(code: str) -> dict[str, Any]:
    return {
        "schema_version": "flowguard.skillguard_project_adoption_check.v1",
        "status": "blocked",
        "ok": False,
        "findings": [code],
        "runtime_authorities": [],
        "claim_boundary": (
            "This wrapper only delegates the read-only portable project audit to the installed "
            "SkillGuard authority. It does not prove execution depth, installation parity, release "
            "readiness, or future AI behavior."
        ),
    }


def _frozen_audit_root(root: Path) -> tuple[Path, tempfile.TemporaryDirectory[str] | None, str]:
    """Preserve the declared project identity inside an OpenSpec frozen copy.

    OpenSpec deliberately gives a full-verification snapshot a random directory
    name.  SkillGuard deliberately binds the project manifest to the repository
    directory name.  For that one integration boundary, stage only the exact
    surfaces read by SkillGuard under the manifest's declared project id.  The
    official SkillGuard audit still owns every acceptance decision.
    """

    if not root.name.casefold().startswith(FROZEN_ROOT_PREFIX):
        return root, None, ""
    manifest_path = root / ".skillguard" / "project.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return root, None, "frozen_project_manifest_unreadable"
    project_id = str(manifest.get("project_id", "")).strip() if isinstance(manifest, Mapping) else ""
    if not project_id or Path(project_id).name != project_id or project_id in {".", ".."}:
        return root, None, "frozen_project_id_invalid"

    temporary = tempfile.TemporaryDirectory(prefix="flowguard-skillguard-audit-")
    staged = Path(temporary.name) / project_id
    try:
        staged.mkdir()
        shutil.copy2(root / "AGENTS.md", staged / "AGENTS.md")
        shutil.copytree(root / ".skillguard", staged / ".skillguard")
        (staged / ".agents").mkdir()
        shutil.copytree(root / ".agents" / "skills", staged / ".agents" / "skills")
    except OSError:
        temporary.cleanup()
        return root, None, "frozen_project_audit_staging_failed"
    return staged.resolve(), temporary, ""


def run_project_audit(
    root: str | Path,
    *,
    skillguard: str = "all",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    runner: Runner = subprocess.run,
) -> tuple[Mapping[str, Any], int, str]:
    """Return the authoritative payload, wrapper exit code, and child stderr."""

    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        return _blocked("repository_root_missing"), 1, ""
    if timeout_seconds <= 0:
        return _blocked("timeout_must_be_positive"), 1, ""
    cli = resolve_skillguard_cli(skillguard)
    if not cli.is_file():
        return _blocked("skillguard_cli_missing"), 1, ""
    audit_root, temporary, staging_error = _frozen_audit_root(root_path)
    if staging_error:
        return _blocked(staging_error), 1, ""
    command = [sys.executable, str(cli), "project-audit", "--root", str(audit_root)]
    try:
        completed = runner(
            command,
            cwd=str(audit_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _blocked("skillguard_project_audit_timeout"), 1, ""
    except OSError:
        return _blocked("skillguard_project_audit_launch_failed"), 1, ""
    finally:
        if temporary is not None:
            temporary.cleanup()

    stderr = completed.stderr or ""
    try:
        payload = json.loads(completed.stdout or "")
    except json.JSONDecodeError:
        return _blocked("skillguard_project_audit_unparseable"), 1, stderr
    if not isinstance(payload, Mapping):
        return _blocked("skillguard_project_audit_payload_invalid"), 1, stderr

    official_pass = payload.get("ok") is True and payload.get("status") == "pass"
    if completed.returncode == 0 and not official_pass:
        return _blocked("skillguard_project_audit_terminal_mismatch"), 1, stderr
    return payload, 0 if completed.returncode == 0 and official_pass else 1, stderr


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root to audit")
    parser.add_argument(
        "--skillguard",
        default="all",
        help="'all' for the installed SkillGuard CLI or an explicit skillguard.py path",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--json", action="store_true", help="Emit canonical JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout <= 0:
        payload, exit_code, stderr = _blocked("timeout_must_be_positive"), 1, ""
    else:
        payload, exit_code, stderr = run_project_audit(
            args.root,
            skillguard=args.skillguard,
            timeout_seconds=args.timeout,
        )
    if stderr:
        print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    else:
        print(f"status: {payload.get('status', 'blocked')}")
        for finding in payload.get("findings", []):
            print(f"finding: {finding}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
