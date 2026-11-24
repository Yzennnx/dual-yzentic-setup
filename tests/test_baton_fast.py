import json
import subprocess
import unittest
from pathlib import Path

from tests import test_gatekeeper as tg
from tests.test_gatekeeper import BATON, appender, git
from tests.test_baton_speed import ROUTES


def git_out(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True).stdout.strip()


class TestBatonFast(unittest.TestCase):
    """Fast verify on feature branches, one full verify per branch, and merge only after it."""

    setUp = tg.TestGatekeeper.setUp
    write = tg.TestGatekeeper.write
    make_fixture = tg.TestGatekeeper.make_fixture
    baton = tg.TestGatekeeper.baton
    runs = tg.TestGatekeeper.runs
    e2e_env = tg.TestGatekeeper.e2e_env

    def on_branch(self, changes, routes=ROUTES, commit=False):
        root = self.make_fixture(test_command=appender("T"), changes=changes, verify={"routes": routes})
        git(root, "checkout", "-q", "-b", "feat/x")
        if commit:
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "task")
        return root

    def verify(self, root, *flags):
        (Path(self.tmp.name) / "runs.txt").unlink(missing_ok=True)
        res = self.baton(root, "--no-gatekeeper", *flags, env=self.e2e_env())
        return res, self.runs()

    def merge(self, root, branch):
        return subprocess.run(["node", str(BATON), "merge", branch, "--root", str(root)], capture_output=True, text=True)

    def test_fast_verify_runs_only_the_routes_the_change_touches(self):
        res, runs = self.verify(self.on_branch({"a/x.js": "1;\n", "c/z.js": "1;\n"}))
        self.assertEqual((res.returncode, runs), (0, "SA"), res.stdout + res.stderr)  # no full command for c/z.js

    def test_fast_verify_with_no_route_runs_no_tests(self):
        res, runs = self.verify(self.on_branch({"c/z.js": "1;\n"}))
        self.assertEqual((res.returncode, runs), (0, ""), res.stdout + res.stderr)
        self.assertIn("the full run before merge tests them", res.stdout)

    def test_full_runs_the_whole_suite_and_notes_the_tip(self):
        root = self.on_branch({"a/x.js": "1;\n"}, commit=True)
        res, runs = self.verify(root, "--full")
        self.assertEqual((res.returncode, runs), (0, "T"), res.stdout + res.stderr)
        self.assertIn("full verify passed", git_out(root, "notes", "--ref=baton", "show", "HEAD"))

    def test_full_runs_even_for_a_docs_only_tip(self):
        res, runs = self.verify(self.on_branch({"README.md": "docs\n"}, commit=True), "--full")
        self.assertEqual(runs, "T")

    def test_full_with_uncommitted_changes_records_nothing(self):
        root = self.on_branch({"a/x.js": "1;\n"})
        res, runs = self.verify(root, "--full")
        self.assertEqual(runs, "T")
        self.assertIn("not recorded", res.stdout)
        self.assertEqual(git_out(root, "notes", "--ref=baton", "list"), "")

    def test_main_keeps_the_full_command_for_uncovered_files(self):
        root = self.make_fixture(test_command=appender("T"), changes={"c/z.js": "1;\n"}, verify={"routes": ROUTES})
        res, runs = self.verify(root)
        self.assertEqual(runs, "T")

    def test_merge_refuses_a_branch_without_a_full_verify(self):
        root = self.on_branch({"a/x.js": "1;\n"}, commit=True)
        main = git_out(root, "rev-parse", "--abbrev-ref", "@{-1}")
        git(root, "checkout", "-q", main)
        res = self.merge(root, "feat/x")
        self.assertEqual(res.returncode, 1)
        self.assertIn("no full verify", res.stderr)
        self.assertNotEqual(git_out(root, "rev-parse", "HEAD"), git_out(root, "rev-parse", "feat/x"))

    def test_merge_fast_forwards_after_a_full_verify(self):
        root = self.on_branch({"a/x.js": "1;\n"}, commit=True)
        self.verify(root, "--full")
        main = git_out(root, "rev-parse", "--abbrev-ref", "@{-1}")
        git(root, "checkout", "-q", main)
        res = self.merge(root, "feat/x")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(git_out(root, "rev-parse", "HEAD"), git_out(root, "rev-parse", "feat/x"))

    def test_e2e_scope_and_merge_trigger_tracking(self):
        root = self.make_fixture(
            test_command=appender("T"),
            changes={"src/ui.js": "1;\n"},
            verify={
                "test_scoped": appender("U") + " {scope}",
                "e2e": appender("E"),
                "e2e_scoped": appender("S") + " {scope}",
                "e2e_blast_radius": ["prisma/"],
            },
        )
        # Seed e2e-state.json with 2 merges and verify --e2e-scope + --scope does not reset it
        e2e_state_path = root / ".agents" / "sync" / "e2e-state.json"
        e2e_state_path.write_text(
            json.dumps({"merges_since_full_e2e": 2, "tier3_since_full_e2e": 0, "blast_radius_pending": False}),
            encoding="utf-8",
        )
        res, ran = self.verify(root, "--scope", "tests/ui.test.js", "--e2e-scope", "e2e/ui.e2e.ts")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(ran, "US")
        self.assertEqual(json.loads(e2e_state_path.read_text(encoding="utf-8"))["merges_since_full_e2e"], 2)

        # Merging a blast-radius branch increments counters and prints Full E2E due notice
        default_branch = git_out(root, "rev-parse", "--abbrev-ref", "HEAD")
        git(root, "checkout", "-q", "-b", "feat/schema")
        self.write(root, "prisma/schema.prisma", "model User {}\n")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "schema")
        res, ran = self.verify(root, "--full", "--e2e-scope", "e2e/auth.e2e.ts")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(ran, "TS")

        git(root, "checkout", "-q", default_branch)
        merge_res = self.merge(root, "feat/schema")
        self.assertEqual(merge_res.returncode, 0, merge_res.stderr)
        self.assertIn("[Baton] Full E2E due (blast-radius path merged)", merge_res.stdout)
        state_after_merge = json.loads(e2e_state_path.read_text(encoding="utf-8"))
        self.assertEqual(state_after_merge["merges_since_full_e2e"], 3)
        self.assertTrue(state_after_merge["blast_radius_pending"])

        # sync:reset preserves e2e-state.json
        reset_res = subprocess.run(["node", str(BATON), "reset", "--root", str(root)], capture_output=True, text=True)
        self.assertEqual(reset_res.returncode, 0, reset_res.stderr)
        self.assertTrue(e2e_state_path.exists())
        self.assertEqual(json.loads(e2e_state_path.read_text(encoding="utf-8"))["merges_since_full_e2e"], 3)

        # Full --e2e resets e2e-state.json
        res, ran = self.verify(root, "--e2e")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(ran, "TE")
        self.assertEqual(
            json.loads(e2e_state_path.read_text(encoding="utf-8")),
            {"merges_since_full_e2e": 0, "tier3_since_full_e2e": 0, "blast_radius_pending": False},
        )


if __name__ == "__main__":
    unittest.main()
