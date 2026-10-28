import copy
import json
import tempfile
import unittest

from tests.repo_fixture import VALID_PROJECT, make_repo, run_node


class TestTailorValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.root = make_repo(self.tmp.name)

    def validate(self, blueprint):
        code = f"""
        import {{ validateManifest }} from './scripts/tailor.mjs';
        console.log(JSON.stringify(validateManifest({json.dumps(blueprint)}, {{ root: {json.dumps(str(self.root))} }})));
        """
        res = run_node(code)
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout)

    def problems(self, project):
        return self.validate({"project": project, "rules": {"source": ["src/**/*.ts"]}})

    def test_valid_manifest_has_no_problems(self):
        self.assertEqual(self.problems(VALID_PROJECT), [])

    def test_each_rule_reports_its_field(self):
        cases = [
            (lambda p: p.update(name=""), "project.name"),
            (lambda p: p.update(description="  "), "project.description"),
            (lambda p: p.update(archetype="fullstack-web"), "project.archetype"),
            (lambda p: p.update(source_rules="docs/rules/no.md"), "project.source_rules"),
            (lambda p: p.update(source_rules="../outside.md"), "project.source_rules"),
            (lambda p: p.pop("source_spec", None) or p.pop("source_rules"), "project.source_rules"),
            (lambda p: p["roadmap"][0].update(features=[]), "project.roadmap[0].features"),
            (lambda p: p["roadmap"][0].pop("features"), "project.roadmap[0].features"),
            (lambda p: p["roadmap"][1].update(features=["canvas", "nope"]), "project.roadmap[1].features"),
            (lambda p: p.update(stack=[]), "project.stack"),
            (lambda p: p.update(developer=""), "project.developer"),
            (lambda p: p.update(developer=7), "project.developer"),
            (lambda p: p.update(skills="alpha"), "project.skills"),
            (lambda p: p.update(skills=["alpha", "nope"]), "project.skills"),
            (lambda p: p["verify"].pop("test"), "project.verify.test"),
            (lambda p: p["verify"].update(test_scoped="npm test"), "project.verify.test_scoped"),
            (lambda p: p["verify"].update(e2e=""), "project.verify.e2e"),
            (lambda p: p["verify"].update(e2e=7), "project.verify.e2e"),
            (lambda p: p.update(roadmap=[]), "project.roadmap"),
            (lambda p: p["roadmap"][0].update(priority="P3"), "project.roadmap[0].priority"),
            (lambda p: p["roadmap"][1].update(id="1.1"), "project.roadmap[1].id"),
            (lambda p: p["roadmap"][0].update(title=""), "project.roadmap[0].title"),
            (lambda p: p.update(developer=" "), "project.developer"),
            (lambda p: p["roadmap"][0].update(description=""), "project.roadmap[0].description"),
            (lambda p: p["roadmap"].__setitem__(1, "not a task"), "project.roadmap[1]"),
            (lambda p: p.update(source_rules=str(self.root / "docs" / "rules" / "README.md")), "project.source_rules"),
            (lambda p: p.update(skills=["alpha", "../alpha"]), "project.skills"),
            (lambda p: p.update(skills=["_staging"]), "project.skills"),
        ]
        for mutate, expected in cases:
            with self.subTest(field=expected):
                project = copy.deepcopy(VALID_PROJECT)
                mutate(project)
                found = self.problems(project)
                self.assertEqual(len(found), 1, found)
                self.assertTrue(found[0].startswith(expected), found[0])

    def test_rules_source_globs_are_required(self):
        for rules in ({}, {"source": []}, {"source": [3]}):
            with self.subTest(rules=rules):
                found = self.validate({"project": VALID_PROJECT, "rules": rules})
                self.assertEqual(len(found), 1, found)
                self.assertTrue(found[0].startswith("rules.source"), found[0])

    def test_arch_needs_no_feature_doc(self):
        project = copy.deepcopy(VALID_PROJECT)
        project["roadmap"][0]["features"] = ["arch"]
        self.assertEqual(self.problems(project), [])

    def test_e2e_command_is_optional_and_valid_when_text(self):
        project = copy.deepcopy(VALID_PROJECT)
        project["verify"].pop("e2e", None)
        self.assertEqual(self.problems(project), [])
        project["verify"]["e2e"] = "npx playwright test"
        self.assertEqual(self.problems(project), [])

    def test_all_problems_reported_together(self):
        project = copy.deepcopy(VALID_PROJECT)
        project["name"] = ""
        project["roadmap"][0]["priority"] = "P3"
        project["skills"] = ["nope"]
        self.assertEqual(len(self.problems(project)), 3)

    def test_missing_project_block(self):
        found = self.validate({})
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].startswith("project"), found[0])

    def test_optional_fields_may_be_absent(self):
        project = copy.deepcopy(VALID_PROJECT)
        del project["verify"]["test_scoped"]
        del project["verify"]["build"]
        del project["developer"]
        self.assertEqual(self.problems(project), [])

    def test_developer_is_optional_but_must_be_text_when_present(self):
        project = copy.deepcopy(VALID_PROJECT)
        del project["developer"]
        self.assertEqual(self.problems(project), [])

        project["developer"] = ""
        found = self.problems(project)
        self.assertEqual(len(found), 1, found)
        self.assertTrue(found[0].startswith("project.developer"), found[0])

    def test_old_team_and_owner_fields_are_ignored(self):
        project = copy.deepcopy(VALID_PROJECT)
        project["team"] = {"dev1": {"name": ""}}
        project["roadmap"][0]["owner"] = "nobody"
        self.assertEqual(self.problems(project), [])

    def test_duplicate_and_always_kept_skills_are_valid(self):
        project = copy.deepcopy(VALID_PROJECT)
        project["skills"] = ["alpha", "alpha", "caveman"]
        self.assertEqual(self.problems(project), [])


if __name__ == "__main__":
    unittest.main()
