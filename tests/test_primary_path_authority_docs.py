from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_agents_and_skill_guidance_include_primary_path_authority_policy():
    texts = [
        (ROOT / "AGENTS.md").read_text(encoding="utf-8"),
        (ROOT / "docs" / "agents_snippet.md").read_text(encoding="utf-8"),
        (ROOT / ".agents" / "skills" / "flowguard-development-process-flow" / "SKILL.md").read_text(encoding="utf-8"),
        (ROOT / ".agents" / "skills" / "flowguard-contract-exhaustion-mesh" / "SKILL.md").read_text(encoding="utf-8"),
        (ROOT / ".agents" / "skills" / "flowguard-test-mesh" / "SKILL.md").read_text(encoding="utf-8"),
    ]
    combined = "\n".join(texts).lower()

    assert "primary path authority" in combined
    assert "visible primary failure" in combined
    assert "no alternate automatic success" in combined
    assert "cartesian coverage" in combined
