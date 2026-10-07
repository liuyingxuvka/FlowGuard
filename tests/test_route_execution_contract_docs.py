"""Static checks for the author-side public-route execution documentation."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTRACT = ROOT / ".agents" / "skills" / "flowguard" / "references" / "route_execution_common.md"
ROUTE_INDEX = ROOT / ".agents" / "skills" / "flowguard" / "references" / "route_index.md"
KERNEL_SKILL = ROOT / ".agents" / "skills" / "flowguard" / "SKILL.md"

CURRENT_OPERATIONS = ("read", "change", "release")
CURRENT_DOMAINS = (
    "architecture-reduction",
    "behavior-commitment-ledger",
    "code-structure-recommendation",
    "contract-exhaustion-mesh",
    "development-process-flow",
    "existing-model-preflight",
    "field-lifecycle-mesh",
    "model-mesh",
    "model-miss-review",
    "model-test-alignment",
    "model-topology-hazard-review",
    "structure-mesh",
    "test-mesh",
    "ui-flow-structure",
)


class RouteExecutionContractDocsTests(unittest.TestCase):
    def test_contract_covers_one_skill_and_three_public_operations(self) -> None:
        text = " ".join(CONTRACT.read_text(encoding="utf-8").split())
        index = ROUTE_INDEX.read_text(encoding="utf-8")
        skill = KERNEL_SKILL.read_text(encoding="utf-8")
        self.assertIn("read observes; change executes the exact affected closure; release verifies its declared scope", text)
        self.assertIn("one public skill", skill)
        for operation in CURRENT_OPERATIONS:
            with self.subTest(operation=operation):
                self.assertIn(f"`{operation}`", index)
                self.assertIn(f"`{operation}`", skill)
        for domain in CURRENT_DOMAINS:
            with self.subTest(domain=domain):
                self.assertIn(f"references/domains/{domain}/", index)

    def test_shared_contract_contains_finite_execution_and_governed_gates(self) -> None:
        text = " ".join(CONTRACT.read_text(encoding="utf-8").split())
        required_fragments = (
            "RouteContext",
            "execute | reuse_current | blocked | not_run",
            "Read/plan-only creates no producer, lease, run directory, receipt, pointer or installation",
            "reuse_current",
            "Freeze that identity before execute",
            "unknown ownership never becomes run-all",
            "cleanup uncertainty",
            "out_of_scope",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

    def test_single_public_skill_points_to_the_lazy_contract(self) -> None:
        self.assertTrue(KERNEL_SKILL.is_file())
        text = KERNEL_SKILL.read_text(encoding="utf-8")
        self.assertIn("references/route_index.md", text)
        self.assertIn("references/domains/<subject>/protocol.md", text)
        self.assertIn("read", text)
        self.assertIn("change", text)
        self.assertIn("release", text)

    def test_open_spec_local_acceptance_files_still_name_the_three_gates(self) -> None:
        completion_tasks = (
            ROOT
            / "openspec"
            / "changes"
            / "close-runtime-evidence-and-task-map"
            / "tasks.md"
        ).read_text(encoding="utf-8")
        objective_tasks = (
            ROOT
            / "openspec"
            / "changes"
            / "allow-explicit-completion-objective"
            / "tasks.md"
        ).read_text(encoding="utf-8")
        self.assertIn("9.2", completion_tasks)
        self.assertIn("9.3", completion_tasks)
        self.assertIn("3.3", objective_tasks)
        self.assertIn("same-parent", completion_tasks)
        self.assertIn("reuse-only", objective_tasks)
        self.assertIn("WinError 1314", objective_tasks)


if __name__ == "__main__":
    unittest.main()
