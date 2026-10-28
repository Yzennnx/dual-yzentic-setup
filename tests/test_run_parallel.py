import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RUNNER = Path(__file__).resolve().parent / "run_parallel.py"

PASSING = "import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        print('PASSING-MODULE-OUTPUT')\n"
FAILING = "import unittest\n\nclass T(unittest.TestCase):\n    def test_bad(self):\n        self.fail('FAILING-MODULE-OUTPUT')\n"


class TestRunParallel(unittest.TestCase):
    def make_tests_dir(self, modules):
        """A temp parent holding a `tests` package; the runner never sees the real tests directory."""
        tmp = tempfile.TemporaryDirectory(prefix="run parallel ")
        self.addCleanup(tmp.cleanup)
        tests_dir = Path(tmp.name) / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text("", encoding="utf-8")
        for name, body in modules.items():
            (tests_dir / name).write_text(body, encoding="utf-8")
        return tests_dir

    def run_runner(self, tests_dir, *patterns):
        # Run from an unrelated directory: the runner must not depend on the current directory.
        return subprocess.run([sys.executable, str(RUNNER), str(tests_dir), *patterns], cwd=tests_dir.parent.parent,
                              capture_output=True, text=True)

    def test_module_patterns_narrow_the_run(self):
        tests_dir = self.make_tests_dir({"test_a1.py": PASSING, "test_a2.py": PASSING, "test_b.py": FAILING})
        res = self.run_runner(tests_dir, "test_a*.py")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertRegex(res.stdout.strip().splitlines()[-1], r"^Ran 2 test modules")

    def test_a_failing_module_fails_the_run_and_shows_only_its_own_output(self):
        res = self.run_runner(self.make_tests_dir({"test_good.py": PASSING, "test_bad.py": FAILING}))
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("FAILING-MODULE-OUTPUT", res.stdout)
        self.assertNotIn("PASSING-MODULE-OUTPUT", res.stdout)
        last = res.stdout.strip().splitlines()[-1]
        self.assertRegex(last, r"^Ran 2 test modules in [\d.]+s: 1 passed, 1 failed$")

    def test_all_passing_modules_exit_zero(self):
        res = self.run_runner(self.make_tests_dir({"test_a.py": PASSING, "test_b.py": PASSING}))
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        last = res.stdout.strip().splitlines()[-1]
        self.assertRegex(last, r"^Ran 2 test modules in [\d.]+s: 2 passed, 0 failed$")

    def test_a_directory_without_modules_exits_one(self):
        tests_dir = self.make_tests_dir({})
        res = self.run_runner(tests_dir)
        self.assertEqual(res.returncode, 1)
        self.assertIn(f"No test modules found in {tests_dir}", res.stderr)

    def test_a_missing_directory_exits_one(self):
        tests_dir = self.make_tests_dir({}) / "nope"
        res = self.run_runner(tests_dir)
        self.assertEqual(res.returncode, 1)
        self.assertIn(f"No test modules found in {tests_dir}", res.stderr)

    def test_npm_config_variables_are_stripped_case_insensitively(self):
        body = (
            "import os, unittest\n\nclass T(unittest.TestCase):\n    def test_unset(self):\n"
            "        self.assertIsNone(os.environ.get('NPM_CONFIG_TIER'))\n"
            "        self.assertIsNone(os.environ.get('npm_config_tier'))\n"
        )
        tests_dir = self.make_tests_dir({"test_env.py": body})
        env = {**os.environ, "NPM_CONFIG_TIER": "2", "npm_config_tier": "2"}
        res = subprocess.run([sys.executable, str(RUNNER), str(tests_dir)], cwd=tests_dir.parent.parent, env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()
