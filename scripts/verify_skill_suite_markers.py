"""Verify FlowGuard skill-suite onboarding markers.

The check is intentionally small and standard-library only. It verifies the
agent-facing distribution contract: `.agents/skills/` is the primary skill
surface, `model-first-function-flow` is the default entrypoint, and check
commands are not presented as the skill installation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


EXPECTED_FLOWGUARD_SKILLS = (
    "model-first-function-flow",
    "flowguard-agent-workflow-rehearsal",
    "flowguard-architecture-reduction",
    "flowguard-code-structure-recommendation",
    "flowguard-contract-exhaustion-mesh",
    "flowguard-development-process-flow",
    "flowguard-existing-model-preflight",
    "flowguard-field-lifecycle-mesh",
    "flowguard-model-mesh",
    "flowguard-model-miss-review",
    "flowguard-model-test-alignment",
    "flowguard-model-topology-hazard-review",
    "flowguard-plan-detailing-compiler",
    "flowguard-structure-mesh",
    "flowguard-test-mesh",
    "flowguard-ui-flow-structure",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _has_before(text: str, first: str, second: str) -> bool:
    first_index = text.find(first)
    second_index = text.find(second)
    return first_index >= 0 and (second_index < 0 or first_index < second_index)


def _squash(text: str) -> str:
    return " ".join(text.split())


def _require(condition: bool, message: str, findings: list[str]) -> None:
    if not condition:
        findings.append(message)


def verify_repository(root: Path) -> list[str]:
    findings: list[str] = []

    readme = _read(root / "README.md")
    agents = _read(root / "AGENTS.md")
    snippet = _read(root / "docs" / "agents_snippet.md")
    integration = _read(root / "docs" / "project_integration.md")
    kernel = _read(root / ".agents" / "skills" / "model-first-function-flow" / "SKILL.md")

    _require("AI-agent skill suite" in readme, "README missing AI-agent skill suite wording", findings)
    _require(".agents/skills/model-first-function-flow/SKILL.md" in readme, "README missing default entry skill path", findings)
    _require("Run executable check scripts only when current evidence is needed" in readme, "README missing check-script evidence wording", findings)
    _require("python -m pip install -e ." not in readme, "README still contains package-first editable install command", findings)
    _require(_has_before(readme, ".agents/skills/model-first-function-flow/SKILL.md", "python -m flowguard"), "README mentions CLI before skill suite entry", findings)

    for text_name, text in (("AGENTS.md", agents), ("docs/agents_snippet.md", snippet)):
        squashed = _squash(text)
        _require("Primary agent surface: `.agents/skills/`" in text, f"{text_name} missing primary agent surface", findings)
        _require("Default entry skill: `.agents/skills/model-first-function-flow/SKILL.md`" in text, f"{text_name} missing default entry skill", findings)
        _require("not the AI-agent skill installation surface" in squashed, f"{text_name} missing check-support distinction", findings)

    _require("Agent Skill Suite Setup" in integration, "project integration missing skill-suite setup section", findings)
    _require("check-execution convenience; it is not the AI-agent skill install surface" in integration, "project integration missing command-wrapper boundary", findings)
    _require(_has_before(integration, "Agent Skill Suite Setup", "python -m pip install -e"), "project integration mentions editable install before skill setup", findings)
    _require("temporary local mini-framework" in integration, "project integration missing temporary local mini-framework warning", findings)
    _require("one-off mini framework" in integration, "project integration missing one-off mini framework warning", findings)
    _require("blocked_or_partial" in integration, "project integration missing blocked_or_partial state", findings)
    _require("project-adopt" in integration and "project-audit" in integration and "project-upgrade" in integration, "project integration missing project record commands", findings)
    _require("artifact-upgrade" in integration, "project integration missing artifact-upgrade command", findings)
    _require("latest-schema-first" in integration, "project integration missing latest-schema-first guidance", findings)
    _require(".flowguard/project.toml" in integration, "project integration missing project manifest path", findings)

    _require("default entrypoint for the FlowGuard AI-agent skill suite" in kernel, "kernel missing skill-suite entrypoint wording", findings)
    _require("all sibling FlowGuard" in kernel, "kernel missing sibling skill wording", findings)
    _require("Skill availability and executable evidence are separate" in kernel, "kernel missing skill/evidence separation", findings)

    skills_root = root / ".agents" / "skills"
    for skill_name in EXPECTED_FLOWGUARD_SKILLS:
        skill_file = skills_root / skill_name / "SKILL.md"
        _require(skill_file.exists(), f"repository missing FlowGuard skill {skill_name}", findings)

    return findings


def verify_installed(root: Path, installed_root: Path) -> list[str]:
    findings: list[str] = []
    repo_skills = root / ".agents" / "skills"
    for skill_name in EXPECTED_FLOWGUARD_SKILLS:
        repo_skill = repo_skills / skill_name / "SKILL.md"
        installed_skill = installed_root / skill_name / "SKILL.md"
        _require(repo_skill.exists(), f"repository missing FlowGuard skill {skill_name}", findings)
        _require(installed_skill.exists(), f"installed skill missing {skill_name}", findings)

    kernel = installed_root / "model-first-function-flow" / "SKILL.md"
    if kernel.exists():
        text = _read(kernel)
        _require("default entrypoint for the FlowGuard AI-agent skill suite" in text, "installed kernel missing skill-suite entrypoint wording", findings)
        _require("Skill availability and executable evidence are separate" in text, "installed kernel missing skill/evidence separation", findings)

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="verify FlowGuard skill-suite markers")
    parser.add_argument("--root", default=".", help="FlowGuard repository root")
    parser.add_argument("--installed-root", default=None, help="Optional installed Codex skills root")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    findings = verify_repository(root)
    if args.installed_root:
        findings.extend(verify_installed(root, Path(args.installed_root).resolve()))

    payload = {"ok": not findings, "findings": findings}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("status: OK" if payload["ok"] else "status: FAIL")
        for finding in findings:
            print(f"finding: {finding}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
