import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARD = REPO_ROOT / "scripts" / "guard-commands.mjs"
SESSION_CONTEXT = REPO_ROOT / "scripts" / "session-context.mjs"
SETTINGS = REPO_ROOT / ".claude" / "settings.json"

BLOCKED = [
    "npm test",
    "npm run test",
    "npm test -- --watch",
    "pnpm test",
    "yarn test",
    "pytest",
    "pytest -x -q",
    "python -m pytest",
    "python3 -m unittest discover tests",
    "python -m unittest",
    "py -m unittest discover",
    "npx playwright test",
    "npx playwright test --project chromium",
    "npx vitest run",
    "npx jest",
    "cd app && npm test",
    "git status; pytest",
    "CI=1 npm test",
]

ALLOWED = [
    "npm run verify:agent",
    "npm run verify:agent -- --tier 3",
    "npm run verify:agent -- --tier 2 --scope tests/test_roadmap.py",
    "node scripts/baton.mjs verify",
    "npm test -- src/app.test.ts",
    "pytest tests/test_one.py",
    "pytest tests/test_one.py::test_name -x",
    "pytest -k login",
    "python -m unittest tests/test_roadmap.py",
    "python3 -m unittest tests.test_roadmap",
    "npx playwright test e2e/login.spec.ts",
    "npx playwright test -g checkout",
    "npx vitest run src/app.test.ts",
    "npx jest -t renders",
    "npm install",
    "npm run build",
    "git log --grep pytest",
    "echo npm test",
    "ls tests",
]


def run_guard(payload):
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(["node", str(GUARD)], input=stdin, capture_output=True, text=True)


class TestGuardCommands(unittest.TestCase):
    def classify(self, commands):
        code = f"""
        import {{ findBlockedCommand }} from './scripts/guard-commands.mjs';
        const out = {{}};
        for (const c of {json.dumps(commands)}) out[c] = findBlockedCommand(c);
        console.log(JSON.stringify(out));
        """
        res = subprocess.run(["node", "--input-type=module", "-e", code], cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout)

    def test_full_suite_commands_are_blocked(self):
        for command, verdict in self.classify(BLOCKED).items():
            with self.subTest(command=command):
                self.assertIsNotNone(verdict, f"should be blocked: {command}")

    def test_scoped_and_unrelated_commands_are_allowed(self):
        for command, verdict in self.classify(ALLOWED).items():
            with self.subTest(command=command):
                self.assertIsNone(verdict, f"should be allowed: {command}")

    def test_hook_denies_a_blocked_shell_command(self):
        for tool in ["Bash", "PowerShell"]:
            with self.subTest(tool=tool):
                res = run_guard({"tool_name": tool, "tool_input": {"command": "npm test"}})
                self.assertEqual(res.returncode, 0, res.stderr)
                output = json.loads(res.stdout)["hookSpecificOutput"]
                self.assertEqual(output["hookEventName"], "PreToolUse")
                self.assertEqual(output["permissionDecision"], "deny")
                self.assertIn("npm run verify:agent", output["permissionDecisionReason"])

    def test_hook_is_silent_for_allowed_commands(self):
        res = run_guard({"tool_name": "Bash", "tool_input": {"command": "npm run verify:agent -- --tier 3"}})
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "")

    def test_hook_ignores_other_tools_and_bad_input(self):
        for payload in [{"tool_name": "Write", "tool_input": {"content": "npm test"}}, "not json", "{}"]:
            with self.subTest(payload=payload):
                res = run_guard(payload)
                self.assertEqual(res.returncode, 0, res.stderr)
                self.assertEqual(res.stdout.strip(), "")


class TestSessionContext(unittest.TestCase):
    def fixture(self, session=None, blueprint=None):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / ".agents" / "sync").mkdir(parents=True)
        if session is not None:
            (root / ".agents" / "sync" / "session.md").write_text(session, encoding="utf-8")
        if blueprint is not None:
            (root / "project-blueprint.json").write_text(blueprint, encoding="utf-8")
        return root

    def context(self, root):
        res = subprocess.run(["node", str(SESSION_CONTEXT), "--root", str(root)], input="{}", capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        output = json.loads(res.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "SessionStart")
        return output["additionalContext"]

    def test_injects_the_handoff_and_blueprint_status(self):
        root = self.fixture(session="# Session Handoff\n\n- **Next:** build the widget\n", blueprint=json.dumps({"status": "uninitialized"}))
        text = self.context(root)
        self.assertIn("build the widget", text)
        self.assertIn("uninitialized", text)
        self.assertIn("npm run verify:agent", text)
        self.assertIn("Tier 1", text)

    def test_missing_files_still_produce_valid_output(self):
        text = self.context(self.fixture())
        self.assertIn("No session handoff", text)

    def test_unreadable_blueprint_does_not_break_the_session(self):
        text = self.context(self.fixture(session="hello handoff\n", blueprint="{not json"))
        self.assertIn("hello handoff", text)

    def test_long_handoff_is_truncated(self):
        session = "\n".join(f"line {i}" for i in range(1, 201))
        text = self.context(self.fixture(session=session))
        self.assertIn("line 40", text)
        self.assertNotIn("line 41\n", text + "\n")
        self.assertIn("truncated", text)

    def test_no_orca_repo_id_means_no_ready_to_merge_list(self):
        text = self.context(self.fixture(session="handoff", blueprint=json.dumps({"status": "initialized", "workflow": {"orca_repo_id": ""}})))
        self.assertNotIn("Ready to merge:", text)


class TestReadyToMerge(unittest.TestCase):
    REPO = "repo-1"

    def parse(self, stdout, repo_id=REPO):
        code = f"import {{ parseReadyToMerge }} from './scripts/session-context.mjs'; console.log(JSON.stringify(parseReadyToMerge({json.dumps(stdout)}, {json.dumps(repo_id)})));"
        res = subprocess.run(["node", "--input-type=module", "-e", code], cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout)

    def card(self, **over):
        return {"repoId": self.REPO, "workspaceStatus": "in-review", "branch": "refs/heads/ui/x", "head": "abcdef1234567", "comment": "ready to merge: abcdef1", **over}

    def out(self, *cards):
        return json.dumps({"ok": True, "result": {"worktrees": list(cards)}})

    def test_lists_only_this_repos_in_review_cards(self):
        lines = self.parse(self.out(
            self.card(),
            self.card(branch="refs/heads/other", workspaceStatus="in-progress"),
            self.card(branch="refs/heads/foreign", repoId="someone-else"),
        ))
        self.assertEqual(lines, ["ui/x @ abcdef1: ready to merge: abcdef1"])

    def test_nothing_without_in_review_cards_or_repo_id(self):
        self.assertEqual(self.parse(self.out(self.card(workspaceStatus="completed"))), [])
        self.assertEqual(self.parse(self.out()), [])
        self.assertEqual(self.parse(self.out(self.card()), repo_id=""), [])

    def test_nothing_when_the_cli_is_missing_or_orca_is_stopped(self):
        self.assertEqual(self.parse(""), [])
        self.assertEqual(self.parse("orca: command not found"), [])
        self.assertEqual(self.parse(json.dumps({"ok": False, "error": {"code": "not_running"}})), [])


class TestSettingsFile(unittest.TestCase):
    def commands(self, event, matcher=None):
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        found = []
        for group in settings["hooks"][event]:
            if matcher is None or group.get("matcher") == matcher:
                found += [hook["command"] for hook in group["hooks"] if hook["type"] == "command"]
        return found

    def test_session_start_runs_the_context_script(self):
        self.assertTrue(any("scripts/session-context.mjs" in c for c in self.commands("SessionStart")))

    def test_shell_tools_are_guarded(self):
        self.assertTrue(any("scripts/guard-commands.mjs" in c for c in self.commands("PreToolUse", "Bash|PowerShell")))


if __name__ == "__main__":
    unittest.main()
