import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestNodeScripts(unittest.TestCase):
    def test_solo_blocks_headless_build_and_qa(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agents").mkdir()
            (root / ".agents" / "workflow.local.json").write_text('{"mode":"claude-solo"}', encoding="utf-8")
            calls = root / "calls.jsonl"
            env = {
                **os.environ, "BATON_AGY_CMD": str(REPO_ROOT / "tests" / "stubs" / "agy_stub.mjs"),
                "STUB_MODE": "success", "STUB_ARGS_FILE": str(calls),
            }
            for flag, value, job in (("--design", "plan.md", "build"), ("--qa", "checkout", "qa")):
                with self.subTest(job=job):
                    result = subprocess.run(
                        ["node", str(REPO_ROOT / "scripts" / "agy-build.mjs"), "--root", tmp, flag, value],
                        capture_output=True, text=True, env=env,
                    )
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn(f"disables headless {job}", result.stderr)
                    self.assertFalse(calls.exists())

    def test_script_tests_pass(self):
        files = sorted(str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / "scripts").glob("*.test.mjs"))
        self.assertTrue(files, "no scripts/*.test.mjs found")
        res = subprocess.run(["node", "--test", *files], cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(res.returncode, 0, (res.stdout + res.stderr)[-3000:])


if __name__ == "__main__":
    unittest.main()
