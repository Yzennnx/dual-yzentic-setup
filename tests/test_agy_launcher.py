import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import repo_fixture

STUB = Path(__file__).resolve().parent / "stubs" / "agy_stub.mjs"
BATON = repo_fixture.SCRIPTS / "baton.mjs"
PROMPT = "do the thing"
DEFAULT_ARGS = ["--print", PROMPT, "--output-format", "json", "--print-timeout", "30s", "--model", "gemini-4-argon-medium"]


class TestAgyLauncher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.args_file = Path(self.tmp.name) / "args.jsonl"  # outside the fixture so git never sees it
        fixture = Path(self.tmp.name) / "fixture"
        fixture.mkdir()
        (fixture / "src").mkdir()
        (fixture / "src" / "app.js").write_text("module.exports = 1;\n", encoding="utf-8")
        (fixture / "README.md").write_text("# fixture\n", encoding="utf-8")
        self.root = repo_fixture.git_init(fixture)

    def snippet(self, body, mode="success", cmd=None, env=None):
        """Run an ES module snippet with the stub wired in through process.env (run_node inherits our env)."""
        settings = {"BATON_AGY_CMD": cmd or str(STUB), "STUB_MODE": mode, "STUB_ARGS_FILE": str(self.args_file), **(env or {})}
        sets = "\n".join(f"process.env[{json.dumps(k)}] = {json.dumps(v)};" for k, v in settings.items())
        code = f"""
        import {{ launchAgy, appendDelegation, processTimeoutMs, timeoutForJob }} from './scripts/agy.mjs';
        import {{ snapshotChanges, checkScope }} from './scripts/changes.mjs';
        delete process.env.BATON_AGY_MODEL;
        delete process.env.BATON_AGY_MODEL_FAST;
        delete process.env.BATON_AGY_MODEL_DEEP;
        delete process.env.BATON_AGY_TIMEOUT;
        delete process.env.BATON_AGY_GRACE;
        {sets}
        const root = {json.dumps(str(self.root))};
        {body}
        """
        res = repo_fixture.run_node(code)
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout.strip().splitlines()[-1])

    def launch(self, mode="success", allow_edits=False, timeout=30, **kwargs):
        timeout_part = "" if timeout is None else f"timeoutSeconds: {timeout},"
        body = f"""
        const result = await launchAgy({{ job: 'unit', prompt: {json.dumps(PROMPT)}, allowEdits: {json.dumps(allow_edits)}, {timeout_part} root }});
        console.log(JSON.stringify(result));
        """
        return self.snippet(body, mode=mode, **kwargs)

    def recorded_args(self):
        return [json.loads(line) for line in self.args_file.read_text(encoding="utf-8").splitlines()]

    def test_read_only_command_line(self):
        result = self.launch()
        self.assertTrue(result["ok"])
        self.assertEqual(self.recorded_args(), [DEFAULT_ARGS])

    def test_allow_edits_adds_accept_edits_mode(self):
        self.launch(allow_edits=True)
        self.assertEqual(self.recorded_args(), [DEFAULT_ARGS + ["--mode", "accept-edits"]])

    def test_model_override(self):
        self.launch(env={"BATON_AGY_MODEL": "gemini-test-model"})
        args = self.recorded_args()[0]
        self.assertEqual(args[args.index("--model") + 1], "gemini-test-model")

    def test_model_for_each_job(self):
        jobs = ["scout", "diagnose", "write_tests", "review", "unknown"]
        cases = [
            ({}, ["gemini-4-argon-low"] + ["gemini-4-argon-medium"] * 4),
            ({"BATON_AGY_MODEL_FAST": "fast-x"}, ["fast-x"] + ["gemini-4-argon-medium"] * 4),
            ({"BATON_AGY_MODEL_DEEP": "deep-x"}, ["gemini-4-argon-low"] + ["deep-x"] * 4),
            ({"BATON_AGY_MODEL": "all-x", "BATON_AGY_MODEL_FAST": "fast-x", "BATON_AGY_MODEL_DEEP": "deep-x"}, ["all-x"] * 5),
        ]
        for env, expected in cases:
            with self.subTest(env=env):
                body = f"""
                import {{ modelForJob }} from './scripts/agy.mjs';
                console.log(JSON.stringify({json.dumps(jobs)}.map(modelForJob)));
                """
                self.assertEqual(self.snippet(body, env=env), expected)

    def test_the_entry_records_the_model(self):
        self.assertEqual(self.launch()["entry"]["model"], "gemini-4-argon-medium")

    def test_timeout_defaults_and_env_override(self):
        self.launch(timeout=None)
        self.launch(timeout=None, env={"BATON_AGY_TIMEOUT": "45"})
        first, second = self.recorded_args()
        self.assertEqual(first[first.index("--print-timeout") + 1], "600s")
        self.assertEqual(second[second.index("--print-timeout") + 1], "45s")

    def test_timeout_for_job(self):
        body = """
        const read = () => ['review', 'scout', 'mystery'].map(job => timeoutForJob(job));
        const plain = read();
        process.env.BATON_AGY_TIMEOUT = '45';
        console.log(JSON.stringify({ plain, overridden: read() }));
        """
        data = self.snippet(body)
        self.assertEqual(data["plain"], [1200, 600, 600])
        self.assertEqual(data["overridden"], [45, 45, 45])

    def test_a_review_launch_passes_1200_seconds(self):
        body = """
        launchAgy({ job: 'review', prompt: 'p', root });
        console.log('{}');
        """
        self.snippet(body)
        args = self.recorded_args()[0]
        self.assertEqual(args[args.index("--print-timeout") + 1], "1200s")

    def test_a_non_success_status_is_named_in_the_detail(self):
        result = self.launch(mode="status_timeout")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "failed")
        self.assertTrue(result["detail"].startswith("status TIMEOUT"), result["detail"])
        self.assertEqual(result["entry"]["total_tokens"], 77)

    def test_success_parses_the_json_after_a_warning_line(self):
        result = self.launch()
        self.assertTrue(result["ok"])
        self.assertIsNone(result["reason"])
        self.assertEqual(result["response"], "ok")
        self.assertEqual(result["usage"]["total_tokens"], 1234)
        self.assertEqual(result["deniedActions"], [])

    def test_entry_on_success(self):
        entry = self.launch()["entry"]
        self.assertEqual(entry["job"], "unit")
        self.assertTrue(entry["ok"])
        self.assertIsNone(entry["reason"])
        self.assertEqual(entry["total_tokens"], 1234)
        self.assertEqual(entry["seconds"], 1.5)  # duration_seconds from the JSON wins over wall time
        self.assertRegex(entry["at"], r"^\d{4}-\d{2}-\d{2}T")

    def test_denied_reports_the_denied_actions(self):
        result = self.launch(mode="denied")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "denied")
        self.assertEqual(result["deniedActions"][0]["display_name"], "RunCommand")
        self.assertEqual(result["entry"]["reason"], "denied")

    def test_garbage_output_fails_with_the_first_three_lines(self):
        result = self.launch(mode="garbage")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "failed")
        self.assertEqual(result["detail"], "this is not json\nsecond line\nthird line")
        self.assertEqual(result["entry"]["total_tokens"], 0)  # no usage reported, so nothing to count

    def test_nonzero_exit_fails_with_the_error_line(self):
        result = self.launch(mode="fail_exit")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "failed")
        self.assertIn("invalid model selection", result["detail"])

    def test_missing_command_is_not_installed(self):
        result = self.launch(cmd="definitely-not-a-real-agy-binary")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "not_installed")
        self.assertEqual(result["entry"]["reason"], "not_installed")

    def test_slow_command_times_out(self):
        result = self.launch(mode="sleep", timeout=1, env={"STUB_SLEEP": "120", "BATON_AGY_GRACE": "1"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "timeout")

    def test_process_timeout_adds_the_kill_grace(self):
        body = """
        const unset = processTimeoutMs(30);
        process.env.BATON_AGY_GRACE = '1';
        const short = processTimeoutMs(30);
        process.env.BATON_AGY_GRACE = '0';
        const none = processTimeoutMs(30);
        process.env.BATON_AGY_GRACE = 'soon';
        const invalid = processTimeoutMs(30);
        console.log(JSON.stringify({ unset, short, none, invalid }));
        """
        self.assertEqual(self.snippet(body), {"unset": 45000, "short": 31000, "none": 30000, "invalid": 45000})

    def test_append_delegation_keeps_the_last_20(self):
        body = """
        const state = { delegations: [{ job: 'old' }] };
        for (let i = 0; i < 25; i++) appendDelegation(state, { job: 'j' + i });
        console.log(JSON.stringify(state.delegations.map(d => d.job)));
        """
        jobs = self.snippet(body)
        self.assertEqual(jobs, [f"j{i}" for i in range(5, 25)])

    def test_append_delegation_creates_the_list(self):
        body = """
        const state = {};
        appendDelegation(state, { job: 'first' });
        console.log(JSON.stringify(state.delegations));
        """
        self.assertEqual(self.snippet(body), [{"job": "first"}])

    def scoped(self, mode, allow_edits):
        body = f"""
        const before = snapshotChanges(root);
        await launchAgy({{ job: 'unit', prompt: 'p', allowEdits: {json.dumps(allow_edits)}, timeoutSeconds: 30, root }});
        console.log(JSON.stringify(checkScope(before, snapshotChanges(root), {{ allowEdits: {json.dumps(allow_edits)} }})));
        """
        return self.snippet(body, mode=mode)

    def test_scope_guard_allows_a_new_test_file_when_edits_are_allowed(self):
        self.assertEqual(self.scoped("write_test", True), {"testsWritten": ["tests/generated.test.js"], "outOfScope": []})

    def test_scope_guard_flags_a_new_source_file(self):
        self.assertEqual(self.scoped("write_source", True), {"testsWritten": [], "outOfScope": ["src/rogue.js"]})

    def test_scope_guard_flags_a_changed_source_file(self):
        self.assertEqual(self.scoped("modify_source", True), {"testsWritten": [], "outOfScope": ["src/app.js"]})

    def test_scope_guard_rejects_a_test_file_from_a_read_only_launch(self):
        self.assertEqual(self.scoped("write_test", False), {"testsWritten": [], "outOfScope": ["tests/generated.test.js"]})

    def baton_status(self, state):
        fixture_tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(fixture_tmp.cleanup)
        root = repo_fixture.git_init(repo_fixture.make_template_repo(fixture_tmp.name, skills=False))
        (root / ".agents" / "sync" / "handoff.json").write_text(json.dumps(state), encoding="utf-8")
        res = subprocess.run(["node", str(BATON), "status", "--root", str(root)], cwd=root, capture_output=True, text=True, env=os.environ.copy())
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout

    def test_sync_status_without_delegations(self):
        self.assertIn("Antigravity:  0 launches, 0 tokens (last 20)", self.baton_status({"status": "idle"}))

    def test_sync_status_sums_the_delegation_tokens(self):
        state = {"status": "idle", "delegations": [{"job": "a", "total_tokens": 1234}, {"job": "b", "total_tokens": 66}]}
        self.assertIn("Antigravity:  2 launches, 1300 tokens (last 20)", self.baton_status(state))


if __name__ == "__main__":
    unittest.main()
