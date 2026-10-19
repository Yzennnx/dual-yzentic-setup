import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PRELUDE = """
import { mkdtempSync, writeFileSync, readFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { acquireLock, lockIsStale } from './scripts/baton.mjs';
const lockPath = join(mkdtempSync(join(tmpdir(), 'verify-lock-test-')), 'lock');
const writeLock = lock => writeFileSync(lockPath, JSON.stringify(lock));
const readHeld = () => JSON.parse(readFileSync(lockPath, 'utf-8'));
const noWait = async () => { throw new Error('waited'); };
"""


class TestVerifyLock(unittest.TestCase):
    def run_node(self, code):
        res = subprocess.run(["node", "--input-type=module", "-e", PRELUDE + code], cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout.strip().splitlines()[-1])

    def test_waits_for_a_live_lock_then_takes_it(self):
        data = self.run_node("""
        writeLock({ pid: process.pid, worktree: 'other-tree', startedAt: new Date().toISOString() });
        const logs = [];
        let polls = 0;
        const sleep = async () => { if (++polls === 3) rmSync(lockPath); };
        const release = await acquireLock('my-tree', { lockPath, sleep, log: m => logs.push(m) });
        const holder = readHeld().worktree;
        release();
        console.log(JSON.stringify({ polls, logs, holder, after: existsSync(lockPath) }));
        """)
        self.assertEqual(data["polls"], 3)
        self.assertEqual(data["logs"], ["[Baton] waiting for verify in other-tree"])
        self.assertEqual(data["holder"], "my-tree")
        self.assertFalse(data["after"], "release must remove the lock")

    def test_takes_over_a_lock_whose_pid_is_gone(self):
        data = self.run_node("""
        writeLock({ pid: 999999, worktree: 'dead', startedAt: new Date().toISOString() });
        const release = await acquireLock('my-tree', { lockPath, isAlive: () => false, sleep: noWait });
        const pid = readHeld().pid;
        release();
        console.log(JSON.stringify({ ours: pid === process.pid }));
        """)
        self.assertTrue(data["ours"])

    def test_takes_over_a_lock_older_than_twenty_minutes(self):
        data = self.run_node("""
        writeLock({ pid: process.pid, worktree: 'old', startedAt: new Date(Date.now() - 21 * 60 * 1000).toISOString() });
        const release = await acquireLock('my-tree', { lockPath, sleep: noWait });
        const holder = readHeld().worktree;
        release();
        console.log(JSON.stringify({ holder }));
        """)
        self.assertEqual(data["holder"], "my-tree")

    def test_missing_or_garbled_lock_is_stale(self):
        data = self.run_node("console.log(JSON.stringify([lockIsStale(null), lockIsStale({ pid: 'x' })]));")
        self.assertEqual(data, [True, True])


if __name__ == "__main__":
    unittest.main()
