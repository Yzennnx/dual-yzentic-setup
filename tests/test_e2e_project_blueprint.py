import json
import shutil
import subprocess
import tempfile
import unittest

from tests import repo_fixture


class TestE2EProjectBlueprint(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.fixture = repo_fixture.make_template_repo(self.tmp.name)
        self.skills_dir = self.fixture / ".agents" / "skills"
        self.archive_dir = self.fixture / ".agents" / "skills-archive"

    def node(self, script, *args):
        cmd = ["node", str(repo_fixture.SCRIPTS / script), *args, "--root", str(self.fixture)]
        return subprocess.run(cmd, cwd=self.fixture, capture_output=True, text=True)

    def test_tailor_and_skill_toggle_lifecycle(self):
        # 1. A manifest in the blueprint, with the rules it points at
        rules = self.fixture / "docs" / "rules"
        (rules / "features").mkdir(parents=True)
        (rules / "README.md").write_text("# Rules\n", encoding="utf-8")
        (rules / "features" / "lists.md").write_text("---\nowns: []\n---\n# Lists\n", encoding="utf-8")
        path = self.fixture / "project-blueprint.json"
        bp = json.loads(path.read_text(encoding="utf-8"))
        bp["project"] = {
            "name": "e2e-demo-system",
            "description": "Fullstack AI Web App",
            "archetype": "custom",
            "source_rules": "docs/rules/README.md",
            "stack": {"runtime": "Node"},
            "developer": "Alice",
            "skills": ["ui-ux-pro-max"],
            "verify": {"test": "npm test"},
            "roadmap": [{"id": "1.1", "title": "Lists", "priority": "P0", "description": "Lists page.", "features": ["lists"]}],
        }
        bp["rules"] = {"source": ["src/**/*.ts"], "ignore": [], "tests": ["**/*.test.*"]}
        path.write_text(json.dumps(bp, indent=2), encoding="utf-8")

        # 2. Tailor
        res = self.node("tailor.mjs")
        self.assertEqual(res.returncode, 0, f"tailor failed: {res.stderr}")
        bp = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(bp["status"], "initialized")
        self.assertEqual(bp["project"]["developer"], "Alice")
        self.assertIn("Task 1.1 [lists]: Lists", (self.fixture / "docs" / "PLAN.md").read_text(encoding="utf-8"))

        # 3. Archived skills can be restored on demand
        res_list = self.node("skills-manager.mjs", "list", "--json")
        self.assertEqual(res_list.returncode, 0, res_list.stderr)
        skills_data = json.loads(res_list.stdout)
        self.assertIn("ui-ux-pro-max", skills_data["active"])
        self.assertIn("caveman", skills_data["active"])
        self.assertIn("ponytail", skills_data["active"])
        self.assertIn("slides", skills_data["archived"])
        res_enable = self.node("skills-manager.mjs", "enable", "slides")
        self.assertEqual(res_enable.returncode, 0, res_enable.stderr)
        self.assertTrue((self.skills_dir / "slides").exists())
        self.assertFalse((self.archive_dir / "slides").exists())

        # 4. Baton status works cleanly in initialized state
        res_baton = self.node("baton.mjs", "status")
        self.assertEqual(res_baton.returncode, 0, res_baton.stderr)


if __name__ == "__main__":
    unittest.main()
