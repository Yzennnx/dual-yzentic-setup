import json
import re
import tempfile
import unittest
from pathlib import Path
from tests.repo_fixture import run_node

REPO_ROOT = Path(__file__).resolve().parent.parent

class TestPlanIntegrity(unittest.TestCase):
    def setUp(self):
        self.plan_path = REPO_ROOT / "docs" / "PLAN.md"

    def test_plan_file_exists(self):
        self.assertTrue(self.plan_path.exists(), f"Missing {self.plan_path}")

    def test_plan_contains_required_sections(self):
        self.assertTrue(self.plan_path.exists(), f"Missing {self.plan_path}")
        content = self.plan_path.read_text(encoding="utf-8")
        
        required_sections = [
            "Mission & Objective",
            "Current Focus",
            "P0: Must-Have",
            "P1: Should-Have",
            "P2: Later",
            "Rules for Adding Features"
        ]
        for section in required_sections:
            self.assertIn(section, content, f"Missing section '{section}' in docs/PLAN.md")

    def test_plan_contains_priority_and_status_tags(self):
        content = self.plan_path.read_text(encoding="utf-8")
        self.assertIn("Priority:", content)
        self.assertIn("Status:", content)

    def missing_specs(self, root):
        code = f"""
        import {{ missingSpecs }} from './scripts/baton.mjs';
        console.log(JSON.stringify(missingSpecs({json.dumps(str(root))})));
        """
        result = run_node(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_roadmap_spec_links_resolve(self):
        self.assertEqual(self.missing_specs(REPO_ROOT), [])

    def test_completed_workflow_switcher_links_to_archived_spec(self):
        content = self.plan_path.read_text(encoding="utf-8")
        match = re.search(r"(?ms)^- \[x\] \*\*Task 0\.7:[^\n]+\n(.*?)(?=^- \[|\Z)", content)
        self.assertIsNotNone(match, "Workflow switcher should remain a completed task")
        self.assertIn("(specs/archive/2026-11-19-workflow-switcher-plan.md)", match.group(1))

    def test_two_closed_tasks_preserve_both_spec_links_after_archiving(self):
        active = "specs/active/2026-11-19-saved-searches-plan.md"
        archived = active.replace("/active/", "/archive/")
        anchors = ("task-1-save-a-search", "task-2-list-saved-searches")
        tasks = [
            {
                "id": f"1.{index}", "title": title, "description": title,
                "priority": "P1", "features": ["search"], "spec": f"{active}#{anchor}",
            }
            for index, (title, anchor) in enumerate(zip(("Save a search", "List saved searches"), anchors), start=1)
        ]
        result = run_node(f"""
        import {{ generateRoadmap }} from './scripts/roadmap.mjs';
        process.stdout.write(generateRoadmap({{ name: 'Search', tasks: {json.dumps(tasks)} }}));
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            docs = root / "docs"
            active_file = docs / active
            active_file.parent.mkdir(parents=True)
            active_file.write_text("## Task 1 Save a search\n\n## Task 2 List saved searches\n", encoding="utf-8")
            (docs / "specs" / "README.md").write_text("# Spec lifecycle\n", encoding="utf-8")
            plan = docs / "PLAN.md"
            plan.write_text(result.stdout, encoding="utf-8")
            self.assertEqual(self.missing_specs(root), [])

            archive_file = docs / archived
            archive_file.parent.mkdir()
            active_file.rename(archive_file)
            closed_plan = result.stdout.replace("- [ ] **Task", "- [x] **Task").replace("**Status:** Backlog", "**Status:** Done")
            plan.write_text(closed_plan.replace(active, archived, 1), encoding="utf-8")
            self.assertEqual(self.missing_specs(root), [f"docs/{active}"])
            closed_plan = closed_plan.replace(active, archived)
            plan.write_text(closed_plan, encoding="utf-8")
            self.assertEqual(self.missing_specs(root), [])
            for anchor in anchors:
                self.assertIn(f"({archived}#{anchor})", closed_plan)

if __name__ == "__main__":
    unittest.main()
