import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.repo_fixture import REPO_ROOT, git_init


class TestWorkflow(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.preference = self.root / ".agents" / "workflow.local.json"

    def workflow(self, *args, root=None, ok=True):
        result = subprocess.run(
            ["node", str(REPO_ROOT / "scripts" / "workflow.mjs"), *args],
            cwd=root or self.root, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def blueprint(self, mode):
        (self.root / "project-blueprint.json").write_text(json.dumps({"workflow": {"mode": mode}}), encoding="utf-8")

    def test_all_presets_can_be_selected(self):
        modes = ("classic", "agy-build", "codex-solo", "claude-solo", "agy-solo", "codex-agy")
        listed = self.workflow("list").splitlines()
        for mode in modes:
            with self.subTest(mode=mode):
                self.assertIn(mode, listed)
                self.assertIn(f"Workflow: {mode} (local override)", self.workflow(mode))
                self.assertEqual(json.loads(self.preference.read_text()), {"mode": mode})

    def test_defaults_and_reset(self):
        self.assertIn("classic (built-in default)", self.workflow())
        (self.root / "project-blueprint.json").write_text("{}", encoding="utf-8")
        self.assertIn("classic (built-in default)", self.workflow("status"))
        self.blueprint("agy-build")
        self.assertIn("agy-build (blueprint default)", self.workflow("status"))
        self.assertIn("Default: agy-build", self.workflow("codex-solo"))
        self.assertIn("codex-solo (local override)", self.workflow("status"))
        for _ in range(2):
            self.assertIn("agy-build (blueprint default)", self.workflow("reset"))
        self.assertFalse(self.preference.exists())

    def test_invalid_mode_and_malformed_preference(self):
        self.blueprint("invalid")
        self.assertIn("project-blueprint.json", self.workflow("status", ok=False))
        self.assertIn("project-blueprint.json", self.workflow("codex-solo", ok=False))
        self.assertFalse(self.preference.exists())
        self.blueprint("classic")
        self.workflow("agy-solo")
        before = self.preference.read_bytes()
        self.assertIn("Unknown workflow preset", self.workflow("unknown", ok=False))
        self.assertEqual(self.preference.read_bytes(), before)
        self.preference.write_text("{oops secret-like data", encoding="utf-8")
        result = self.workflow("status", ok=False)
        self.assertIn("workflow.local.json", result)
        self.assertNotIn("secret-like", result)
        self.assertIn("classic", self.workflow("reset"))

    def test_reset_clears_preference_even_if_blueprint_is_invalid(self):
        self.workflow("claude-solo")
        self.blueprint("invalid")
        self.assertIn("project-blueprint.json", self.workflow("reset", ok=False))
        self.assertFalse(self.preference.exists())

    def test_checkout_local_and_only_ignored_file_changes(self):
        (self.root / ".gitignore").write_bytes((REPO_ROOT / ".gitignore").read_bytes())
        (self.root / "AGENTS.md").write_text("keep these rules", encoding="utf-8")
        handoff = self.root / ".agents" / "sync" / "handoff.md"
        handoff.parent.mkdir(parents=True)
        handoff.write_text("keep this handoff", encoding="utf-8")
        git_init(self.root)
        with tempfile.TemporaryDirectory() as other:
            self.workflow("claude-solo")
            self.assertIn("classic (built-in default)", self.workflow("status", root=Path(other)))
        result = subprocess.run(["git", "status", "--porcelain"], cwd=self.root, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, "")
        self.assertEqual(handoff.read_text(), "keep this handoff")
        self.assertEqual((self.root / "AGENTS.md").read_text(), "keep these rules")

    def test_switch_and_reset_preserve_mid_task_handoff(self):
        self.blueprint("classic")
        resume = self.root / ".agents" / "sync" / "resume.md"
        resume.parent.mkdir(parents=True)
        resume.write_text("Approved Tier 2 fix. Regression test still owed.\n", encoding="utf-8")
        self.workflow("codex-solo")
        self.assertIn("Tests and diagnosis: Codex", self.workflow("status"))
        self.workflow("reset")
        self.assertEqual(resume.read_text(encoding="utf-8"), "Approved Tier 2 fix. Regression test still owed.\n")
