import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import repo_fixture

STUB = Path(__file__).resolve().parent / "stubs" / "agy_stub.mjs"
REVIEW = repo_fixture.SCRIPTS / "review.mjs"
SPEC = "docs/specs/demo-design.md"
FIRST_PLAN = "docs/specs/2026-01-01-first-plan.md"
LAST_PLAN = "docs/specs/2026-02-02-second-plan.md"
PLAIN_PATHS_RULE = (
    "Reply in plain text. Refer to files by repo-relative path with forward slashes. "
    "Do not use Markdown links or absolute paths."
)


def git(root, *args):
    res = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
    return res.stdout.strip()


def commit_file(root, rel, text="module.exports = 1;\n"):
    target = Path(root) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", f"add {rel}")


class TestReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.args_file = Path(self.tmp.name) / "args.jsonl"  # outside the fixture so git never sees it
        self.root = self.make_fixture(Path(self.tmp.name) / "fixture", source_spec=SPEC, plans=True)
        # main stays at the fixture commit while work moves two commits ahead of it
        base = git(self.root, "rev-parse", "HEAD")
        git(self.root, "checkout", "-q", "-b", "work")
        commit_file(self.root, "src/alpha.js")
        commit_file(self.root, "src/beta.js")
        git(self.root, "branch", "-f", "main", base)

    def make_fixture(self, fixture, source_spec=None, plans=False):
        fixture.mkdir()
        root = repo_fixture.make_template_repo(fixture, skills=False)
        blueprint = json.loads((root / "project-blueprint.json").read_text(encoding="utf-8"))
        if source_spec:
            blueprint["project"]["source_spec"] = source_spec
        (root / "project-blueprint.json").write_text(json.dumps(blueprint, indent=2), encoding="utf-8")
        specs = root / "docs" / "specs"
        specs.mkdir(parents=True)
        (specs / "demo-design.md").write_text("# Demo design\n", encoding="utf-8")
        if plans:
            for name in ("2026-01-01-first-plan.md", "2026-02-02-second-plan.md"):
                (specs / name).write_text("# Plan\n", encoding="utf-8")
        return repo_fixture.git_init(root)

    def review(self, *flags, mode="success", root=None, cmd=None, env=None):
        """Run review.mjs as a subprocess from outside the fixture, with the stub wired in."""
        clean = {k: v for k, v in os.environ.items() if not k.startswith(("BATON_AGY_", "STUB_", "npm_config_"))}
        clean.update({"BATON_AGY_CMD": cmd or str(STUB), "STUB_MODE": mode, "STUB_ARGS_FILE": str(self.args_file), **(env or {})})
        argv = ["node", str(REVIEW), *flags, "--root", str(root or self.root)]
        return subprocess.run(argv, cwd=self.tmp.name, capture_output=True, text=True, env=clean)

    def recorded_args(self):
        return [json.loads(line) for line in self.args_file.read_text(encoding="utf-8").splitlines()]

    def prompt(self):
        return self.recorded_args()[0][1]

    def diff(self, root=None):
        return ((root or self.root) / ".agents" / "sync" / "review.diff").read_text(encoding="utf-8")

    def test_default_base_is_the_merge_base_with_main(self):
        res = self.review()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("src/alpha.js", self.diff())
        self.assertIn("src/beta.js", self.diff())

    def test_prompt_names_the_diff_spec_and_last_plan_and_is_read_only(self):
        self.review()
        args = self.recorded_args()[0]
        self.assertNotIn("--mode", args)
        prompt = args[1]
        self.assertIn(".agents/sync/review.diff", prompt)
        self.assertIn(SPEC, prompt)
        self.assertIn(LAST_PLAN, prompt)
        self.assertNotIn(FIRST_PLAN, prompt)
        for heading in ("Critical", "Important", "Minor"):
            self.assertIn(heading, prompt)
        self.assertIn("at most 60 lines", prompt)
        self.assertIn("Read only. Edit nothing. Run nothing.", prompt)
        self.assertTrue(prompt.endswith(PLAIN_PATHS_RULE), prompt)

    def test_the_prompt_asks_for_line_numbers_from_the_file_before_the_plain_paths_rule(self):
        self.review()
        prompt = self.prompt()
        sentence = "Give line numbers from the file itself, not positions in the diff file."
        self.assertIn(sentence, prompt)
        self.assertLess(prompt.index(sentence), prompt.index(PLAIN_PATHS_RULE))
        self.assertTrue(prompt.endswith(PLAIN_PATHS_RULE), prompt)

    def test_base_flag_picks_the_diff_range(self):
        res = self.review("--base", "HEAD~1")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("src/beta.js", self.diff())
        self.assertNotIn("src/alpha.js", self.diff())

    def test_a_launch_is_announced_with_its_range(self):
        res = self.review("--base", "HEAD~1")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.splitlines(), ["[Review] Reviewing HEAD~1..HEAD", "ok"])

    def test_npm_config_base_selects_the_base_when_the_flag_is_absent(self):
        # npm swallows `--base x` after `npm run review` and exports it as npm_config_base
        res = self.review(env={"npm_config_base": "HEAD~1"})
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("src/beta.js", self.diff())
        self.assertNotIn("src/alpha.js", self.diff())
        self.assertIn("[Review] Reviewing HEAD~1..HEAD", res.stdout.splitlines())

    def test_the_base_flag_wins_over_npm_config_base(self):
        res = self.review("--base", "HEAD~1", env={"npm_config_base": "HEAD~2"})
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("src/beta.js", self.diff())
        self.assertNotIn("src/alpha.js", self.diff())
        self.assertIn("[Review] Reviewing HEAD~1..HEAD", res.stdout.splitlines())

    def test_npm_config_spec_and_plan_apply_unless_the_flags_are_given(self):
        self.review(env={"npm_config_spec": "docs/specs/env-design.md", "npm_config_plan": "docs/specs/env-plan.md"})
        self.assertIn("docs/specs/env-design.md", self.prompt())
        self.assertIn("docs/specs/env-plan.md", self.prompt())
        self.args_file.unlink()
        self.review("--spec", "docs/specs/flag-design.md", "--plan", "docs/specs/flag-plan.md",
                    env={"npm_config_spec": "docs/specs/env-design.md", "npm_config_plan": "docs/specs/env-plan.md"})
        self.assertIn("docs/specs/flag-design.md", self.prompt())
        self.assertIn("docs/specs/flag-plan.md", self.prompt())
        self.assertNotIn("env-design", self.prompt())
        self.assertNotIn("env-plan", self.prompt())

    def test_without_a_main_branch_the_base_is_head_minus_one(self):
        git(self.root, "branch", "-D", "main")
        self.assertEqual(self.review().returncode, 0)
        self.assertIn("src/beta.js", self.diff())
        self.assertNotIn("src/alpha.js", self.diff())

    def test_main_at_head_makes_the_base_head_minus_one(self):
        git(self.root, "branch", "-f", "main", "HEAD")
        self.assertEqual(self.review().returncode, 0)
        self.assertIn("src/beta.js", self.diff())
        self.assertNotIn("src/alpha.js", self.diff())

    def test_a_single_commit_repo_has_nothing_to_review(self):
        root = self.make_fixture(Path(self.tmp.name) / "single")
        res = self.review(root=root)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "[Review] Nothing to review.")
        self.assertFalse(self.args_file.exists())

    def test_an_empty_diff_launches_nothing(self):
        res = self.review("--base", "HEAD")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "[Review] Nothing to review.")
        self.assertFalse(self.args_file.exists())
        self.assertFalse((self.root / ".agents" / "sync" / "review.md").exists())

    def test_spec_and_plan_flags_override_the_defaults(self):
        res = self.review("--spec", "docs/specs/other-design.md", "--plan", "docs/specs/other-plan.md")
        self.assertEqual(res.returncode, 0, res.stderr)
        prompt = self.prompt()
        self.assertIn("docs/specs/other-design.md", prompt)
        self.assertIn("docs/specs/other-plan.md", prompt)
        self.assertNotIn(SPEC, prompt)
        self.assertNotIn(LAST_PLAN, prompt)

    def test_an_absolute_path_is_made_repo_relative_with_forward_slashes(self):
        absolute = self.root / "docs" / "specs" / "demo-design.md"
        self.review("--spec", str(absolute))
        self.assertIn(f" {SPEC}", self.prompt())
        self.assertNotIn("\\", self.prompt())

    def test_absent_spec_and_plan_are_left_out(self):
        root = self.make_fixture(Path(self.tmp.name) / "bare")
        commit_file(root, "src/one.js")
        res = self.review(root=root)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("demo-design", self.prompt())
        self.assertNotIn("-plan.md", self.prompt())

    def test_the_review_is_written_and_printed_unchanged(self):
        res = self.review()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.splitlines()[-1], "ok")
        self.assertEqual((self.root / ".agents" / "sync" / "review.md").read_text(encoding="utf-8").strip(), "ok")

    def test_files_written_under_agents_sync_are_not_a_scope_violation(self):
        first = self.review()
        second = self.review()  # review.diff, review.md and handoff.json now exist from the first run
        self.assertEqual((first.returncode, second.returncode), (0, 0), first.stderr + second.stderr)
        self.assertEqual(git(self.root, "status", "--porcelain"), "")

    def test_unavailable_exits_1_with_one_line_and_no_review(self):
        res = self.review(mode="garbage")
        self.assertEqual(res.returncode, 1)
        self.assertEqual(res.stderr.strip(), "[Review] Antigravity unavailable (failed: this is not json).")
        self.assertFalse((self.root / ".agents" / "sync" / "review.md").exists())

    def test_a_missing_agy_is_not_installed(self):
        res = self.review(cmd="definitely-not-a-real-agy-binary")
        self.assertEqual(res.returncode, 1)
        self.assertEqual(res.stderr.strip(), "[Review] Antigravity unavailable (not_installed).")

    def test_a_source_file_written_by_agy_exits_1_and_writes_no_review(self):
        res = self.review(mode="write_source")
        self.assertEqual(res.returncode, 1)
        self.assertIn("src/rogue.js", res.stderr)
        self.assertFalse((self.root / ".agents" / "sync" / "review.md").exists())

    def test_an_unknown_base_fails_without_launching(self):
        res = self.review("--base", "no-such-ref")
        self.assertEqual(res.returncode, 1)
        self.assertIn("[Review]", res.stderr)
        self.assertFalse(self.args_file.exists())

    def test_the_delegation_entry_lands_in_handoff_json(self):
        self.review()
        state = json.loads((self.root / ".agents" / "sync" / "handoff.json").read_text(encoding="utf-8"))
        entry = state["delegations"][0]
        self.assertEqual(entry["job"], "review")
        self.assertTrue(entry["ok"])
        self.assertEqual(entry["total_tokens"], 1234)

    def test_review_uses_the_deep_model_and_records_it(self):
        self.review()
        args = self.recorded_args()[0]
        self.assertEqual(args[args.index("--model") + 1], "gemini-4-argon-medium")
        state = json.loads((self.root / ".agents" / "sync" / "handoff.json").read_text(encoding="utf-8"))
        self.assertEqual(state["delegations"][0]["model"], "gemini-4-argon-medium")


if __name__ == "__main__":
    unittest.main()
