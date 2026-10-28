import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RULES = REPO_ROOT / "docs" / "rules"


class TestRulesSkeleton(unittest.TestCase):
    def read(self, rel):
        return (RULES / rel).read_text(encoding="utf-8")

    def test_skeleton_files_exist(self):
        for rel in ["README.md", "invariants.md", "architecture.md", "features/_example.md"]:
            self.assertTrue((RULES / rel).exists(), rel)

    def test_readme_has_map_markers(self):
        text = self.read("README.md")
        self.assertIn("<!-- rules:map -->", text)
        self.assertIn("<!-- /rules:map -->", text)

    def test_invariants_carry_three_numbered_examples(self):
        text = self.read("invariants.md")
        for n in (1, 2, 3):
            self.assertIn(f"[inv#{n}]", text)
        self.assertIn("Replace", text)

    def test_example_feature_has_the_four_sections_and_owns(self):
        text = self.read("features/_example.md")
        self.assertTrue(text.startswith("---\nowns:") or text.startswith("---\r\nowns:"))
        for heading in ["## What the user sees", "## Rules", "## How it works", "## Limits and out of scope"]:
            self.assertIn(heading, text)

    def test_rules_check_is_quiet_in_the_template(self):
        res = subprocess.run(["node", "scripts/rules-check.mjs"], cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("skipped", res.stdout)


if __name__ == "__main__":
    unittest.main()
