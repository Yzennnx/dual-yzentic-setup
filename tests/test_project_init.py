import subprocess
import unittest

from tests import repo_fixture


class TestProjectInit(unittest.TestCase):
    def test_init_project_is_retired(self):
        res = subprocess.run(
            ["node", str(repo_fixture.SCRIPTS / "init-project.mjs"), "--preset", "minimal"],
            cwd=repo_fixture.REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("Start with the wayfinder kickoff, then tailor-setup", res.stdout)

    def test_no_archetype_code_remains(self):
        self.assertFalse((repo_fixture.SCRIPTS / "scaffolder.mjs").exists())
        blueprint = (repo_fixture.REPO_ROOT / "project-blueprint.json").read_text(encoding="utf-8")
        self.assertNotIn('"archetypes"', blueprint)


if __name__ == "__main__":
    unittest.main()
