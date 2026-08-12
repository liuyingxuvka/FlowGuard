import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README_EN = ROOT / "README.md"
README_ZH = ROOT / "README.zh-CN.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def heading_shape(text: str) -> tuple[int, ...]:
    return tuple(len(match.group(1)) for match in re.finditer(r"^(#{1,6})\s+", text, re.MULTILINE))


def fence_languages(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"^```([^\n]*)$", text, re.MULTILINE)[::2])


def mermaid_topology(text: str) -> tuple[tuple[str, ...], ...]:
    blocks = re.findall(r"```mermaid\n(.*?)```", text, flags=re.DOTALL)
    normalized_blocks = []
    for block in blocks:
        block = re.sub(
            r"(note\s+[^\n]+\n).*?(\n\s*end note)",
            r"\1LABEL\2",
            block,
            flags=re.DOTALL,
        )
        lines = []
        for raw in block.splitlines():
            line = raw.strip()
            if not line:
                continue
            line = re.sub(r'\[".*?"\]', '["LABEL"]', line)
            line = re.sub(r'\{".*?"\}', '{"LABEL"}', line)
            line = re.sub(
                r'(\b[A-Za-z_][A-Za-z0-9_]*)\[(?!")([^\]]*)\]',
                r'\1["LABEL"]',
                line,
            )
            line = re.sub(
                r'(\b[A-Za-z_][A-Za-z0-9_]*)\{(?!")([^}]*)\}',
                r'\1{"LABEL"}',
                line,
            )
            line = re.sub(r'--?>\|.*?\|', '-->|LABEL|', line)
            if "-->" in line and ":" in line:
                line = line.split(":", 1)[0].rstrip()
            lines.append(line)
        normalized_blocks.append(tuple(lines))
    return tuple(normalized_blocks)


def local_doc_links(text: str) -> tuple[str, ...]:
    links = re.findall(r"\]\((\./[^)#]+)", text)
    return tuple(sorted(link for link in links if not link.startswith("./README")))


def command_lines(text: str) -> tuple[str, ...]:
    prefixes = ("python ", "git clone ", "cd FlowGuard")
    return tuple(line.strip() for line in text.splitlines() if line.strip().startswith(prefixes))


class ReadmeMirrorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.english = read(README_EN)
        cls.chinese = read(README_ZH)

    def test_language_switch_and_visible_language_boundary(self):
        self.assertIn("[中文说明](./README.zh-CN.md)", self.english)
        self.assertIn("[English](./README.md)", self.chinese)
        english_without_language_switch = self.english.replace("[中文说明]", "")
        self.assertIsNone(re.search(r"[\u3400-\u9fff]", english_without_language_switch))
        self.assertIsNotNone(re.search(r"[\u3400-\u9fff]", self.chinese))

    def test_structural_shape_is_identical(self):
        self.assertEqual(heading_shape(self.english), heading_shape(self.chinese))
        self.assertEqual(fence_languages(self.english), fence_languages(self.chinese))
        self.assertEqual(self.english.count("\n| ---"), self.chinese.count("\n| ---"))
        self.assertEqual(
            sum(line.startswith("|") for line in self.english.splitlines()),
            sum(line.startswith("|") for line in self.chinese.splitlines()),
        )
        self.assertEqual(self.english.count("<details>"), self.chinese.count("<details>"))

    def test_diagrams_keep_the_same_topology(self):
        english = mermaid_topology(self.english)
        chinese = mermaid_topology(self.chinese)
        self.assertEqual(7, len(english))
        self.assertEqual(english, chinese)

    def test_assets_links_and_commands_stay_aligned(self):
        image_pattern = r'<img\s+src="([^"]+)"'
        self.assertEqual(
            tuple(re.findall(image_pattern, self.english)),
            tuple(re.findall(image_pattern, self.chinese)),
        )
        self.assertEqual(local_doc_links(self.english), local_doc_links(self.chinese))
        self.assertEqual(command_lines(self.english), command_lines(self.chinese))

        for text in (self.english, self.chinese):
            linked_paths = re.findall(r"\]\((\./[^)#]+)", text)
            linked_paths.extend(re.findall(image_pattern, text))
            for linked_path in linked_paths:
                with self.subTest(linked_path=linked_path):
                    self.assertTrue((ROOT / linked_path).exists())

    def test_hero_privacy_review_is_bound_to_the_current_asset(self):
        review_path = ROOT / "assets" / "readme-hero" / "visual-privacy-review.json"
        review = json.loads(read(review_path))
        asset = ROOT / review["asset_path"]
        self.assertEqual("passed", review["status"])
        self.assertTrue(asset.is_file())
        self.assertEqual(
            review["asset_sha256"],
            hashlib.sha256(asset.read_bytes()).hexdigest().upper(),
        )


if __name__ == "__main__":
    unittest.main()
