"""Static checks for the author-side public-route execution documentation."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard.route_topology import PUBLIC_ROUTE_IDS, PUBLIC_ROUTE_SKILL_OWNERS


CONTRACT = ROOT / ".agents" / "skills" / "flowguard" / "references" / "route_execution_contract.md"
ROUTE_INDEX = ROOT / ".agents" / "skills" / "flowguard" / "references" / "route_index.md"


class RouteExecutionContractDocsTests(unittest.TestCase):
    def test_contract_covers_exactly_the_public_route_registry(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")
        self.assertEqual(15, len(PUBLIC_ROUTE_IDS))
        for route_id in PUBLIC_ROUTE_IDS:
            with self.subTest(route=route_id):
                self.assertIn(f"| `{route_id}` |", text)
                self.assertIn(f"`{route_id}`", ROUTE_INDEX.read_text(encoding="utf-8"))

    def test_shared_contract_contains_finite_execution_and_open_spec_gates(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")
        required_fragments = (
            "RouteContext",
            "execute | reuse_current | blocked | not_run",
            "producer count remains zero",
            "--reuse-only",
            "WinError 1314",
            "allow-explicit-completion-objective/tasks.md:3.3",
            "close-runtime-evidence-and-task-map/tasks.md:9.2",
            "close-runtime-evidence-and-task-map/tasks.md:9.3",
            "typed `blocked`/`not_run`",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

    def test_each_public_skill_points_to_its_single_lazy_contract_row(self) -> None:
        for route_id in PUBLIC_ROUTE_IDS:
            skill_id = PUBLIC_ROUTE_SKILL_OWNERS[route_id]
            skill_path = ROOT / ".agents" / "skills" / skill_id / "SKILL.md"
            with self.subTest(route=route_id, skill=skill_id):
                self.assertTrue(skill_path.is_file())
                text = skill_path.read_text(encoding="utf-8")
                self.assertIn("## Shared execution contract", text)
                self.assertIn("route_execution_contract.md", text)
                self.assertIn(f"`{route_id}`", text)
                self.assertIn("## Use When", text)
                self.assertIn("## Do Not Use When", text)

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
