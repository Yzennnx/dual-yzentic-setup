import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import repo_fixture

GLOBAL_SKILLS = repo_fixture.SCRIPTS / "global-skills.mjs"


def write_skill(base, name):
    skill_dir = Path(base) / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\ndescription: fixture\n---\n", encoding="utf-8")


class TestGlobalSkills(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / "repo"
        self.home = base / "home"
        self.root.mkdir()
        self.home.mkdir()

    def write_manifest(self, skills, library="~/skill-library"):
        manifest = {"library": library, "skills": skills}
        (self.root / "global-skills.json").write_text(json.dumps(manifest), encoding="utf-8")

    def run_cli(self, *args):
        cmd = ["node", str(GLOBAL_SKILLS), *args, "--root", str(self.root), "--home", str(self.home)]
        return subprocess.run(cmd, cwd=self.root, capture_output=True, text=True)

    def call_fn(self, expr):
        code = f"import * as gs from './scripts/global-skills.mjs'; console.log(JSON.stringify({expr}));"
        res = repo_fixture.run_node(code)
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout)

    def test_read_manifest_expands_home_and_deduplicates_skills(self):
        self.write_manifest(["caveman", "ponytail", "caveman"], library="~/my-lib")
        res = self.call_fn(f"gs.readManifest({json.dumps(str(self.root))}, {json.dumps(str(self.home))})")
        self.assertEqual(res["skills"], ["caveman", "ponytail"])
        self.assertEqual(Path(res["library"]), self.home / "my-lib")

    def test_missing_manifest_returns_null_and_exits_nonzero(self):
        res = self.call_fn(f"gs.checkGlobalSkills({{ root: {json.dumps(str(self.root))}, home: {json.dumps(str(self.home))} }})")
        self.assertIsNone(res)
        line = self.call_fn(f"gs.globalSkillsLine({json.dumps(str(self.root))}, {json.dumps(str(self.home))})")
        self.assertEqual(line, [])
        cli = self.run_cli()
        self.assertEqual(cli.returncode, 1)
        self.assertIn("global-skills.json not found", cli.stderr)

    def test_check_and_install_copies_from_library_and_links_both_agents(self):
        self.write_manifest(["alpha", "beta"])
        lib = self.home / "skill-library"
        write_skill(lib, "alpha")
        write_skill(lib, "beta")

        before = self.run_cli("--json")
        self.assertEqual(before.returncode, 1)
        self.assertEqual(
            json.loads(before.stdout),
            {"claude": ["alpha", "beta"], "antigravity": ["alpha", "beta"], "ok": False},
        )

        line = self.call_fn(f"gs.globalSkillsLine({json.dumps(str(self.root))}, {json.dumps(str(self.home))})")
        self.assertEqual(line, ["Global skills missing: alpha, beta (run npm run skills:global -- --install)"])

        install = self.run_cli("--install", "--json")
        self.assertEqual(install.returncode, 0, install.stderr)
        self.assertEqual(
            json.loads(install.stdout),
            {
                "copied": ["alpha", "beta"],
                "linked": ["claude:alpha", "claude:beta", "antigravity:skills"],
                "notInLibrary": [],
            },
        )

        self.assertTrue((self.home / ".agents" / "skills" / "alpha" / "SKILL.md").exists())
        self.assertTrue((self.home / ".claude" / "skills" / "alpha" / "SKILL.md").exists())
        self.assertTrue((self.home / ".gemini" / "config" / "skills" / "beta" / "SKILL.md").exists())

        after = self.run_cli("--json")
        self.assertEqual(after.returncode, 0)
        self.assertEqual(json.loads(after.stdout), {"claude": [], "antigravity": [], "ok": True})
        self.assertEqual(
            self.call_fn(f"gs.globalSkillsLine({json.dumps(str(self.root))}, {json.dumps(str(self.home))})"),
            [],
        )

    def test_install_links_individual_skills_when_antigravity_dir_is_real_folder(self):
        self.write_manifest(["alpha"])
        write_skill(self.home / "skill-library", "alpha")
        (self.home / ".gemini" / "config" / "skills").mkdir(parents=True)

        install = self.run_cli("--install", "--json")
        self.assertEqual(install.returncode, 0, install.stderr)
        data = json.loads(install.stdout)
        self.assertIn("antigravity:alpha", data["linked"])
        self.assertTrue((self.home / ".gemini" / "config" / "skills" / "alpha" / "SKILL.md").exists())

    def test_install_reports_skills_not_in_library_and_exits_nonzero(self):
        self.write_manifest(["alpha", "missing-skill"])
        write_skill(self.home / "skill-library", "alpha")

        install = self.run_cli("--install", "--json")
        self.assertEqual(install.returncode, 1)
        data = json.loads(install.stdout)
        self.assertEqual(data["copied"], ["alpha"])
        self.assertEqual(data["notInLibrary"], ["missing-skill"])


if __name__ == "__main__":
    unittest.main()
