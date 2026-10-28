"""Run every test_*.py in a directory in its own process, a few at a time.

Usage: python3 tests/run_parallel.py [tests_dir]   (tests_dir defaults to this script's directory)
"""
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MAX_WORKERS = 8
# The pre-commit hook and some tests export these; a child must start from a clean environment.
STRIPPED_PREFIXES = ("BATON_HOOK", "BATON_DEBUG", "BATON_GATEKEEPER", "BATON_AGY_", "BATON_DIAGNOSE_MIN_LINES", "STUB_", "NPM_CONFIG_")


def clean_env():
    return {k: v for k, v in os.environ.items() if not k.upper().startswith(STRIPPED_PREFIXES)}


def run_module(tests_dir, module):
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", str(tests_dir), "-t", str(tests_dir.parent), "-p", module.name]
    res = subprocess.run(cmd, cwd=tests_dir.parent, env=clean_env(), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return module, res.returncode, res.stdout + res.stderr


def main(argv):
    tests_dir = Path(argv[1] if len(argv) > 1 else Path(__file__).resolve().parent).resolve()
    # Optional module patterns after the directory (test_tailor_*.py) narrow the run, for verify routes
    patterns = argv[2:] or ["test_*.py"]
    modules = sorted({m for pattern in patterns for m in tests_dir.glob(pattern)})
    if not modules:
        print(f"No test modules found in {tests_dir}", file=sys.stderr)
        return 1
    started = time.time()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = list(pool.map(lambda m: run_module(tests_dir, m), modules))
    failed = [(m, out) for m, code, out in results if code != 0]
    for module, output in failed:
        print(f"=== FAILED: {module.name} ===")
        print(output.rstrip())
    elapsed = time.time() - started
    print(f"Ran {len(modules)} test modules in {elapsed:.1f}s: {len(modules) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
