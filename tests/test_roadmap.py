import json
import unittest

from tests.repo_fixture import run_node

TASKS = [
    {"id": "1.1", "title": "Canvas shell", "priority": "P0", "description": "Drag and drop nodes."},
    {"id": "2.1", "title": "Seed flows", "priority": "P1", "description": "Three demo flows."},
]

P0 = "## P0: Must-Have"
P1 = "## P1: Should-Have"
P2 = "## P2: Later"


class TestRoadmap(unittest.TestCase):
    def render(self, tasks=TASKS):
        options = {
            "name": "Flow Canvas",
            "desc": "A visual canvas for AI steps",
            "developer": "Steve",
            "preset": "custom",
            "tasks": tasks,
        }
        code = f"""
        import {{ generateRoadmap }} from './scripts/roadmap.mjs';
        process.stdout.write(generateRoadmap({json.dumps(options)}));
        """
        res = run_node(code)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout

    def test_groups_tasks_under_priority_headings(self):
        text = self.render()
        first = text.index("- [ ] **Task 1.1: Canvas shell**")
        second = text.index("- [ ] **Task 2.1: Seed flows**")
        self.assertLess(text.index(P0), first)
        self.assertLess(first, text.index(P1))
        self.assertLess(text.index(P1), second)
        self.assertLess(second, text.index(P2))
        self.assertIn("  - **Priority:** P0", text)
        self.assertIn("  - **Status:** Backlog", text)

    def test_features_render_as_tags_after_the_id(self):
        tasks = [{**TASKS[0], "features": ["auth", "billing"]}, {**TASKS[1], "features": ["arch"]}]
        text = self.render(tasks)
        self.assertIn("- [ ] **Task 1.1 [auth] [billing]: Canvas shell**", text)
        self.assertIn("- [ ] **Task 2.1 [arch]: Seed flows**", text)

    def test_empty_priority_keeps_heading(self):
        text = self.render()
        self.assertIn("None yet.", text[text.index(P2):])

    def test_contains_all_required_sections(self):
        text = self.render()
        for section in [
            "## Mission & Objective",
            "## Rules for Adding Features",
            "## Current Focus",
            P0,
            P1,
            P2,
        ]:
            self.assertIn(section, text)

    def test_sections_appear_in_order(self):
        text = self.render()
        headings = [
            "## Mission & Objective",
            "## Rules for Adding Features",
            "## Current Focus",
            P0,
            P1,
            P2,
        ]
        positions = [text.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))

    def test_single_developer_wording_and_no_hackathon_terms(self):
        text = self.render()
        self.assertIn("> **For Steve and the AI agents:**", text)
        self.assertIn("Active milestone: **Core scaffolding and first feature loop**", text)
        self.assertIn("- **Verification:** [`scripts/baton.mjs`](../scripts/baton.mjs)", text)
        for banned in ["Owner", "Hackathon", "judges", "Demo"]:
            self.assertNotIn(banned, text)

    def test_multiline_text_collapses_to_one_line(self):
        tasks = [dict(TASKS[0], title="Canvas\nshell", description="  Drag\n\nand drop.  ")]
        text = self.render(tasks)
        self.assertIn("**Task 1.1: Canvas shell**", text)
        self.assertIn("  - **Description:** Drag and drop.\n", text)


if __name__ == "__main__":
    unittest.main()
