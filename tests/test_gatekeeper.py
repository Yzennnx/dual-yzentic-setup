import json
import os
import re
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from tests import repo_fixture

STUB = Path(__file__).resolve().parent / "stubs" / "agy_stub.mjs"
BATON = repo_fixture.SCRIPTS / "baton.mjs"
GATEKEEPER = repo_fixture.SCRIPTS / "gatekeeper.mjs"
SPEC = "docs/specs/demo-design.md"
PLAIN_PATHS_RULE = (
    "Reply in plain text. Refer to files by repo-relative path with forward slashes. "
    "Do not use Markdown links or absolute paths."
)
PASS = 'node -e "process.exit(0)"'
FAIL = "node -e \"console.error('boom: expected 1 got 2'); process.exit(1)\""
NEEDS_GENERATED = "node -e \"process.exit(process.getBuiltinModule('fs').existsSync('tests/generated.test.js') ? 0 : 1)\""
DIAGNOSIS_HEADING = "--- Gatekeeper Diagnosis ---"
EXCERPT_HEADING = "Distilled Failure Diagnostic"
CHANGES_HEADING = "## Changes Implemented by Claude"
REPORT_HEADING = "## Verification Report by Antigravity"

# A stand-in for agy that records the active_agent it sees in handoff.json while it runs.
PROBE = """
import { readFileSync, appendFileSync } from 'node:fs';
const state = JSON.parse(readFileSync('.agents/sync/handoff.json', 'utf-8'));
appendFileSync(process.env.PROBE_FILE, state.active_agent + '\\n');
console.log(JSON.stringify({ status: 'SUCCESS', response: 'probe diagnosis line', usage: { total_tokens: 1 } }));
"""

# A stand-in for agy that writes a source file and then hangs until the launcher kills it.
ROGUE_THEN_HANG = """
import { mkdirSync, writeFileSync } from 'node:fs';
mkdirSync('src', { recursive: true });
writeFileSync('src/rogue.js', 'module.exports = "rogue";\\n');
setTimeout(() => {}, 60000);
"""


def appender(letter, exit_code=0):
    """A command that appends `letter` to the file named by RUNS_FILE, to prove it ran and in what order."""
    return f"node -e \"require('fs').appendFileSync(process.env.RUNS_FILE, '{letter}'); process.exit({exit_code})\""


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


class TestGatekeeper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.args_file = Path(self.tmp.name) / "args.jsonl"  # outside the fixtures so git never sees it
        self.fixtures = 0

    def write(self, root, rel, text):
        target = Path(root) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")

    def make_fixture(self, test_command=PASS, changes=None, commit=False, e2e=None, verify=None, project=None):
        """An initialized project committed once, then `changes` (path -> text) written without committing."""
        self.fixtures += 1
        fixture = Path(self.tmp.name) / f"fixture{self.fixtures}"
        fixture.mkdir()
        root = repo_fixture.make_template_repo(fixture, skills=False)
        blueprint_path = root / "project-blueprint.json"
        blueprint = json.loads(blueprint_path.read_text(encoding="utf-8"))
        blueprint["status"] = "initialized"
        blueprint["project"] = {"source_spec": SPEC, "verify": {"test": test_command}}
        if e2e is not None:
            blueprint["project"]["verify"]["e2e"] = e2e
        blueprint["project"]["verify"].update(verify or {})
        blueprint["project"].update(project or {})
        blueprint_path.write_text(json.dumps(blueprint, indent=2) + "\n", encoding="utf-8")
        repo_fixture.git_init(root)
        for rel, text in (changes if changes is not None else {"src/app.js": "module.exports = 1;\n"}).items():
            self.write(root, rel, text)
        if commit:
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "change")
        return root

    def baton(self, root, *flags, mode="success", cmd=None, env=None):
        """Run `baton verify` as a subprocess from outside the fixture, with the stub wired in."""
        clean = {k: v for k, v in os.environ.items() if not k.startswith(("BATON_", "STUB_", "PROBE_", "npm_config_"))}
        clean.update({
            "BATON_AGY_CMD": cmd or str(STUB),
            "BATON_AGY_GRACE": "1",
            "STUB_MODE": mode,
            "STUB_ARGS_FILE": str(self.args_file),
            "BATON_DIAGNOSE_MIN_LINES": "0",  # the default threshold would skip the diagnosis of a one-line failure
            **(env or {}),
        })
        argv = ["node", str(BATON), "verify", *flags, "--root", str(root)]
        return subprocess.run(argv, cwd=self.tmp.name, capture_output=True, text=True, env=clean)

    def launches(self):
        if not self.args_file.exists():
            return []
        return [json.loads(line) for line in self.args_file.read_text(encoding="utf-8").splitlines()]

    def launches_reset(self):
        self.args_file.unlink(missing_ok=True)

    def prompt(self, index=0):
        return self.launches()[index][1]

    def state(self, root):
        return json.loads((Path(root) / ".agents" / "sync" / "handoff.json").read_text(encoding="utf-8"))

    def handoff(self, root):
        return (Path(root) / ".agents" / "sync" / "handoff.md").read_text(encoding="utf-8")

    def write_script(self, name, source):
        path = Path(self.tmp.name) / name
        path.write_text(source, encoding="utf-8", newline="\n")
        return path

    # Trigger table (spec section 5.1)

    def test_trigger_table(self):
        cases = [
            # tier, files, disabled, launches
            (1, ["src/app.js"], False, False),  # Tier 1 never launches
            (2, ["src/app.js"], True, False),  # disabled by flag or variable
            (2, ["src/app.js"], False, True),  # source changed, no test changed
            (3, ["src/a.js", "src/b.js", "src/c.js", "src/d.js"], False, True),
            (2, ["src/app.js", "tests/app.test.js"], False, False),  # a test changed too
            (2, ["src/app.js", "tests/test_app.py"], False, False),
            (2, ["tests/app.test.js"], False, False),  # no source file
            (2, ["README.md", "styles/site.css", "docs/notes.txt"], False, False),  # cosmetic only
            (2, [".agents/sync/session.md"], False, False),  # agent state is not source
            (2, ["src/app.js", "README.md"], False, True),  # cosmetic files do not count as tests
            (2, [], False, False),
        ]
        rows = [{"tier": tier, "files": files, "disabled": disabled} for tier, files, disabled, _ in cases]
        code = f"""
        import {{ shouldWriteTests }} from './scripts/gatekeeper.mjs';
        console.log(JSON.stringify({json.dumps(rows)}.map(row => shouldWriteTests(row))));
        """
        res = repo_fixture.run_node(code)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(json.loads(res.stdout), [expected for *_, expected in cases])

    def test_tier_1_launches_nothing(self):
        root = self.make_fixture(changes={"README.md": "# changed\n"})
        res = self.baton(root)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.launches(), [])
        self.assertEqual(self.state(root)["gatekeeper"], {"result": "not_needed", "tests_written": [], "out_of_scope": []})

    def test_no_gatekeeper_flag_launches_nothing(self):
        root = self.make_fixture()
        res = self.baton(root, "--no-gatekeeper")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.launches(), [])
        self.assertIn("Executing test command", res.stdout)
        self.assertEqual(self.state(root)["gatekeeper"]["result"], "not_needed")

    def test_the_disabled_switches_turn_off_both_the_write_and_the_diagnosis_step(self):
        for label, flags, env in (("flag", ("--no-gatekeeper",), None), ("variable", (), {"BATON_GATEKEEPER": "0"})):
            with self.subTest(label):
                root = self.make_fixture(FAIL)  # source changed, no test changed, and the tests fail
                res = self.baton(root, *flags, env=env)
                self.assertEqual(res.returncode, 1, res.stdout)
                self.assertEqual(self.launches(), [])
                self.assertIn(EXCERPT_HEADING, res.stderr)
                self.assertIn("boom: expected 1 got 2", res.stderr)
                self.assertNotIn(DIAGNOSIS_HEADING, res.stderr)
                self.assertFalse((root / ".agents" / "sync" / "last-failure.log").exists())

    def scoped_fixture(self, scoped_command):
        """Source changed and no test changed, in a project that defines a scoped test command."""
        root = self.make_fixture()
        blueprint_path = root / "project-blueprint.json"
        blueprint = json.loads(blueprint_path.read_text(encoding="utf-8"))
        blueprint["project"]["verify"]["test_scoped"] = scoped_command
        blueprint_path.write_text(json.dumps(blueprint, indent=2) + "\n", encoding="utf-8")
        return root

    def test_an_explicit_scope_means_no_write_launch(self):
        # Naming the test file that covers a change says its tests already exist
        root = self.scoped_fixture(PASS + " {scope}")
        res = self.baton(root, "--tier", "2", "--scope", "tests/app.test.js")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.launches(), [])
        self.assertEqual(self.state(root)["gatekeeper"]["result"], "not_needed")

    def test_a_scoped_failure_is_still_diagnosed(self):
        root = self.scoped_fixture(FAIL + " {scope}")
        res = self.baton(root, "--tier", "2", "--scope", "tests/app.test.js")
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertEqual(len(self.launches()), 1)
        self.assertIn(DIAGNOSIS_HEADING, res.stderr)

    def test_a_changed_test_file_means_no_write_launch(self):
        root = self.make_fixture(changes={"src/app.js": "module.exports = 1;\n", "tests/app.test.js": "// test\n"})
        res = self.baton(root)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.launches(), [])
        self.assertEqual(self.state(root)["gatekeeper"]["result"], "not_needed")

    def test_configuration_only_changes_launch_nothing(self):
        root = self.make_fixture(changes={"package.json": '{"name": "demo"}\n', ".gitignore": "node_modules/\n"})
        res = self.baton(root)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Tier 2", res.stdout)
        self.assertEqual(self.launches(), [])
        self.assertIn("Executing test command", res.stdout)
        self.assertEqual(self.state(root)["gatekeeper"], {"result": "not_needed", "tests_written": [], "out_of_scope": []})

    def test_source_without_tests_launches_with_edits_and_a_full_prompt(self):
        root = self.make_fixture()
        res = self.baton(root)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(len(self.launches()), 1)
        args = self.launches()[0]
        self.assertEqual(args[args.index("--mode") + 1], "accept-edits")
        prompt = self.prompt()
        for expected in (
            "Gatekeeper",
            "src/app.js",
            "docs/PLAN.md",
            SPEC,
            PASS,
            "Touch test files only.",
            "Run nothing.",
            "test to the spec",
        ):
            self.assertIn(expected, prompt)
        self.assertTrue(prompt.endswith(PLAIN_PATHS_RULE), prompt)
        self.assertEqual(self.state(root)["gatekeeper"], {"result": "ran", "tests_written": [], "out_of_scope": []})

    RULE_DOC = (
        "---\nowns: []\n---\n# Demo\n\n## What the user sees\nx\n\n## Rules\n"
        "- [demo#1] The demo opens in under a second.\n- [demo#2] (manual) The demo looks calm.\n\n"
        "## How it works\nx\n\n## Limits and out of scope\nx\n"
    )

    def test_the_write_prompt_carries_the_changed_rules_and_a_rule_without_a_test_then_fails(self):
        root = self.make_fixture(changes={"src/app.js": "module.exports = 1;\n", "docs/rules/features/demo.md": self.RULE_DOC})
        res = self.baton(root)
        prompt = self.prompt()
        self.assertIn("- demo#1: The demo opens in under a second.", prompt)
        self.assertIn("never bend a test to fit the code", prompt.lower())
        self.assertNotIn("demo#2", prompt, "manual rules are not handed to the test writer")
        self.assertEqual(res.returncode, 1)
        self.assertIn("rule demo#1 was added or reworded but no test cites it", res.stderr)

    def test_a_prompt_without_changed_rules_has_no_rule_section(self):
        root = self.make_fixture()
        self.baton(root)
        self.assertNotIn("Rules added or reworded", self.prompt())

    def test_tier_3_launches_too(self):
        root = self.make_fixture(changes={f"src/{name}.js": "module.exports = 1;\n" for name in "abcd"})
        res = self.baton(root)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Tier 3", res.stdout)
        self.assertEqual(len(self.launches()), 1)
        for name in "abcd":
            self.assertIn(f"src/{name}.js", self.prompt())

    def test_a_clean_tree_uses_the_last_commit_as_the_change_set(self):
        root = self.make_fixture(commit=True)
        res = self.baton(root, mode="write_test")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Working tree clean", res.stdout)
        self.assertEqual(len(self.launches()), 1)
        self.assertIn("src/app.js", self.prompt())

    # Writing tests

    def test_written_tests_are_recorded_and_the_test_command_runs_afterwards(self):
        root = self.make_fixture(NEEDS_GENERATED)
        res = self.baton(root, mode="write_test")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(self.state(root)["gatekeeper"], {"result": "ran", "tests_written": ["tests/generated.test.js"], "out_of_scope": []})
        self.assertLess(res.stdout.index("Gatekeeper wrote"), res.stdout.index("Executing test command"))
        entry = self.state(root)["delegations"][0]
        self.assertEqual((entry["job"], entry["ok"], entry["total_tokens"]), ("write_tests", True, 1234))
        self.assertIn("- tests/generated.test.js", self.handoff(root))

    def test_a_new_source_file_from_the_gatekeeper_is_out_of_scope(self):
        root = self.make_fixture()
        res = self.baton(root, mode="write_source")
        self.assertEqual(res.returncode, 1)
        self.assertIn("src/rogue.js", res.stderr)
        self.assertNotIn("Executing test command", res.stdout)
        self.assertTrue((root / "src" / "rogue.js").exists())  # nothing is reverted
        self.assertEqual(self.state(root)["status"], "gatekeeper_out_of_scope")
        self.assertIn("gatekeeper_out_of_scope", self.handoff(root))

    def test_a_source_file_changed_again_by_the_gatekeeper_is_out_of_scope(self):
        root = self.make_fixture()
        res = self.baton(root, mode="modify_source")
        self.assertEqual(res.returncode, 1)
        self.assertIn("src/app.js", res.stderr)
        self.assertNotIn("Executing test command", res.stdout)
        self.assertTrue((root / "src" / "app.js").read_text(encoding="utf-8").endswith("// touched by the stub\n"))
        self.assertEqual(self.state(root)["status"], "gatekeeper_out_of_scope")

    def test_a_write_step_violation_is_recorded_and_reaches_the_ticket(self):
        root = self.make_fixture()
        res = self.baton(root, mode="write_source")
        self.assertEqual(res.returncode, 1)
        self.assertEqual(self.state(root)["gatekeeper"]["out_of_scope"], ["src/rogue.js"])
        report = self.handoff(root).split(REPORT_HEADING)[1]
        self.assertIn("Out of scope (not reverted):", report)
        self.assertIn("- src/rogue.js", report)
        self.assertNotIn("Not launched.", report)

    def test_active_agent_is_claude_after_every_outcome(self):
        for mode, env in (("success", None), ("fail_exit", None), ("sleep", {"BATON_AGY_TIMEOUT": "1"})):
            with self.subTest(mode):
                root = self.make_fixture()
                res = self.baton(root, mode=mode, env=env)
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
                self.assertEqual(self.state(root)["active_agent"], "claude")
                self.assertIn("Executing test command", res.stdout)

    def test_a_timed_out_launch_is_skipped_but_the_tests_still_run(self):
        root = self.make_fixture()
        res = self.baton(root, mode="sleep", env={"BATON_AGY_TIMEOUT": "1"})
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("Gatekeeper skipped (timeout): tests for this change are still owed.", res.stdout)
        self.assertEqual(self.state(root)["gatekeeper"], {"result": "skipped", "tests_written": [], "out_of_scope": []})

    def test_the_scope_guard_still_runs_after_a_timed_out_launch(self):
        root = self.make_fixture()
        rogue = self.write_script("rogue_then_hang.mjs", ROGUE_THEN_HANG)
        res = self.baton(root, cmd=str(rogue), env={"BATON_AGY_TIMEOUT": "1"})
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("src/rogue.js", res.stderr)
        self.assertEqual(self.state(root)["status"], "gatekeeper_out_of_scope")
        self.assertEqual(self.state(root)["active_agent"], "claude")

    def test_unavailable_still_runs_the_tests_and_prints_the_owed_warning(self):
        for label, kwargs, reason in (
            ("garbage", {"mode": "garbage"}, "failed: this is not json"),
            ("denied", {"mode": "denied"}, "denied"),
            ("missing", {"cmd": "definitely-not-a-real-agy-binary"}, "not_installed"),
        ):
            with self.subTest(label):
                root = self.make_fixture()
                res = self.baton(root, **kwargs)
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
                self.assertIn(f"[Baton] Gatekeeper skipped ({reason}): tests for this change are still owed.", res.stdout)
                self.assertIn("Executing test command", res.stdout)
                self.assertEqual(self.state(root)["gatekeeper"], {"result": "skipped", "tests_written": [], "out_of_scope": []})
                self.assertIn("still owed", self.handoff(root))

    # End-to-end tests are opt-in

    def runs(self):
        path = Path(self.tmp.name) / "runs.txt"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def e2e_env(self, **extra):
        return {"RUNS_FILE": str(Path(self.tmp.name) / "runs.txt"), **extra}

    def test_the_e2e_command_does_not_run_without_the_flag(self):
        for name, changes in (
            ("tier 2", {"src/app.js": "module.exports = 1;\n", "tests/app.test.js": "// t\n"}),
            ("tier 3", {f"src/{n}.js": "module.exports = 1;\n" for n in "abcd"}),
        ):
            with self.subTest(name):
                root = self.make_fixture(appender("t"), changes=changes, e2e=appender("e"))
                res = self.baton(root, "--no-gatekeeper", env=self.e2e_env())
                self.assertEqual(res.returncode, 0, res.stderr)
                self.assertEqual(self.state(root)["e2e"], "not_run")
                self.assertIn("E2E: not run", self.handoff(root))
        self.assertEqual(self.runs(), "tt")

    def test_with_the_flag_the_test_command_runs_first_and_then_the_e2e_command(self):
        root = self.make_fixture(appender("t"), e2e=appender("e"))
        res = self.baton(root, "--e2e", "--no-gatekeeper", env=self.e2e_env())
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.runs(), "te")
        self.assertIn("Executing e2e command:", res.stdout)
        self.assertEqual(self.state(root)["e2e"], "passed")
        self.assertTrue(self.handoff(root).rstrip().endswith("E2E: passed"))

    def test_the_e2e_flag_on_tier_1_runs_only_the_e2e_command(self):
        root = self.make_fixture(appender("t"), changes={"README.md": "# hi\n"}, e2e=appender("e"))
        res = self.baton(root, "--e2e", env=self.e2e_env())
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.runs(), "e")
        self.assertEqual(self.state(root)["status"], "verified")
        self.assertEqual(self.state(root)["e2e"], "passed")

    def test_a_failing_e2e_command_fails_the_verify(self):
        root = self.make_fixture(appender("t"), e2e=appender("e", 1))
        res = self.baton(root, "--e2e", "--no-gatekeeper", env=self.e2e_env())
        self.assertEqual(res.returncode, 1, res.stdout)
        state = self.state(root)
        self.assertEqual((state["status"], state["turn_count"], state["e2e"]), ("verification_failed", 1, "failed"))
        self.assertTrue(self.handoff(root).rstrip().endswith("E2E: failed"))

    def test_a_failing_test_command_skips_the_e2e_command(self):
        root = self.make_fixture(appender("t", 1), e2e=appender("e"))
        res = self.baton(root, "--e2e", "--no-gatekeeper", env=self.e2e_env())
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertEqual(self.runs(), "t")
        self.assertEqual(self.state(root)["e2e"], "not_run")

    def test_the_e2e_flag_without_a_configured_command_changes_nothing(self):
        root = self.make_fixture(appender("t"))
        self.baton(root, "--no-gatekeeper", env=self.e2e_env())
        before = (root / ".agents" / "sync" / "handoff.json").read_bytes()
        res = self.baton(root, "--e2e", env=self.e2e_env())
        self.assertEqual(res.returncode, 1)
        self.assertIn("[Baton] No e2e command configured (project.verify.e2e).", res.stderr)
        self.assertEqual(self.runs(), "t")
        self.assertEqual((root / ".agents" / "sync" / "handoff.json").read_bytes(), before)

    def test_npm_config_e2e_behaves_as_the_flag(self):
        root = self.make_fixture(appender("t"), e2e=appender("e"))
        res = self.baton(root, "--no-gatekeeper", env=self.e2e_env(npm_config_e2e="true"))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.runs(), "te")

    def test_the_write_prompt_says_whether_e2e_tests_are_wanted(self):
        with_e2e = "Write unit or component tests. Write an end-to-end test only when the change adds or alters a user journey named in the spec, and put it under e2e/."
        without = "Write unit or component tests only. Do not write end-to-end or browser tests."
        for e2e, expected, absent in ((PASS, with_e2e, without), (None, without, with_e2e)):
            with self.subTest(e2e=e2e):
                self.launches_reset()
                root = self.make_fixture(e2e=e2e)
                self.baton(root)
                prompt = self.prompt()
                self.assertIn(expected, prompt)
                self.assertNotIn(absent, prompt)
                self.assertTrue(prompt.endswith(PLAIN_PATHS_RULE), prompt)

    # Diagnosing failures

    def test_a_failing_test_command_prints_the_diagnosis_instead_of_the_excerpt(self):
        root = self.make_fixture(FAIL, changes={"src/app.js": "module.exports = 1;\n", "tests/app.test.js": "// test\n"})
        res = self.baton(root)
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertIn(DIAGNOSIS_HEADING, res.stderr)
        self.assertNotIn(EXCERPT_HEADING, res.stderr)
        self.assertNotIn("boom: expected", res.stderr)

        log = (root / ".agents" / "sync" / "last-failure.log").read_text(encoding="utf-8")
        self.assertIn("boom: expected 1 got 2", log)

        self.assertEqual(len(self.launches()), 1)  # a test changed, so only the diagnosis launched
        self.assertNotIn("--mode", self.launches()[0])
        prompt = self.prompt()
        self.assertIn(".agents/sync/last-failure.log", prompt)
        self.assertIn("at most 15 lines", prompt)
        self.assertNotIn("test-results", prompt)
        self.assertNotIn("playwright-report", prompt)
        self.assertTrue(prompt.endswith(PLAIN_PATHS_RULE), prompt)

        state = self.state(root)
        self.assertEqual((state["status"], state["turn_count"]), ("verification_failed", 1))
        self.assertEqual(state["delegations"][0]["job"], "diagnose")

    # A failure is diagnosed only when it is not readable as it is

    def lines_failing(self, count):
        return f"node -e \"console.error(Array.from({{length: {count}}}, (_, i) => 'line ' + i).join('\\n')); process.exit(1)\""

    def failing_fixture(self, command, **kwargs):
        return self.make_fixture(command, changes={"src/app.js": "module.exports = 1;\n", "tests/app.test.js": "// test\n"}, **kwargs)

    def test_a_one_line_failure_is_not_diagnosed_by_default(self):
        root = self.failing_fixture(FAIL)
        res = self.baton(root, env={"BATON_DIAGNOSE_MIN_LINES": ""})
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertEqual(self.launches(), [])
        self.assertIn(EXCERPT_HEADING, res.stderr)
        self.assertIn("boom: expected 1 got 2", res.stderr)
        self.assertNotIn(DIAGNOSIS_HEADING, res.stderr)
        self.assertFalse((root / ".agents" / "sync" / "last-failure.log").exists())

    def test_the_threshold_is_150_non_empty_lines(self):
        for count, launched in ((150, 0), (151, 1)):
            with self.subTest(lines=count):
                self.launches_reset()
                root = self.failing_fixture(self.lines_failing(count))
                self.baton(root, env={"BATON_DIAGNOSE_MIN_LINES": ""})
                self.assertEqual(len(self.launches()), launched)

    def test_an_artifact_folder_made_by_the_failing_run_makes_a_short_failure_worth_diagnosing(self):
        command = "node -e \"require('fs').mkdirSync('playwright-report',{recursive:true});require('fs').writeFileSync('playwright-report/index.html','x');console.error('boom');process.exit(1)\""
        root = self.failing_fixture(command)
        self.baton(root, env={"BATON_DIAGNOSE_MIN_LINES": ""})
        self.assertEqual(len(self.launches()), 1)

    def test_a_stale_artifact_folder_does_not_make_a_short_failure_worth_diagnosing(self):
        root = self.failing_fixture(FAIL)
        report = root / "playwright-report"
        report.mkdir()
        (report / "index.html").write_text("old", encoding="utf-8")
        old = time.time() - 3600
        for path in (report / "index.html", report):
            os.utime(path, (old, old))
        res = self.baton(root, env={"BATON_DIAGNOSE_MIN_LINES": ""})
        self.assertEqual(self.launches(), [])
        self.assertIn(EXCERPT_HEADING, res.stderr)

    def test_should_diagnose_treats_missing_output_as_empty(self):
        code = """
        import { shouldDiagnose } from './scripts/gatekeeper.mjs';
        const root = process.cwd() + '/no-such-dir';
        const env = { BATON_DIAGNOSE_MIN_LINES: '' };
        console.log(JSON.stringify([shouldDiagnose({ root, output: undefined, env }), shouldDiagnose({ root, output: null, env }), shouldDiagnose({ root, output: 5, env })]));
        """
        res = repo_fixture.run_node(code)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(json.loads(res.stdout.strip()), [False, False, False])

    def test_a_failing_e2e_command_is_always_diagnosed(self):
        root = self.failing_fixture(PASS, e2e=FAIL)
        self.baton(root, "--e2e", env={"BATON_DIAGNOSE_MIN_LINES": ""})
        self.assertEqual(len(self.launches()), 1)
        self.assertEqual(self.state(root)["delegations"][0]["job"], "diagnose")

    def test_a_zero_threshold_diagnoses_a_one_line_failure(self):
        root = self.failing_fixture(FAIL)
        self.baton(root, env={"BATON_DIAGNOSE_MIN_LINES": "0"})
        self.assertEqual(len(self.launches()), 1)

    def test_the_diagnosis_uses_the_fast_model_and_test_writing_the_deep_one(self):
        root = self.make_fixture(FAIL)  # no tests changed and the tests fail: a write launch, then a diagnosis launch
        self.baton(root)
        write, diagnose = self.launches()
        self.assertEqual(write[write.index("--model") + 1], "gemini-4-argon-medium")
        self.assertEqual(diagnose[diagnose.index("--model") + 1], "gemini-4-argon-medium")
        models = [entry["model"] for entry in self.state(root)["delegations"]]
        self.assertEqual(models, ["gemini-4-argon-medium", "gemini-4-argon-medium"])

    def test_the_diagnosis_prompt_names_the_artifact_folders_that_exist(self):
        root = self.make_fixture(FAIL, changes={"src/app.js": "module.exports = 1;\n", "tests/app.test.js": "// test\n"})
        (root / "test-results").mkdir()
        (root / "playwright-report").mkdir()
        self.baton(root)
        self.assertIn("test-results/", self.prompt())
        self.assertIn("playwright-report/", self.prompt())

    def test_an_unusable_diagnosis_falls_back_to_the_excerpt(self):
        root = self.make_fixture(FAIL, changes={"src/app.js": "module.exports = 1;\n", "tests/app.test.js": "// test\n"})
        res = self.baton(root, mode="garbage")
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertIn(EXCERPT_HEADING, res.stderr)
        self.assertIn("boom: expected 1 got 2", res.stderr)
        self.assertNotIn(DIAGNOSIS_HEADING, res.stderr)
        self.assertEqual(self.state(root)["active_agent"], "claude")

    def test_a_diagnosis_step_violation_is_recorded_and_the_run_stays_verification_failed(self):
        root = self.make_fixture(FAIL, changes={"src/app.js": "module.exports = 1;\n", "tests/app.test.js": "// test\n"})
        res = self.baton(root, mode="write_source")  # a test changed, so only the diagnosis launches
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertEqual(len(self.launches()), 1)
        self.assertIn("[Baton] The Gatekeeper changed files during a read-only diagnosis:", res.stderr)
        self.assertIn("src/rogue.js", res.stderr)
        self.assertTrue((root / "src" / "rogue.js").exists())  # nothing is reverted
        state = self.state(root)
        self.assertEqual((state["status"], state["turn_count"]), ("verification_failed", 1))
        self.assertEqual(state["gatekeeper"]["out_of_scope"], ["src/rogue.js"])
        report = self.handoff(root).split(REPORT_HEADING)[1]
        self.assertIn("Out of scope (not reverted):", report)
        self.assertIn("- src/rogue.js", report)
        self.assertNotIn("Not launched.", report)

    def test_state_says_antigravity_during_both_launches_and_the_note_reaches_the_ticket(self):
        root = self.make_fixture(FAIL)  # no tests changed and the tests fail: a write launch, then a diagnosis launch
        probe = self.write_script("probe.mjs", PROBE)
        seen = Path(self.tmp.name) / "seen.txt"
        res = self.baton(root, cmd=str(probe), env={"PROBE_FILE": str(seen)})
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertEqual(seen.read_text(encoding="utf-8").split(), ["antigravity", "antigravity"])
        self.assertEqual(self.state(root)["active_agent"], "claude")
        self.assertIn("probe diagnosis line", res.stderr)
        report = self.handoff(root).split(REPORT_HEADING)[1]
        self.assertIn("probe diagnosis line", report)

    # Handoff ticket

    def test_handoff_md_is_rewritten_after_every_verify(self):
        passing_with_tests = {"src/app.js": "module.exports = 1;\n", "tests/app.test.js": "// test\n"}
        for label, kwargs in (
            ("tier 1", {"changes": {"README.md": "# changed\n"}}),
            ("pass, gatekeeper launched", {}),
            ("pass, not launched", {"changes": passing_with_tests}),
            ("fail", {"test_command": FAIL, "changes": passing_with_tests}),
        ):
            with self.subTest(label):
                root = self.make_fixture(**kwargs)
                (root / ".agents" / "sync" / "handoff.md").write_text("stale\n", encoding="utf-8")
                self.baton(root)
                text = self.handoff(root)
                self.assertTrue(text.startswith("# Agent Handoff Ticket:"), text)
                self.assertNotIn("stale", text)
                self.assertIn(CHANGES_HEADING, text)
                self.assertIn(REPORT_HEADING, text)
                self.assertIn(f"- Status: {self.state(root)['status']}", text)
                self.assertRegex(text, r"- Tier: [123]")

    def test_the_ticket_lists_changes_and_says_not_launched_when_nothing_ran(self):
        root = self.make_fixture(changes={"src/app.js": "module.exports = 1;\n", "tests/app.test.js": "// test\n"})
        self.baton(root)
        text = self.handoff(root)
        self.assertIn("- src/app.js", text.split(CHANGES_HEADING)[1].split(REPORT_HEADING)[0])
        self.assertIn("Not launched.", text.split(REPORT_HEADING)[1])

    def test_the_ticket_holds_the_diagnosis(self):
        root = self.make_fixture(FAIL, changes={"src/app.js": "module.exports = 1;\n", "tests/app.test.js": "// test\n"})
        self.baton(root)
        text = self.handoff(root)
        self.assertIn("- Status: verification_failed", text)
        report = text.split(REPORT_HEADING)[1]
        self.assertIn("Diagnosis:", report)
        self.assertNotIn("Not launched.", report)

    # Structure

    def test_the_ticket_says_launched_when_a_launch_wrote_no_tests(self):
        root = self.make_fixture()  # source changed, no test changed; the stub replies but writes nothing
        res = self.baton(root, mode="success")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.state(root)["gatekeeper"]["result"], "ran")
        report = self.handoff(root).split(REPORT_HEADING)[1]
        self.assertIn("Launched; wrote no tests.", report)
        self.assertNotIn("Not launched.", report)

    def test_the_ticket_says_unavailable_when_the_launch_was_skipped(self):
        root = self.make_fixture()
        res = self.baton(root, mode="garbage")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.state(root)["gatekeeper"]["result"], "skipped")
        report = self.handoff(root).split(REPORT_HEADING)[1]
        self.assertIn("Launch attempted; Antigravity was unavailable.", report)
        self.assertNotIn("Not launched.", report)

    def test_the_gatekeeper_does_not_import_the_baton(self):
        text = GATEKEEPER.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"from\s+['\"][^'\"]*baton", text))


if __name__ == "__main__":
    unittest.main()
