import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestNodeScripts(unittest.TestCase):
    def test_script_tests_pass(self):
        files = sorted(str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / "scripts").glob("*.test.mjs"))
        self.assertTrue(files, "no scripts/*.test.mjs found")
        res = subprocess.run(["node", "--test", *files], cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(res.returncode, 0, (res.stdout + res.stderr)[-3000:])


if __name__ == "__main__":
    unittest.main()
