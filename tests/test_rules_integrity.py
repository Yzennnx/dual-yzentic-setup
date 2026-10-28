import unittest
import re
import os
from pathlib import Path

class TestRulesIntegrity(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.rules_dir = self.root / "docs" / "rules"
        self.expected_files = ["README.md", "requirements.md", "frontend.md", "backend.md"]

    def test_all_rule_files_exist(self):
        self.assertTrue(self.rules_dir.exists(), "docs/rules/ directory must exist")
        for filename in self.expected_files:
            rule_file = self.rules_dir / filename
            self.assertTrue(rule_file.exists(), f"Rule file {filename} must exist in docs/rules/")
            content = rule_file.read_text(encoding="utf-8")
            self.assertGreater(len(content.strip()), 100, f"Rule file {filename} must not be empty")

    def test_rule_files_structure(self):
        domain_files = ["requirements.md", "frontend.md", "backend.md"]
        for filename in domain_files:
            rule_file = self.rules_dir / filename
            if rule_file.exists():
                content = rule_file.read_text(encoding="utf-8")
                self.assertIn("## Core Standards", content, f"{filename} must contain '## Core Standards'")
                self.assertIn("## Dos and Don'ts", content, f"{filename} must contain '## Dos and Don'ts'")

    def test_claude_rule_contract(self):
        claude_md = self.root / "CLAUDE.md"
        self.assertTrue(claude_md.exists(), "CLAUDE.md must exist")
        content = claude_md.read_text(encoding="utf-8")
        self.assertIn("Builder", content)
        self.assertIn("verify:agent", content)
        self.assertIn("caveman", content)
        self.assertIn("ponytail", content)
        self.assertIn("project-blueprint.json", content)

    def test_gemini_rule_contract(self):
        gemini_md = self.root / "GEMINI.md"
        self.assertTrue(gemini_md.exists(), "GEMINI.md must exist")
        content = gemini_md.read_text(encoding="utf-8")
        self.assertIn("Gatekeeper", content)
        self.assertIn("handoff", content)
        self.assertIn("project-blueprint.json", content)

    def test_agents_rule_contract(self):
        agents_md = self.root / "AGENTS.md"
        self.assertTrue(agents_md.exists(), "AGENTS.md must exist")
        content = agents_md.read_text(encoding="utf-8")
        self.assertIn("docs/PLAN.md", content)
        self.assertIn(".agents/sync", content)
        self.assertIn("project-blueprint.json", content)
        self.assertIn("init:project", content)

    def test_handbook_initial_orientation_blueprint(self):
        handbook = self.root / "docs" / "ai" / "agent-handbook.md"
        self.assertTrue(handbook.exists(), "docs/ai/agent-handbook.md must exist")
        content = handbook.read_text(encoding="utf-8")
        self.assertIn("project-blueprint.json", content)

if __name__ == "__main__":
    unittest.main()
