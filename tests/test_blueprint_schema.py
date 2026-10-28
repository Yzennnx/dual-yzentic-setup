import unittest
import json
from pathlib import Path

class TestBlueprintSchema(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.blueprint_file = self.root / "project-blueprint.json"

    def test_blueprint_file_exists_and_valid(self):
        self.assertTrue(self.blueprint_file.exists(), "project-blueprint.json must exist")
        data = json.loads(self.blueprint_file.read_text(encoding="utf-8"))
        self.assertIn("status", data)
        self.assertIn(data["status"], ["uninitialized", "initialized"])
        self.assertIn("project", data)
        self.assertNotIn("archetypes", data)

    def test_rules_block_has_globs(self):
        rules = json.loads(self.blueprint_file.read_text(encoding="utf-8"))["rules"]
        for key in ("source", "ignore", "tests"):
            self.assertIsInstance(rules[key], list, key)
        self.assertIn("**/*.test.*", rules["tests"])

    def test_single_developer(self):
        data = json.loads(self.blueprint_file.read_text(encoding="utf-8"))
        self.assertNotIn("team", data["project"])
        self.assertIsInstance(data["project"]["developer"], str)

if __name__ == "__main__":
    unittest.main()
