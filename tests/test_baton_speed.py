import json
import unittest
from pathlib import Path

from tests.repo_fixture import run_node
from tests import test_gatekeeper as tg
from tests.test_gatekeeper import FAIL, PASS, appender, git

BAD_ROUTE_TEST = """
import { appendFileSync, mkdirSync, writeFileSync } from 'node:fs';
appendFileSync(process.env.STUB_ARGS_FILE, JSON.stringify(process.argv.slice(2)) + '\\n');
mkdirSync('src/app', { recursive: true });
writeFileSync('src/app/bad.test.js', 'test("x", () => {});\\n');
console.log(JSON.stringify({ status: 'SUCCESS', response: 'ok', usage: { total_tokens: 1 } }));
"""

ROUTES = [
    {"paths": ["a/"], "setup": appender("S"), "command": appender("A")},
    {"paths": ["b/"], "setup": appender("S"), "command": appender("B")},
]


class TestBatonSpeed(unittest.TestCase):
    """Tier by surface, debug mode, the Gatekeeper self-check, no-tests folders and test routes."""

    # Borrow the fixture and subprocess helpers of the Gatekeeper tests without inheriting its test cases.
    setUp = tg.TestGatekeeper.setUp
    write = tg.TestGatekeeper.write
    make_fixture = tg.TestGatekeeper.make_fixture
    baton = tg.TestGatekeeper.baton
    launches = tg.TestGatekeeper.launches
    launches_reset = tg.TestGatekeeper.launches_reset
    prompt = tg.TestGatekeeper.prompt
    state = tg.TestGatekeeper.state
    write_script = tg.TestGatekeeper.write_script
    runs = tg.TestGatekeeper.runs
    e2e_env = tg.TestGatekeeper.e2e_env

    def node_json(self, expression):
        res = run_node(f"import * as b from './scripts/baton.mjs'; console.log(JSON.stringify({expression}));")
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout)

    # Tier by risky surface

    def test_risky_paths_decide_the_tier(self):
        risky = json.dumps(["api/", "packages/shared/"])
        cases = [
            (["README.md", "x.css"], 1),
            (["a.ts", "b.ts", "c.ts", "d.ts", "e.ts"], 2),  # no file-count rule
            (["src/config/a.ts"], 2),  # no name heuristic either
            (["a.ts", "packages/shared/domain/x.ts"], 3),
        ]
        for files, tier in cases:
            with self.subTest(files=files):
                self.assertEqual(self.node_json(f"b.detectExecutionTier({json.dumps(files)}, {risky})"), tier)

    def test_unset_or_empty_risky_paths_keep_the_heuristic(self):
        many = json.dumps(["a.ts", "b.ts", "c.ts", "d.ts"])
        self.assertEqual(self.node_json(f"b.detectExecutionTier({many})"), 3)
        self.assertEqual(self.node_json(f"b.detectExecutionTier({many}, [])"), 3)

    def test_verify_uses_risky_paths_and_tier_flag(self):
        changes = {f"src/f{i}.js": "1;\n" for i in range(5)}
        root = self.make_fixture(changes=changes, project={"risky_paths": ["api/"]})
        res = self.baton(root, "--no-gatekeeper")
        self.assertIn("Tier 2 - auto-detected", res.stdout)
        res = self.baton(root, "--no-gatekeeper", "--tier", "3")
        self.assertIn("Tier 3 - set by --tier", res.stdout)
        res = self.baton(root, "--tier", "4")
        self.assertEqual(res.returncode, 1)
        self.assertIn("--tier must be 1, 2 or 3", res.stderr)
        root = self.make_fixture(changes={"api/routes.js": "1;\n"}, project={"risky_paths": ["api/"]})
        self.assertIn("Tier 3 - auto-detected", self.baton(root, "--no-gatekeeper").stdout)

    # Debug mode

    def test_debug_never_launches_and_records_the_owed_files(self):
        for flags, env in (((("--debug",)), {}), ((), {"BATON_DEBUG": "1"})):
            with self.subTest(flags=flags, env=env):
                self.launches_reset()
                root = self.make_fixture(test_command=appender("T"))
                runs = Path(self.tmp.name) / f"runs{self.fixtures}.txt"
                res = self.baton(root, *flags, env={**env, "RUNS_FILE": str(runs)})
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
                self.assertEqual(self.launches(), [])
                self.assertIn("[Baton] Debug mode: tests not written; owed for: src/app.js", res.stdout)
                self.assertEqual(self.state(root)["tests_owed"], ["src/app.js"])
                self.assertEqual(runs.read_text(encoding="utf-8"), "T")

    def test_owed_files_join_the_next_write_and_are_then_cleared(self):
        root = self.make_fixture()
        self.baton(root, "--debug")
        self.baton(root, "--debug")  # deduped
        self.assertEqual(self.state(root)["tests_owed"], ["src/app.js"])
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "debug work")
        self.write(root, "src/other.js", "module.exports = 2;\n")
        res = self.baton(root, mode="write_test")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        prompt = self.prompt()
        self.assertIn("- src/app.js", prompt)
        self.assertIn("- src/other.js", prompt)
        self.assertEqual(self.state(root)["tests_owed"], [])

    def test_owed_files_stay_when_no_tests_were_written(self):
        root = self.make_fixture()
        self.baton(root, "--debug")
        self.write(root, "src/other.js", "module.exports = 2;\n")
        self.baton(root, mode="success")  # the stub writes nothing
        self.assertEqual(self.state(root)["tests_owed"], ["src/app.js"])

    # Gatekeeper self-check

    def test_new_tests_get_one_repair_round_when_they_fail(self):
        root = self.make_fixture(verify={"test_scoped": FAIL + " {scope}"})
        res = self.baton(root, mode="write_test")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(len(self.launches()), 2)  # write, then exactly one repair
        repair = self.prompt(1)
        self.assertIn("- tests/generated.test.js", repair)
        self.assertIn("boom: expected 1 got 2", repair)
        self.assertIn("exposes a real bug in the source", repair)
        self.assertIn("asking the Gatekeeper to repair them (once)", res.stdout)

    def test_passing_new_tests_need_no_repair(self):
        root = self.make_fixture(verify={"test_scoped": PASS + " {scope}"})
        res = self.baton(root, mode="write_test")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(len(self.launches()), 1)
        self.assertIn("Checking the new tests", res.stdout)

    def test_self_check_command_shapes(self):
        files = '["a.test.ts", "b.test.ts"]'
        cases = [
            ({"test": "npx vitest run"}, "npx vitest run a.test.ts b.test.ts"),
            ({"test": "npm test"}, "npm test -- a.test.ts b.test.ts"),
            ({"test": "make check"}, "make check"),
            ({"test": "npx vitest run", "test_scoped": "vt {scope}"}, "vt a.test.ts b.test.ts"),
        ]
        for verify, expected in cases:
            with self.subTest(verify=verify):
                self.assertEqual(self.node_json(f"b.selfCheckCommand({files}, {json.dumps(verify)}, 'x')"), expected)

    # No-tests folders

    def test_a_test_in_a_no_tests_folder_fails_verification(self):
        root = self.make_fixture(changes={"src/app/routes.test.js": "1;\n"}, verify={"no_tests_in": ["src/app"]})
        res = self.baton(root, "--no-gatekeeper")
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertIn("src/app/routes.test.js", res.stderr)
        self.assertIn("no_tests_in", res.stderr)

    def test_a_gatekeeper_test_in_a_no_tests_folder_fails_and_the_prompt_forbids_it(self):
        root = self.make_fixture(changes={"src/app/index.js": "1;\n"}, verify={"no_tests_in": ["src/app"]})
        bad = self.write_script("bad_route_test.mjs", BAD_ROUTE_TEST)
        res = self.baton(root, cmd=str(bad))
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("src/app/bad.test.js", res.stderr)
        self.assertIn("Never create files under: src/app.", self.prompt())

    def test_no_prompt_line_without_no_tests_in(self):
        root = self.make_fixture()
        self.baton(root)
        self.assertNotIn("Never create files under", self.prompt())

    # Test routes

    def routed(self, changes, routes=None):
        root = self.make_fixture(test_command=appender("T"), changes=changes, verify={"routes": routes or ROUTES})
        (Path(self.tmp.name) / "runs.txt").unlink(missing_ok=True)
        res = self.baton(root, "--no-gatekeeper", env=self.e2e_env())
        return res, self.runs()

    def test_routes_run_matching_commands_with_one_setup(self):
        res, runs = self.routed({"a/x.js": "1;\n"})
        self.assertEqual((res.returncode, runs), (0, "SA"), res.stdout + res.stderr)
        res, runs = self.routed({"a/x.js": "1;\n", "b/y.js": "1;\n"})
        self.assertEqual(runs, "SAB")  # the shared setup ran once

    def test_routes_add_the_full_command_for_an_uncovered_file(self):
        res, runs = self.routed({"a/x.js": "1;\n", "c/z.js": "1;\n"})
        self.assertEqual(runs, "SAT")

    def test_routes_fall_back_to_the_full_command_when_none_match(self):
        res, runs = self.routed({"c/z.js": "1;\n"})
        self.assertEqual(runs, "T")

    def test_a_failing_route_reports_which_command_failed(self):
        routes = [{"paths": ["a/"], "command": appender("A", 1)}, {"paths": ["b/"], "command": appender("B")}]
        res, runs = self.routed({"a/x.js": "1;\n", "b/y.js": "1;\n"}, routes)
        self.assertEqual(res.returncode, 1)
        self.assertEqual(runs, "A")  # stops at the first failure
        self.assertIn("Failed command: " + appender("A", 1), res.stderr)

    def test_without_routes_the_full_command_runs(self):
        root = self.make_fixture(test_command=appender("T"))
        (Path(self.tmp.name) / "runs.txt").unlink(missing_ok=True)
        self.baton(root, "--no-gatekeeper", env=self.e2e_env())
        self.assertEqual(self.runs(), "T")


if __name__ == "__main__":
    unittest.main()
