import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

class TestBatonRunner(unittest.TestCase):
    def setUp(self):
        self.baton_script = REPO_ROOT / "scripts" / "baton.mjs"

    def run_node_eval(self, code):
        cmd = ["node", "--input-type=module", "-e", code]
        result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        return result

    def test_baton_script_exists(self):
        self.assertTrue(self.baton_script.exists(), f"Missing {self.baton_script}")

    def test_detect_execution_tier(self):
        code = """
        import { detectExecutionTier } from './scripts/baton.mjs';
        console.log(JSON.stringify({
            tier1: detectExecutionTier(['README.md', 'src/styles/app.css']),
            tier2: detectExecutionTier(['src/components/Button.tsx', 'tests/Button.test.ts']),
            tier3: detectExecutionTier(['prisma/schema.prisma', 'src/auth.ts', 'src/server.ts', 'src/db.ts']),
            empty: detectExecutionTier([])
        }));
        """
        res = self.run_node_eval(code)
        self.assertEqual(res.returncode, 0, f"Error: {res.stderr}")
        data = json.loads(res.stdout.strip())
        self.assertEqual(data["tier1"], 1)
        self.assertEqual(data["tier2"], 2)
        self.assertEqual(data["tier3"], 3)
        self.assertEqual(data["empty"], 3, "no files must never skip the tests")

    def test_missing_specs(self):
        code = """
        import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
        import { tmpdir } from 'node:os';
        import { join } from 'node:path';
        import { missingSpecs } from './scripts/baton.mjs';
        const root = mkdtempSync(join(tmpdir(), 'specs-'));
        mkdirSync(join(root, 'docs/specs'), { recursive: true });
        writeFileSync(join(root, 'docs/PLAN.md'), '[a](specs/here.md) [b](specs/gone.md#x)');
        writeFileSync(join(root, 'docs/specs/here.md'), '');
        writeFileSync(join(root, 'project-blueprint.json'), JSON.stringify({ project: { source_spec: 'docs/specs/nope.md' } }));
        console.log(JSON.stringify(missingSpecs(root)));
        """
        res = self.run_node_eval(code)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(json.loads(res.stdout), ["docs/specs/gone.md", "docs/specs/nope.md"])

    def test_circuit_breaker(self):
        code = """
        import { checkCircuitBreaker } from './scripts/baton.mjs';
        console.log(JSON.stringify({
            under: checkCircuitBreaker({ turn_count: 2, max_turns: 5 }),
            at_max: checkCircuitBreaker({ turn_count: 5, max_turns: 5 }),
            over_max: checkCircuitBreaker({ turn_count: 6, max_turns: 5 })
        }));
        """
        res = self.run_node_eval(code)
        self.assertEqual(res.returncode, 0, f"Error: {res.stderr}")
        data = json.loads(res.stdout.strip())
        self.assertTrue(data["under"])
        self.assertFalse(data["at_max"])
        self.assertFalse(data["over_max"])

    def test_distill_diagnostics(self):
        code = """
        import { distillDiagnostics } from './scripts/baton.mjs';
        const longOutput = Array.from({ length: 50 }, (_, i) => `Line ${i + 1}`).join('\\n');
        const distilled = distillDiagnostics(longOutput);
        console.log(JSON.stringify({ lineCount: distilled.split('\\n').length }));
        """
        res = self.run_node_eval(code)
        self.assertEqual(res.returncode, 0, f"Error: {res.stderr}")
        data = json.loads(res.stdout.strip())
        self.assertLessEqual(data["lineCount"], 25)

    def test_distill_keeps_the_pieces_of_a_node_test_failure(self):
        code = """
        import { readFileSync } from 'node:fs';
        import { distillDiagnostics } from './scripts/baton.mjs';
        const raw = readFileSync('tests/fixtures/node_test_failure.txt', 'utf-8');
        console.log(JSON.stringify({ text: distillDiagnostics(raw) }));
        """
        res = self.run_node_eval(code)
        self.assertEqual(res.returncode, 0, f"Error: {res.stderr}")
        text = json.loads(res.stdout.strip())["text"]
        self.assertLessEqual(len(text.splitlines()), 25)
        for piece in ("clamps percent above 100", "expected: 0", "actual: -25", "location:"):
            self.assertIn(piece, text)

    def test_distill_returns_a_short_output_whole(self):
        code = """
        import { distillDiagnostics } from './scripts/baton.mjs';
        const out = Array.from({ length: 20 }, (_, i) => `Line ${i + 1}`).join('\\n');
        console.log(JSON.stringify({ same: distillDiagnostics(out) === out }));
        """
        res = self.run_node_eval(code)
        self.assertEqual(res.returncode, 0, f"Error: {res.stderr}")
        self.assertTrue(json.loads(res.stdout.strip())["same"])

if __name__ == "__main__":
    unittest.main()
