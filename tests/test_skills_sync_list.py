import json
import tempfile
import unittest

from tests import repo_fixture
from tests.repo_fixture import make_repo, run_node, skill_dirs


class TestSkillsSyncList(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.root = make_repo(self.tmp.name)

    def sync(self, names):
        code = f"""
        import {{ syncSkillsToList }} from './scripts/skills-manager.mjs';
        console.log(JSON.stringify(syncSkillsToList({json.dumps(names)}, {{ root: {json.dumps(str(self.root))} }})));
        """
        return run_node(code)

    def test_archives_unlisted_and_restores_listed(self):
        res = self.sync(["alpha", "gamma", "wayfinder"])
        self.assertEqual(res.returncode, 0, res.stderr)
        result = json.loads(res.stdout)

        self.assertEqual(skill_dirs(self.root) - {"_staging"}, {"alpha", "gamma", "wayfinder"})
        self.assertEqual(skill_dirs(self.root, "skills-archive"), {"beta", "tailor-setup", "fast-track"})
        self.assertEqual(result["enabled"], ["gamma"])
        self.assertIn("beta", result["disabled"])
        self.assertEqual(result["active_count"], 3)
        self.assertEqual(result["archived_count"], 3)

    def test_unknown_name_moves_nothing(self):
        active_before = skill_dirs(self.root)
        archive_before = skill_dirs(self.root, "skills-archive")

        res = self.sync(["alpha", "nope"])

        self.assertNotEqual(res.returncode, 0)
        self.assertIn("nope", res.stderr)
        self.assertEqual(skill_dirs(self.root), active_before)
        self.assertEqual(skill_dirs(self.root, "skills-archive"), archive_before)

    def test_rejects_non_directory_names(self):
        active_before = skill_dirs(self.root)
        archive_before = skill_dirs(self.root, "skills-archive")

        for bad in ["../alpha", "_staging", ""]:
            with self.subTest(name=bad):
                res = self.sync([bad])
                self.assertNotEqual(res.returncode, 0)
                self.assertEqual(skill_dirs(self.root), active_before)
                self.assertEqual(skill_dirs(self.root, "skills-archive"), archive_before)

    def test_duplicates_are_harmless(self):
        res = self.sync(["alpha", "alpha"])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("alpha", skill_dirs(self.root))
        self.assertEqual(json.loads(res.stdout)["active_count"], 1)

    def test_list_skills_honours_root(self):
        code = f"""
        import {{ listSkills }} from './scripts/skills-manager.mjs';
        console.log(JSON.stringify(listSkills({{ root: {json.dumps(str(self.root))} }})));
        """
        res = run_node(code)
        self.assertEqual(res.returncode, 0, res.stderr)
        data = json.loads(res.stdout)
        self.assertEqual(sorted(data["active"]), sorted(repo_fixture.ACTIVE_SKILLS))
        self.assertEqual(data["archived"], ["gamma"])


if __name__ == "__main__":
    unittest.main()
