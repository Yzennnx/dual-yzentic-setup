import json
import subprocess
import tempfile
import unittest

from tests import repo_fixture

BATON = repo_fixture.SCRIPTS / "baton.mjs"

REQUIRED_KEYS = [
    "version",
    "task_id",
    "active_agent",
    "status",
    "turn_count",
    "max_turns",
    "last_updated",
    "summary",
    "files_modified",
]
ALLOWED_STATUSES = ["idle", "ready_for_verification", "verification_failed", "verified", "gatekeeper_out_of_scope"]


class TestSyncSchema(unittest.TestCase):
    """Sync state is untracked, so check what the baton generates in a fixture, not files in the real repo."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.fixture = repo_fixture.git_init(repo_fixture.make_template_repo(self.tmp.name, skills=False))
        self.json_path = self.fixture / ".agents" / "sync" / "handoff.json"
        self.json_path.unlink()  # start from nothing so the baton has to generate the whole file

    def baton(self, *args):
        cmd = ["node", str(BATON), *args, "--root", str(self.fixture)]
        res = subprocess.run(cmd, cwd=self.fixture, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)

    def read_state(self):
        return json.loads(self.json_path.read_text(encoding="utf-8"))

    def check_schema(self, data):
        for key in REQUIRED_KEYS:
            self.assertIn(key, data, f"Missing key '{key}' in handoff.json")
        self.assertIn(data["status"], ALLOWED_STATUSES)
        self.assertIn(data["active_agent"], ["claude", "antigravity"])
        self.assertIsInstance(data["turn_count"], int)
        self.assertIsInstance(data["max_turns"], int)
        self.assertIsInstance(data["files_modified"], list)
        self.assertIsInstance(data["tests_owed"], list)

    def test_status_generates_valid_handoff_json(self):
        self.baton("status")
        self.assertTrue(self.json_path.exists(), "status must recreate a missing handoff.json")
        data = self.read_state()
        self.check_schema(data)
        self.assertEqual(data["status"], "idle")

    def test_verify_keeps_handoff_json_valid(self):
        self.baton("status")
        self.baton("verify", "--tier", "1")
        data = self.read_state()
        self.check_schema(data)
        self.assertEqual(data["status"], "verified")

    def test_sync_state_stays_out_of_git(self):
        self.baton("verify", "--tier", "1")
        tracked = subprocess.run(
            ["git", "ls-files", ".agents/sync"], cwd=self.fixture, capture_output=True, text=True
        ).stdout
        self.assertNotIn("handoff.json", tracked)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.fixture, capture_output=True, text=True).stdout
        self.assertEqual(status.strip(), "", "baton state must not dirty the tree")


if __name__ == "__main__":
    unittest.main()
