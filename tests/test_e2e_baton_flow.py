import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import repo_fixture

REPO_ROOT = repo_fixture.REPO_ROOT
BATON = repo_fixture.SCRIPTS / "baton.mjs"


class TestE2EBatonFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.sync_json = Path(self.tmp.name) / "handoff.json"

        initial_state = {
            "version": "1.0",
            "task_id": "TEST-01",
            "active_agent": "claude",
            "status": "idle",
            "turn_count": 0,
            "max_turns": 5,
            "last_updated": "2026-10-08T00:00:00.000Z",
            "summary": "E2E testing",
            "files_modified": []
        }
        with open(self.sync_json, "w", encoding="utf-8") as f:
            json.dump(initial_state, f)

    def make_fixture(self):
        """A git-initialised template repo, separate from the sync file used by the snippet tests."""
        fixture_tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(fixture_tmp.cleanup)
        return repo_fixture.git_init(repo_fixture.make_template_repo(fixture_tmp.name, skills=False))

    def make_verify_fixture(self, test_command, scoped_command=None):
        """An initialized project whose last commit changed only src/app.js and whose tree is clean."""
        fixture_tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(fixture_tmp.cleanup)
        root = repo_fixture.make_template_repo(fixture_tmp.name, skills=False)
        blueprint_path = root / "project-blueprint.json"
        blueprint = json.loads(blueprint_path.read_text(encoding="utf-8"))
        blueprint["status"] = "initialized"
        blueprint["project"] = {"verify": {"test": test_command}}
        if scoped_command:
            blueprint["project"]["verify"]["test_scoped"] = scoped_command
        blueprint_path.write_text(json.dumps(blueprint, indent=2) + "\n", encoding="utf-8")
        repo_fixture.git_init(root)
        (root / "src").mkdir()
        (root / "src" / "app.js").write_text("module.exports = 1;\n", encoding="utf-8")
        for args in (["add", "-A"], ["commit", "-q", "-m", "add app"]):
            subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
        return root

    def baton(self, fixture, *args, env=None):
        cmd = ["node", str(BATON), *args, "--root", str(fixture)]
        base_env = {k: v for k, v in os.environ.items() if k not in ("npm_config_tier", "npm_config_scope", "BATON_HOOK")}
        base_env["BATON_GATEKEEPER"] = "0"  # these runs are about the gate, so they must never launch the real agy
        return subprocess.run(cmd, cwd=fixture, capture_output=True, text=True, env={**base_env, **(env or {})}, timeout=45)

    def test_tier_1_express_pass(self):
        code = f"""
        import {{ readSyncState, writeSyncState }} from './scripts/baton.mjs';
        const state = readSyncState({json.dumps(str(self.sync_json))});
        state.status = 'verified';
        writeSyncState(state, {json.dumps(str(self.sync_json))});
        """
        res = repo_fixture.run_node(code)
        self.assertEqual(res.returncode, 0, res.stderr)

        with open(self.sync_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["status"], "verified")

    def test_circuit_breaker_halts_at_max_turns(self):
        state = {
            "version": "1.0",
            "task_id": "TEST-02",
            "active_agent": "claude",
            "status": "verification_failed",
            "turn_count": 5,
            "max_turns": 5,
            "last_updated": "2026-10-08T00:00:00.000Z",
            "summary": "Failing loop",
            "files_modified": ["src/app.ts"]
        }
        with open(self.sync_json, "w", encoding="utf-8") as f:
            json.dump(state, f)

        code = f"""
        import {{ checkCircuitBreaker, readSyncState }} from './scripts/baton.mjs';
        const st = readSyncState({json.dumps(str(self.sync_json))});
        if (!checkCircuitBreaker(st)) {{
            process.exit(42);
        }}
        """
        res = repo_fixture.run_node(code)
        self.assertEqual(res.returncode, 42, "Circuit breaker should have halted execution with exit 42")

    def test_cli_status_command(self):
        res = self.baton(self.make_fixture(), "status")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("=== Baton Sync Status ===", res.stdout)
        self.assertIn("Detected Tier:", res.stdout)

    def test_cli_verify_tier1_express(self):
        res = self.baton(self.make_fixture(), "verify", "--tier", "1")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Tier 1 Express Lane", res.stdout)

    def test_workflow_presets_control_test_writing_and_failure_diagnosis(self):
        test_cmd = 'node -e "console.error(123); process.exit(1)"'
        for preset in ("codex-solo", "claude-solo", "agy-solo", "codex-agy", "classic", "agy-build"):
            with self.subTest(preset=preset):
                fixture = self.make_verify_fixture(test_cmd)
                preference = fixture / ".agents" / "workflow.local.json"
                preference.write_text(json.dumps({"mode": preset}), encoding="utf-8")
                args_file = Path(self.tmp.name) / f"{preset}.jsonl"
                env = {
                    "BATON_GATEKEEPER": "1", "BATON_AGY_CMD": str(REPO_ROOT / "tests" / "stubs" / "agy_stub.mjs"),
                    "BATON_DIAGNOSE_MIN_LINES": "0", "STUB_MODE": "success", "STUB_ARGS_FILE": str(args_file),
                    "VERIFY_LOCK_HELD": "1",  # isolated fixture, independent of the parent's machine-wide lock
                }
                res = self.baton(fixture, "verify", "--full", env=env)
                self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                self.assertIn("FAIL: Verification failed", res.stderr)
                count = len(args_file.read_text(encoding="utf-8").splitlines()) if args_file.exists() else 0
                expected = int(preset in ("classic", "codex-agy")) + int(not preset.endswith("-solo"))
                self.assertEqual(count, expected, res.stdout + res.stderr)
                self.assertIn(f"Workflow: {preset} (local override)", self.baton(fixture, "status").stdout)

    def test_root_flag_isolates_state(self):
        fixture = self.make_fixture()
        real_json = REPO_ROOT / ".agents" / "sync" / "handoff.json"
        real_before = real_json.read_bytes()
        fixture_json = fixture / ".agents" / "sync" / "handoff.json"
        fixture_before = fixture_json.read_bytes()

        res = self.baton(fixture, "verify", "--tier", "1")
        self.assertEqual(res.returncode, 0, res.stderr)

        self.assertNotEqual(fixture_json.read_bytes(), fixture_before)
        self.assertEqual(json.loads(fixture_json.read_text(encoding="utf-8"))["status"], "verified")
        self.assertEqual(real_json.read_bytes(), real_before)

    def test_clean_tree_verifies_the_last_commit(self):
        fixture = self.make_verify_fixture('node -e "process.exit(0)"')
        res = self.baton(fixture, "verify")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Working tree clean: classifying the last commit.", res.stdout)
        self.assertIn('Executing test command: node -e "process.exit(0)"', res.stdout)
        self.assertNotIn("Express Lane", res.stdout)

    def test_clean_tree_with_failing_test_fails_and_counts_a_turn(self):
        fixture = self.make_verify_fixture('node -e "process.exit(1)"')
        res = self.baton(fixture, "verify")
        self.assertEqual(res.returncode, 1, res.stdout)
        state = json.loads((fixture / ".agents" / "sync" / "handoff.json").read_text(encoding="utf-8"))
        self.assertEqual(state["turn_count"], 1)
        self.assertEqual(state["status"], "verification_failed")

    def test_npm_config_tier_selects_the_tier(self):
        fixture = self.make_verify_fixture('node -e "process.exit(1)"')
        res = self.baton(fixture, "verify", env={"npm_config_tier": "1"})
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Tier 1 Express Lane", res.stdout)

    def test_flag_beats_npm_config_tier(self):
        fixture = self.make_verify_fixture('node -e "process.exit(1)"')
        res = self.baton(fixture, "verify", "--tier", "2", env={"npm_config_tier": "1"})
        self.assertEqual(res.returncode, 1)
        self.assertNotIn("Express Lane", res.stdout)

    def test_root_flag_without_value_fails(self):
        res = subprocess.run(["node", str(BATON), "status", "--root"], cwd=self.tmp.name, capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)
        self.assertIn("--root", res.stderr)

    def test_outstanding_tests_are_separate_from_a_passing_solo_run(self):
        command = 'node -e "process.exit(0)"'
        fixture = self.make_verify_fixture(command, scoped_command=command)
        stub = REPO_ROOT / "tests" / "stubs" / "agy_stub.mjs"
        res = self.baton(fixture, "verify", "--full", env={"BATON_GATEKEEPER": "1", "BATON_AGY_CMD": str(stub), "STUB_MODE": "status_timeout"})
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("Gatekeeper skipped", res.stdout)
        local = fixture / ".agents" / "workflow.local.json"
        local.write_text('{"mode":"codex-solo"}', encoding="utf-8")
        solo = self.baton(fixture, "verify", "--full")
        self.assertEqual(solo.returncode, 0, solo.stderr)
        status = self.baton(fixture, "status").stdout
        self.assertIn("Status:       verified", status)
        self.assertIn("Tests owed:   src/app.js (owner: Codex)", status)
        # A scoped run names the existing test that covers this source edit.
        (fixture / "tests").mkdir()
        (fixture / "tests" / "app.test.js").write_text("// fixture covering test\n", encoding="utf-8")
        (fixture / "src" / "app.js").write_text("module.exports = 2;\n", encoding="utf-8")
        scoped = self.baton(fixture, "verify", "--tier", "2", "--scope", "tests/app.test.js")
        self.assertEqual(scoped.returncode, 0, scoped.stdout + scoped.stderr)
        self.assertNotIn("Tests owed:", self.baton(fixture, "status").stdout)

    def test_solo_source_edit_does_not_record_test_debt_from_the_heuristic(self):
        fixture = self.make_verify_fixture('node -e "process.exit(0)"')
        (fixture / ".agents" / "workflow.local.json").write_text('{"mode":"claude-solo"}', encoding="utf-8")
        res = self.baton(fixture, "verify", "--full")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("Tests owed:", self.baton(fixture, "status").stdout)

    def test_missing_sync_directory_is_created(self):
        # A project that is not a template clone has no .agents/sync directory yet
        bare_tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(bare_tmp.cleanup)
        bare = Path(bare_tmp.name)
        bare.joinpath("README.md").write_text("# bare" + chr(10), encoding="utf-8")
        repo_fixture.git_init(bare)

        res = self.baton(bare, "status")

        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("Unexpected error", res.stderr)
        self.assertTrue(bare.joinpath(".agents", "sync", "handoff.json").exists())

    def test_baton_state_is_never_part_of_the_change_set(self):
        # Without the template's .gitignore, the state files are untracked; they must not count as changes
        bare_tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(bare_tmp.cleanup)
        bare = Path(bare_tmp.name)
        bare.joinpath("README.md").write_text("# bare" + chr(10), encoding="utf-8")
        repo_fixture.git_init(bare)
        self.baton(bare, "status")  # creates .agents/sync/handoff.json, untracked and not ignored

        code = f"""
        import {{ resolveChangeSet }} from './scripts/changes.mjs';
        console.log(JSON.stringify(resolveChangeSet({json.dumps(str(bare))})));
        """
        res = repo_fixture.run_node(code)
        self.assertEqual(res.returncode, 0, res.stderr)
        change_set = json.loads(res.stdout)
        self.assertEqual([f for f in change_set["files"] if f.startswith(".agents/sync/")], [])

    # The commit hook does not repeat a run that already passed on the same content

    def counted(self, letter="t", exit_code=0):
        return f"node -e \"require('fs').appendFileSync(process.env.RUNS_FILE, '{letter}'); process.exit({exit_code})\""

    def counter_env(self, **extra):
        return {"RUNS_FILE": str(Path(self.tmp.name) / "runs.txt"), **extra}

    def runs(self):
        path = Path(self.tmp.name) / "runs.txt"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    SKIP_LINE = "[Baton] Already verified for this content; skipping."

    def test_the_hook_skips_a_run_that_already_passed_on_the_same_content(self):
        fixture = self.make_verify_fixture(self.counted())
        self.assertEqual(self.baton(fixture, "verify", env=self.counter_env()).returncode, 0)
        res = self.baton(fixture, "verify", env=self.counter_env(BATON_HOOK="1"))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn(self.SKIP_LINE, res.stdout)
        self.assertNotIn("Verifying changes", res.stdout)
        self.assertEqual(self.runs(), "t")

    def test_the_skip_leaves_the_handoff_untouched(self):
        fixture = self.make_verify_fixture(self.counted())
        self.baton(fixture, "verify", env=self.counter_env())
        paths = [fixture / ".agents" / "sync" / name for name in ("handoff.json", "handoff.md")]
        before = [path.read_bytes() for path in paths]
        self.baton(fixture, "verify", env=self.counter_env(BATON_HOOK="1"))
        self.assertEqual([path.read_bytes() for path in paths], before)

    def test_editing_a_file_between_the_runs_makes_the_hook_run_the_command(self):
        fixture = self.make_verify_fixture(self.counted())
        self.baton(fixture, "verify", env=self.counter_env())
        (fixture / "src" / "app.js").write_text("module.exports = 2;\n", encoding="utf-8")
        res = self.baton(fixture, "verify", env=self.counter_env(BATON_HOOK="1"))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn(self.SKIP_LINE, res.stdout)
        self.assertEqual(self.runs(), "tt")

    def test_a_scoped_first_run_does_not_let_the_hook_skip(self):
        fixture = self.make_verify_fixture(self.counted("t"), scoped_command=self.counted("s") + " {scope}")
        self.baton(fixture, "verify", "--tier", "2", "--scope", "x", env=self.counter_env())
        res = self.baton(fixture, "verify", env=self.counter_env(BATON_HOOK="1"))
        self.assertNotIn(self.SKIP_LINE, res.stdout)
        self.assertEqual(self.runs(), "st")

    def test_a_failing_first_run_does_not_let_the_hook_skip(self):
        fixture = self.make_verify_fixture(self.counted("t", 1))
        self.assertEqual(self.baton(fixture, "verify", env=self.counter_env()).returncode, 1)
        res = self.baton(fixture, "verify", env=self.counter_env(BATON_HOOK="1"))
        self.assertNotIn(self.SKIP_LINE, res.stdout)
        self.assertEqual(self.runs(), "tt")

    def test_without_the_hook_variable_nothing_is_skipped(self):
        fixture = self.make_verify_fixture(self.counted())
        self.baton(fixture, "verify", env=self.counter_env())
        res = self.baton(fixture, "verify", env=self.counter_env())
        self.assertNotIn(self.SKIP_LINE, res.stdout)
        self.assertEqual(self.runs(), "tt")

    def test_a_tier_1_pass_lets_the_hook_skip_on_the_same_content(self):
        fixture = self.make_verify_fixture(self.counted())
        self.assertEqual(self.baton(fixture, "verify", "--tier", "1", env=self.counter_env()).returncode, 0)
        res = self.baton(fixture, "verify", "--tier", "1", env=self.counter_env(BATON_HOOK="1"))
        self.assertIn(self.SKIP_LINE, res.stdout)
        self.assertEqual(self.runs(), "")


if __name__ == "__main__":
    unittest.main()
