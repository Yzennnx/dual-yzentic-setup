import unittest
from pathlib import Path

class TestRootRules(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent

    def test_agents_md_exists_and_contains_tenets(self):
        agents_file = self.root / "AGENTS.md"
        self.assertTrue(agents_file.exists(), "AGENTS.md must exist at repo root")
        content = agents_file.read_text(encoding="utf-8")
        self.assertIn("Evidence before assertions", content)
        self.assertIn("file://", content)
        self.assertIn(".agents/skills", content)

    def test_compatibility_pointers_reference_agents(self):
        for pointer_name in ["GEMINI.md", "CLAUDE.md", ".cursorrules"]:
            pointer = self.root / pointer_name
            self.assertTrue(pointer.exists(), f"{pointer_name} must exist at repo root")
            content = pointer.read_text(encoding="utf-8")
            self.assertIn("AGENTS.md", content, f"{pointer_name} must reference AGENTS.md")

    def test_claude_rule_contract(self):
        content = (self.root / "CLAUDE.md").read_text(encoding="utf-8")
        for phrase in ["Builder", "verify:agent", "caveman", "ponytail", "project-blueprint.json"]:
            self.assertIn(phrase, content)

    def test_gemini_rule_contract(self):
        content = (self.root / "GEMINI.md").read_text(encoding="utf-8")
        for phrase in ["Gatekeeper", "handoff", "project-blueprint.json"]:
            self.assertIn(phrase, content)

    def test_every_root_doc_points_at_docs_rules(self):
        for name in ["AGENTS.md", "CLAUDE.md", ".cursorrules", "README.md"]:
            content = (self.root / name).read_text(encoding="utf-8")
            self.assertIn("docs/rules", content, f"{name} must point at docs/rules")
        claude = (self.root / "CLAUDE.md").read_text(encoding="utf-8")
        for phrase in ["### 3.1b Rules", "invariants.md", "Fix A", "rules:check"]:
            self.assertIn(phrase, claude)
        gemini = (self.root / "GEMINI.md").read_text(encoding="utf-8")
        self.assertIn("Tests from rules", gemini)

    def test_no_doc_points_at_the_retired_rule_files_or_archetypes(self):
        for name in ["AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md", "docs/ai/agent-handbook.md", "docs/ai/workflows.md"]:
            content = (self.root / name).read_text(encoding="utf-8")
            for retired in ["rules/frontend.md", "rules/backend.md", "rules/requirements.md", "npm run init:project", "DESIGN.md"]:
                self.assertNotIn(retired, content, f"{name} still mentions {retired}")

if __name__ == "__main__":
    unittest.main()
