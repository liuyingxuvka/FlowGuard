from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_behavior_commitment_protocol_teaches_primary_path_authority():
    protocol = (
        ROOT / ".agents" / "skills" / "flowguard" / "references" / "domains" / "behavior-commitment" / "protocol.md"
    ).read_text(encoding="utf-8").lower()
    assert "primary path" in protocol
    assert "fallback" in protocol
    assert "review_primary_path_authority" in protocol
