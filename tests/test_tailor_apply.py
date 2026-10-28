import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.repo_fixture import SCRIPTS, VALID_PROJECT, make_repo, skill_dirs


def tailor(root, *flags, env=None):
    cmd = ["node", str(SCRIPTS / "tailor.mjs"), "--root", str(root), *flags]
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def snapshot(root):
    root = Path(root)
    files = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    dirs = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_dir()}
    return files, dirs


class TestTailorApply(unittest.TestCase):
    def repo(self, project=None, status="uninitialized"):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        return make_repo(tmp.name, project=project, status=status)

    def read_json(self, root, relative):
        return json.loads((root / relative).read_text(encoding="utf-8"))

    def test_applies_manifest(self):
        root = self.repo()
        res = tailor(root)
        self.assertEqual(res.returncode, 0, res.stderr)

        self.assertEqual(
            skill_dirs(root) - {"_staging"},
            {"alpha", "gamma", "tailor-setup", "fast-track", "caveman", "ponytail"},
        )
        self.assertEqual(skill_dirs(root, "skills-archive"), {"beta"})

        plan = (root / "docs" / "PLAN.md").read_text(encoding="utf-8")
        self.assertIn("Task 1.1 [canvas]: Canvas shell", plan)
        self.assertIn("Task 2.1 [canvas] [arch]: Seed flows", plan)
        self.assertIn("> **For Steve and the AI agents:**", plan)
        self.assertNotIn("ORIGINAL PLAN", plan)
        for banned in ["Owner", "Hackathon", "judges", "Demo"]:
            self.assertNotIn(banned, plan)

        package = self.read_json(root, "package.json")
        self.assertEqual(package["name"], "ai-flow-canvas")
        self.assertEqual(package["description"], VALID_PROJECT["description"])
        self.assertEqual(package["scripts"], {"tailor": "node scripts/tailor.mjs"})

        handoff = self.read_json(root, ".agents/sync/handoff.json")
        self.assertEqual(handoff["task_id"], "INIT-01")
        self.assertEqual(handoff["status"], "idle")
        self.assertEqual(handoff["turn_count"], 0)

        blueprint = self.read_json(root, "project-blueprint.json")
        self.assertEqual(blueprint["status"], "initialized")
        self.assertEqual(blueprint["project"], VALID_PROJECT)
        self.assertNotIn("archetypes", blueprint)
        self.assertEqual(blueprint["rules"]["source"], ["src/**/*.ts"])
        self.assertEqual(blueprint["rules"]["ignore"], [])
        self.assertIn("**/*.test.*", blueprint["rules"]["tests"])

    def test_manifest_without_developer_renders_the_developer(self):
        project = copy.deepcopy(VALID_PROJECT)
        del project["developer"]
        root = self.repo(project=project)

        res = tailor(root)

        self.assertEqual(res.returncode, 0, res.stderr)
        plan = (root / "docs" / "PLAN.md").read_text(encoding="utf-8")
        self.assertIn("> **For the developer and the AI agents:**", plan)
        handoff = (root / ".agents" / "sync" / "handoff.md").read_text(encoding="utf-8")
        self.assertNotIn("undefined", handoff)

    def test_dry_run_writes_nothing(self):
        root = self.repo()
        before = snapshot(root)

        res = tailor(root, "--dry-run")

        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(snapshot(root), before)
        self.assertIn("[Tailor] archive: beta", res.stdout)
        self.assertIn("[Tailor] restore: gamma", res.stdout)
        self.assertIn("Dry run", res.stdout)

    def test_invalid_manifest_changes_nothing(self):
        project = copy.deepcopy(VALID_PROJECT)
        project["skills"] = ["nope"]
        project["roadmap"][0]["priority"] = "P3"
        root = self.repo(project=project)
        before = snapshot(root)

        res = tailor(root)

        self.assertEqual(res.returncode, 1)
        self.assertIn("project.skills", res.stderr)
        self.assertIn("project.roadmap[0].priority", res.stderr)
        self.assertEqual(snapshot(root), before)

    def test_refuses_initialized_without_force(self):
        root = self.repo(status="initialized")
        before = snapshot(root)

        res = tailor(root)
        self.assertEqual(res.returncode, 1)
        self.assertIn("--force", res.stderr)
        self.assertEqual(snapshot(root), before)

        res = tailor(root, "--force")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Task 1.1 [canvas]: Canvas shell", (root / "docs" / "PLAN.md").read_text(encoding="utf-8"))

    def test_unparseable_blueprint(self):
        root = self.repo()
        (root / "project-blueprint.json").write_text("{not json", encoding="utf-8")

        res = tailor(root)

        self.assertEqual(res.returncode, 1)
        self.assertIn("project-blueprint.json", res.stderr)
        self.assertNotIn("    at ", res.stderr)

    def test_duplicate_skills_apply_once(self):
        project = copy.deepcopy(VALID_PROJECT)
        project["skills"] = ["alpha", "alpha", "caveman"]
        root = self.repo(project=project)

        res = tailor(root)

        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("alpha", skill_dirs(root))
        self.assertIn("gamma", skill_dirs(root, "skills-archive"))

    def test_no_git_dir_skips_hook(self):
        root = self.repo()
        res = tailor(root)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertFalse((root / ".githooks").exists())

    def test_npm_swallowed_dry_run_flag_is_still_a_dry_run(self):
        # `npm run tailor --dry-run` (no `--`) reaches the script only as npm_config_dry_run
        root = self.repo()
        before = snapshot(root)

        res = tailor(root, env=dict(os.environ, npm_config_dry_run="true"))

        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(snapshot(root), before)
        self.assertIn("Dry run", res.stdout)

    def test_unknown_flag_is_rejected(self):
        root = self.repo()
        before = snapshot(root)

        res = tailor(root, "--dryrun")

        self.assertEqual(res.returncode, 1)
        self.assertIn("--dryrun", res.stderr)
        self.assertEqual(snapshot(root), before)

    def test_root_without_value_is_rejected(self):
        res = subprocess.run(["node", str(SCRIPTS / "tailor.mjs"), "--root"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)
        self.assertIn("--root", res.stderr)

    def test_partial_failure_stays_uninitialized_and_rerun_converges(self):
        root = self.repo()
        plan = root / "docs" / "PLAN.md"
        plan.unlink()
        plan.mkdir()  # makes the roadmap write fail after skills have moved

        res = tailor(root)
        self.assertEqual(res.returncode, 1)
        self.assertEqual(self.read_json(root, "project-blueprint.json")["status"], "uninitialized")

        plan.rmdir()
        res = tailor(root)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.read_json(root, "project-blueprint.json")["status"], "initialized")
        self.assertEqual(skill_dirs(root, "skills-archive"), {"beta"})
        self.assertIn("Task 1.1 [canvas]: Canvas shell", plan.read_text(encoding="utf-8"))

    def test_git_repo_gets_the_hook(self):
        root = self.repo()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)

        res = tailor(root)

        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue((root / ".githooks" / "pre-commit").exists())
        hooks_path = subprocess.run(["git", "config", "core.hooksPath"], cwd=root, capture_output=True, text=True)
        self.assertEqual(hooks_path.stdout.strip(), ".githooks")

    def test_missing_project_block(self):
        root = self.repo()
        (root / "project-blueprint.json").write_text(json.dumps({"status": "uninitialized"}), encoding="utf-8")
        before = snapshot(root)

        res = tailor(root)

        self.assertEqual(res.returncode, 1)
        self.assertIn("project:", res.stderr)
        self.assertEqual(snapshot(root), before)

    def test_non_directory_skill_names_are_rejected(self):
        for bad in ["../alpha", "_staging", ""]:
            with self.subTest(name=bad):
                project = copy.deepcopy(VALID_PROJECT)
                project["skills"] = ["alpha", bad]
                root = self.repo(project=project)
                before = snapshot(root)

                res = tailor(root)

                self.assertEqual(res.returncode, 1)
                self.assertIn("project.skills", res.stderr)
                self.assertEqual(snapshot(root), before)


if __name__ == "__main__":
    unittest.main()
