import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import repo_fixture

STUB = Path(__file__).resolve().parent / "stubs" / "agy_stub.mjs"
SCOUT = repo_fixture.SCRIPTS / "scout.mjs"
SPEC = "docs/specs/demo-design.md"
PLAIN_PATHS_RULE = (
    "Reply in plain text. Refer to files by repo-relative path with forward slashes. "
    "Do not use Markdown links or absolute paths."
)


class TestScout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.args_file = Path(self.tmp.name) / "args.jsonl"  # outside the fixture so git never sees it
        self.root = self.make_fixture(Path(self.tmp.name) / "fixture", source_spec=SPEC)

    def make_fixture(self, fixture, source_spec=None):
        fixture.mkdir()
        root = repo_fixture.make_template_repo(fixture, skills=False)
        blueprint = json.loads((root / "project-blueprint.json").read_text(encoding="utf-8"))
        if source_spec:
            blueprint["project"]["source_spec"] = source_spec
        (root / "project-blueprint.json").write_text(json.dumps(blueprint, indent=2), encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "app.js").write_text("module.exports = 1;\n", encoding="utf-8")
        return repo_fixture.git_init(root)

    def scout(self, *words, mode="success", root=None, cmd=None, extra=()):
        """Run scout.mjs as a subprocess from outside the fixture, with the stub wired in."""
        env = {k: v for k, v in os.environ.items() if not k.startswith(("BATON_AGY_", "STUB_"))}
        env.update({"BATON_AGY_CMD": cmd or str(STUB), "STUB_MODE": mode, "STUB_ARGS_FILE": str(self.args_file)})
        argv = ["node", str(SCOUT), *words, "--root", str(root or self.root), *extra]
        return subprocess.run(argv, cwd=self.tmp.name, capture_output=True, text=True, env=env)

    def recorded_args(self):
        return [json.loads(line) for line in self.args_file.read_text(encoding="utf-8").splitlines()]

    def prompt(self):
        return self.recorded_args()[0][1]

    def sync_state(self, root=None):
        return json.loads(((root or self.root) / ".agents" / "sync" / "handoff.json").read_text(encoding="utf-8"))

    def test_prompt_names_the_task_plan_and_spec_and_is_read_only(self):
        res = self.scout("add login")
        self.assertEqual(res.returncode, 0, res.stderr)
        args = self.recorded_args()[0]
        self.assertEqual(args[0], "--print")
        self.assertNotIn("--mode", args)
        prompt = args[1]
        self.assertIn("add login", prompt)
        self.assertIn("docs/PLAN.md", prompt)
        self.assertIn(SPEC, prompt)
        self.assertIn("at most 40 lines", prompt)
        self.assertIn("Read only. Edit nothing. Run nothing.", prompt)
        self.assertTrue(prompt.endswith(PLAIN_PATHS_RULE), prompt)

    def test_scout_uses_the_fast_model_and_records_it(self):
        self.scout("add login")
        args = self.recorded_args()[0]
        self.assertEqual(args[args.index("--model") + 1], "gemini-4-argon-low")
        self.assertEqual(self.sync_state()["delegations"][0]["model"], "gemini-4-argon-low")

    def test_a_blueprint_without_a_source_spec_names_only_the_plan(self):
        root = self.make_fixture(Path(self.tmp.name) / "plain")
        res = self.scout("add login", root=root)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("docs/PLAN.md", self.prompt())
        self.assertNotIn("demo-design", self.prompt())

    def test_words_arrive_as_separate_arguments_and_join_with_a_space(self):
        res = self.scout("add", "login", "page")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("add login page", self.prompt())

    def test_no_task_prints_usage_and_launches_nothing(self):
        res = self.scout()
        self.assertEqual(res.returncode, 1)
        self.assertIn("Usage", res.stderr)
        self.assertFalse(self.args_file.exists())

    def test_the_brief_is_written_and_printed_unchanged(self):
        res = self.scout("add login")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "ok")
        brief = self.root / ".agents" / "sync" / "scout.md"
        self.assertEqual(brief.read_text(encoding="utf-8").strip(), "ok")

    def test_files_written_under_agents_sync_are_not_a_scope_violation(self):
        first = self.scout("add login")
        second = self.scout("add login again")  # scout.md and handoff.json now exist from the first run
        self.assertEqual((first.returncode, second.returncode), (0, 0), first.stderr + second.stderr)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(status.stdout, "")

    def test_unavailable_exits_0_with_one_line_and_no_brief(self):
        res = self.scout("add login", mode="garbage")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "[Scout] Antigravity unavailable (failed: this is not json).")
        self.assertFalse((self.root / ".agents" / "sync" / "scout.md").exists())

    def test_a_missing_agy_is_not_installed(self):
        res = self.scout("add login", cmd="definitely-not-a-real-agy-binary")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "[Scout] Antigravity unavailable (not_installed).")

    def test_a_source_file_written_by_agy_exits_1_and_writes_no_brief(self):
        res = self.scout("add login", mode="write_source")
        self.assertEqual(res.returncode, 1)
        self.assertIn("src/rogue.js", res.stderr)
        self.assertNotEqual(res.stdout.strip(), "ok")
        self.assertFalse((self.root / ".agents" / "sync" / "scout.md").exists())

    def test_the_delegation_entry_lands_in_handoff_json(self):
        self.scout("add login")
        entry = self.sync_state()["delegations"][0]
        self.assertEqual(entry["job"], "scout")
        self.assertTrue(entry["ok"])
        self.assertEqual(entry["total_tokens"], 1234)

    def test_a_failed_launch_is_recorded_too(self):
        self.scout("add login", mode="denied")
        entry = self.sync_state()["delegations"][0]
        self.assertFalse(entry["ok"])
        self.assertEqual(entry["reason"], "denied")


if __name__ == "__main__":
    unittest.main()
