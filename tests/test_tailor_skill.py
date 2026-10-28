import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestTailorSkill(unittest.TestCase):
    def setUp(self):
        self.skill_file = REPO_ROOT / ".agents" / "skills" / "tailor-setup" / "SKILL.md"

    def read_skill(self):
        self.assertTrue(self.skill_file.exists(), f"Missing {self.skill_file}")
        return self.skill_file.read_text(encoding="utf-8")

    def test_skill_frontmatter(self):
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", self.read_skill(), re.DOTALL)
        self.assertIsNotNone(match, "tailor-setup/SKILL.md must have YAML frontmatter")
        frontmatter = match.group(1)
        self.assertIn("name: tailor-setup", frontmatter)
        self.assertIn("description:", frontmatter)
        self.assertIn("version: 1.0.0", frontmatter)

    def test_skill_covers_the_workflow(self):
        content = self.read_skill()
        required = [
            "npm run tailor -- --dry-run",
            "npm run tailor",
            "npm run verify:agent",
            "superpowers:brainstorming",
            "source_rules",
            "docs/rules",
            "rules.source",
            "features",
            "rules:check",
            "owns",
            "test_scoped",
            "--force",
            "tailor-setup",
            "fast-track",
            "caveman",
            "ponytail",
        ]
        for phrase in required:
            self.assertIn(phrase, content, f"SKILL.md must mention {phrase}")

    def test_routing_docs_mention_tailor(self):
        handbook = (REPO_ROOT / "docs" / "ai" / "agent-handbook.md").read_text(encoding="utf-8")
        self.assertIn("tailor-setup", handbook)
        agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("npm run tailor", agents)


if __name__ == "__main__":
    unittest.main()
