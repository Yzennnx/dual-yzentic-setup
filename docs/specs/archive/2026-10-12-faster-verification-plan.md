# Faster Verification: Design and Plan

> **For the builder agent:** implement Tasks 1 to 4 in order, one commit per task. Read "Design", "Global Constraints", and those four tasks. Tasks 5 and 6 are the planner's.

- **Date:** 2026-10-12
- **Status:** Approved in chat by the developer
- **Builds on:** [`2026-10-11-antigravity-delegation-design.md`](2026-10-11-antigravity-delegation-design.md)

## Goal

Remove the waits in the workflow that are slow without being necessary.

## Design

Seven changes, each answering a measured or observed cost.

| # | Change | Why |
| :--- | :--- | :--- |
| 1 | End-to-end tests get their own command, `project.verify.e2e`, run only with `npm run verify:agent -- --e2e`. | Today the baton has one test command, so a browser suite either runs on every verify and commit or never. |
| 2 | The commit hook skips the tests when the baton already passed the same command on the same content. | The same tests run twice: on `verify`, then again on commit. |
| 3 | A failed run gets an Antigravity diagnosis only when it is not readable as it is. | Every failure cost 22 s and 61,000 tokens, including one-line failures. |
| 4 | Scout and diagnosis use a fast model; test writing and review keep the deep one. | Scout took 240 s on `gemini-3.8-flash-high`. |
| 5 | Scout is on demand, not a step before every Tier 2 and 3 task. | A plan that names the files makes it redundant. |
| 6 | A Tier 3 feature gets one design-and-plan document and one approval. | Two documents and two stops, for one developer. |
| 7 | Small related plan tasks go to one builder run. | Each builder run starts cold; eight runs took 2 to 10 minutes each. |

Changes 1 to 4 are code (Tasks 1 to 4). Changes 5 to 7 are rules (Task 5). This document is itself written under changes 6 and 7.

**Left alone on purpose:** Tier 2 without `--scope` still runs the whole of `verify.test`. Once the browser suite is out of that command it should be fast, and it catches regressions.

## Global Constraints

- No new npm dependencies. Node ES modules, standard library only. Tests are Python `unittest` driving the scripts through `subprocess` against fixtures from `tests/repo_fixture.py`.
- Tests never touch the real repo and never launch the real `agy` (`BATON_AGY_CMD` points at `tests/stubs/agy_stub.mjs`).
- Each task is test-first: write the listed tests, watch them fail for the right reason, then change the code.
- For your own checks run `npm run verify:agent -- --tier 2 --scope tests/<file>.py --no-gatekeeper`. The `--no-gatekeeper` matters: a failing red-phase run would otherwise launch the real Antigravity to diagnose it.
- Commit normally. The pre-commit hook runs the baton and blocks a failing commit; fix the cause, never bypass it.
- New options are trailing and defaulted. A project that sets none of the new fields or variables behaves exactly as today, except where a task says otherwise.
- `tests/test_repo_isolation.py` flags certain literal patterns in test files (for example `self.root / "src"`); avoid them.

---

### Task 1: End-to-end tests as a separate, opt-in command

- [x] **Status** (commit `1260b02`)

**Files:**
- Modify: `scripts/baton.mjs`, `scripts/gatekeeper.mjs`, `scripts/changes.mjs`, `scripts/tailor.mjs`
- Tests: `tests/test_gatekeeper.py`, `tests/test_changes.py`, `tests/test_tailor_validation.py`

**Decisions:**
- **Manifest:** `project.verify.e2e` is optional. When present it must be a non-empty string; otherwise `validateManifest` reports a problem starting with `project.verify.e2e`.
- **Flag:** `verify --e2e`, or `npm_config_e2e=true` when the flag is absent. After the tier's normal verification passes, the baton prints `[Baton] Executing e2e command: <command>` and runs `verify.e2e` in the project root. Tier 1 runs no tests, so with `--e2e` only the e2e command runs. Both must pass for `verified`.
- **Not configured:** `--e2e` when `readVerifyConfig` has no `e2e` prints `[Baton] No e2e command configured (project.verify.e2e).` to stderr and exits 1 before running anything, leaving state unchanged.
- **Never implicit:** without `--e2e` the e2e command does not run, on any tier.
- **Failure:** an e2e failure is an ordinary failure (turn count, `verification_failed`, distilled output or diagnosis).
- **State:** after every `verify`, `state.e2e` is `"passed"`, `"failed"`, or `"not_run"`. The Verification Report in `handoff.md` ends with a line `E2E: passed`, `E2E: failed`, or `E2E: not run`.
- **Test files:** `isTestFile` is also true for a path under an `e2e/` directory.
- **Gatekeeper write prompt:** add one sentence group immediately before the plain-paths rule (which stays last):
  - when `verify.e2e` is configured: `Write unit or component tests. Write an end-to-end test only when the change adds or alters a user journey named in the spec, and put it under e2e/.`
  - otherwise: `Write unit or component tests only. Do not write end-to-end or browser tests.`

**Tests:**
- `test_tailor_validation.py`: `verify.e2e` as `""` and as `7` each report `project.verify.e2e`; absent and a real command are valid.
- `test_changes.py`: `e2e/login.spec.ts` and `e2e/helpers/auth.js` are test files.
- `test_gatekeeper.py` (fixture blueprints gain `verify.e2e` where needed; use Node one-liners that append to a file named by an environment variable outside the fixture to prove a command ran):
  - without `--e2e`, a configured e2e command does not run, on Tier 2 and on Tier 3, and `state.e2e` is `not_run`;
  - with `--e2e`, the test command runs first and the e2e command second, exit 0, `state.e2e` is `passed`, and `handoff.md` has `E2E: passed`;
  - with `--e2e` on a Tier 1 change, only the e2e command runs;
  - a failing e2e command exits 1 with `verification_failed`, turn count 1, `state.e2e` `failed`;
  - a failing test command with `--e2e` does not run the e2e command;
  - `--e2e` with no e2e configured exits 1 with the message, runs nothing, and leaves `handoff.json` byte-identical;
  - `npm_config_e2e=true` behaves as the flag;
  - the write prompt carries the first sentence group when e2e is configured and the second when it is not, and still ends with the plain-paths rule.

**Commit:** `feat(baton): run end-to-end tests only on request`

---

### Task 2: The commit hook does not repeat a passed run

- [x] **Status** (commit `f35c07f`)

**Files:**
- Modify: `scripts/changes.mjs`, `scripts/baton.mjs`, `scripts/install-hooks.mjs`, `.githooks/pre-commit` (regenerate with `node scripts/install-hooks.mjs`)
- Tests: `tests/test_changes.py`, `tests/test_e2e_baton_flow.py`, `tests/test_hooks.py`

**Decisions:**
- `changes.mjs` exports `fingerprintChanges(root) -> string`: a SHA-1 over the current `HEAD` commit id (empty when there is no commit) and the sorted `[path, hash]` pairs of `snapshotChanges(root)`.
- On every passing `verify` the baton stores `state.verified = { fingerprint, command }`. `command` is the test command that ran, or the string `express` for Tier 1. A failing `verify` sets `state.verified` to `null`. The fingerprint is taken after the run, so files written during it (Gatekeeper tests) are included.
- The generated hook exports `BATON_HOOK=1` next to `BATON_GATEKEEPER=0`.
- **Hook mode** (`BATON_HOOK=1`): before the Gatekeeper step and before any command runs, if `state.status` is `verified` and `state.verified` equals the current fingerprint and the command this run would execute, print `[Baton] Already verified for this content; skipping.` and exit 0 without writing state.
- Outside hook mode nothing is skipped.

**Tests:**
- `test_changes.py`: the fingerprint is stable across two calls; it changes when a changed file's content changes, when a new file appears, and when `HEAD` moves.
- `test_e2e_baton_flow.py` (initialized fixture whose `verify.test` appends to a counter file outside the fixture):
  - `verify`, then `verify` with `BATON_HOOK=1` on the unchanged tree: the command ran once and the second run prints the skip line;
  - editing a file between the two runs makes the hook run the command;
  - a first run with `--scope` (a different command) does not let the hook skip;
  - a failing first run does not let the hook skip;
  - a second run without `BATON_HOOK` runs the command again;
  - a Tier 1 pass followed by a hook run on the same content skips.
- `test_hooks.py`: the generated hook contains `BATON_HOOK=1`.

**Commit:** `feat(baton): skip the commit-hook run when the same content already passed`

---

### Task 3: Diagnose only what is not readable as it is

- [x] **Status** (commit `dd00296`)

**Files:**
- Modify: `scripts/gatekeeper.mjs`, `scripts/baton.mjs`
- Tests: `tests/test_gatekeeper.py`

**Decisions:**
- A diagnosis launch happens only when at least one holds:
  - the failure output has more than `N` non-empty lines, where `N` is `BATON_DIAGNOSE_MIN_LINES` (default `40`; `0` means always diagnose);
  - `test-results/` or `playwright-report/` exists in the project root;
  - the command that failed was the e2e command.
- Otherwise the baton prints the distilled excerpt as it did before the Gatekeeper existed, launches nothing, and does not write `last-failure.log`.
- `--no-gatekeeper` and `BATON_GATEKEEPER=0` still disable diagnosis entirely.
- Existing tests that expect a diagnosis for a one-line failure set `BATON_DIAGNOSE_MIN_LINES=0`. Put that in the `baton()` helper's default environment and override it in the new tests.

**Tests (`test_gatekeeper.py`):** a one-line failure with the default threshold launches nothing and prints the excerpt; a 41-line failure launches; a 40-line failure does not; a one-line failure launches when `playwright-report/` exists; a one-line e2e failure launches; `BATON_DIAGNOSE_MIN_LINES=0` launches for a one-line failure.

**Commit:** `feat(baton): ask for a diagnosis only when the failure is long or from a browser run`

---

### Task 4: A fast model for scout and diagnosis

- [x] **Status** (commit `cf93d4f`)

**Files:**
- Modify: `scripts/agy.mjs`
- Tests: `tests/test_agy_launcher.py`, `tests/test_scout.py`, `tests/test_review.py`, `tests/test_gatekeeper.py`

**Decisions:**
- `agy.mjs` exports `modelForJob(job) -> string`. Jobs `scout` and `diagnose` use the fast model: `BATON_AGY_MODEL_FAST`, default `gemini-3.8-flash-low`. Every other job, including `write_tests` and `review`, uses the deep model: `BATON_AGY_MODEL_DEEP`, default `gemini-3.8-flash-high`.
- `BATON_AGY_MODEL`, when set, overrides both, as it does today.
- The delegation entry gains `model`.

**Tests:** `modelForJob` for each of the four jobs and an unknown one, with no variables, with each tier variable, and with `BATON_AGY_MODEL` set; the recorded `--model` argument is the fast default for scout and for a diagnosis launch, and the deep default for review and for a test-writing launch; `entry.model` is recorded.

**Commit:** `feat(agy): use a fast model for scout and diagnosis`

---

### Task 7: Fixes from real runs

- [x] **Status** (commits `8fd9490`, `c6c12aa`, `8eb5339`)

Found by running the result of Tasks 1 to 4 for real on 2026-10-12. One grouped builder run, three commits.

**Files:**
- Create: `tests/run_parallel.py`, `tests/test_run_parallel.py`
- Modify: `scripts/baton.mjs`, `scripts/gatekeeper.mjs`, `scripts/agy.mjs`, `scripts/scout.mjs`, `scripts/review.mjs`, `tests/repo_fixture.py`, `tests/stubs/agy_stub.mjs`, and the test files named below
- Given: `tests/fixtures/node_test_failure.txt`, the real output of one failing `node --test` test (61 lines)

**Decisions:**

*Commit A: a diagnosis only when it earns its cost.*
1. `BATON_DIAGNOSE_MIN_LINES` defaults to `150`. One failing `node --test` test printed 59 non-empty lines, so a threshold of 40 diagnosed nearly every failure. The boundary tests move to 150 and 151 lines.
2. `distillDiagnostics` also keeps lines that match `not ok`, `actual`, `location`, or `✖`. For the given fixture the excerpt must contain the failing test's name (`clamps percent above 100`), `expected: 0`, `actual: -25`, and a `location` line, in at most 25 lines. Today's excerpt for it has none of the name, the actual value, or the location.

*Commit B: this repository's own suite, faster.*
3. `tests/run_parallel.py [tests_dir]` (standard library only; `tests_dir` defaults to the script's own directory) runs every `test_*.py` in that directory in its own process, at most 8 at a time, each as `<sys.executable> -m unittest discover -s <tests_dir> -t <parent of tests_dir> -p <file name>`. It prints the captured output of each failing module, ends with the single line `Ran <n> test modules in <s>s: <p> passed, <f> failed`, and exits 1 when any failed, 0 otherwise.
4. The baton's default command, used when no `verify.test` applies and no scope is given, becomes `python3 tests/run_parallel.py`. Measured here: 190 s serially, 84 s with the files in parallel.
5. `repo_fixture.make_template_repo(tmp, skills=True)`: with `skills=False` it creates no skill stub folders. Fixtures that do not exercise skills pass `skills=False`: those in `test_gatekeeper.py`, `test_e2e_baton_flow.py`, `test_review.py`, `test_scout.py`, `test_agy_launcher.py`, `test_changes.py`, `test_hooks.py`, and `test_sync_schema.py`. Report how long `test_gatekeeper.py` takes before and after.

*Commit C: a review that has time to finish, and failures that say why.*
6. The launch timeout default is per job: `review` gets 1200 seconds, every other job 600. `BATON_AGY_TIMEOUT` overrides both. Export `timeoutForJob(job)`.
7. When the tool returns JSON whose `status` is not `SUCCESS`, `detail` starts with `status <STATUS>`. Add a stub mode `status_timeout` that prints `{"status":"TIMEOUT","response":"","usage":{"total_tokens":77}}`.
8. Wherever scout, review, or the baton reports a launch that was not `ok`, the reason is followed by the first line of `detail` when there is one: `(<reason>: <first line>)`. A real review ran 590 seconds, used 265,009 tokens, and reported only `(failed)`.

**Tests:**
- `test_baton_runner.py`: the excerpt of the fixture meets decision 2; an output of 20 lines is still returned whole.
- `test_gatekeeper.py`: 150 lines does not launch a diagnosis and 151 does; the skipped-launch message carries the detail's first line.
- `test_run_parallel.py`: against a temp `tests` directory holding one passing and one failing module, the runner exits 1, prints the failing module's output and not the passing one's, and ends with `Ran 2 test modules` and `1 passed, 1 failed`; with two passing modules it exits 0.
- `test_baton_verify_config.py`: the default command is `python3 tests/run_parallel.py`; a `.py` scope still resolves to `python3 -m unittest <scope>`.
- `test_agy_launcher.py`: `timeoutForJob` for `review`, `scout`, and an unknown job, with and without `BATON_AGY_TIMEOUT`; the `--print-timeout` argument is `1200s` for a review launch; stub mode `status_timeout` gives reason `failed`, a `detail` starting `status TIMEOUT`, and `entry.total_tokens` 77.
- `test_scout.py`, `test_review.py`: the unavailable line includes the detail's first line.

**Verify:** `--scope` with `--no-gatekeeper` on each test file you touched.

**Commits:** `fix(baton): raise the diagnosis threshold and make the excerpt readable`, `perf(tests): run the suite in parallel with lighter fixtures`, `fix(agy): give review a longer timeout and report why a launch failed`

---

### Task 5: Rules and documentation (planner)

- [x] **Status** (commit `b345e46`)

- **Scout on demand:** `CLAUDE.md` directive 4, the handbook, `README.md`, and `docs/ai/workflows.md`. Run it when the files are not known; skip it when the task or plan names them.
- **One document, one approval:** a Tier 3 feature is designed in chat, then written as one `docs/specs/YYYY-MM-DD-<name>-plan.md` (design first, tasks after) with one approval. `AGENTS.md`, `CLAUDE.md`, the handbook, `workflows.md`, `architecture.md`, and the session hook text.
- **Grouped builder runs:** `CLAUDE.md` section 3.2 and `.claude/agents/builder.md`.
- **E2E rule:** keep `verify.test` fast and put any browser suite in `verify.e2e`; run `npm run verify:agent -- --e2e` once per Tier 3 branch before `npm run review`. `tailor-setup` skill, `README.md`, `AGENTS.md`, `CLAUDE.md`, `workflows.md`.
- The new variables in `README.md`; amendments in the delegation spec; `docs/PLAN.md`; `.agents/sync/session.md`.

### Task 6: Measure and review (planner)

- [x] **Status** (review fixes in commit `3a581df`)

- One real scout on the fast model: time, tokens, and whether the brief is usable.
- `npm run review` on the branch; re-grade, one fix pass.
- Full suite in a fresh clone; merge to `main`.

**Results (2026-10-12):**

| Measure | Before | After |
| :--- | :--- | :--- |
| This repository's suite | 190 s | 56 s |
| Tests on commit, after a passing `verify` | 190 s | 1 s |
| Scout | 240 s, 121,403 tokens (deep model) | 93 s, 180,591 tokens (fast model) |
| Diagnosis | 21.8 s, 60,807 tokens | 12.5 s, 57,692 tokens |
| `test_gatekeeper.py` | 73 s | 40 s |
| Four plan tasks | about 100,000 Sonnet tokens each, one run each | 117,462 for all four in one run |

- The fast model makes scout quicker but not cheaper in tokens, and its brief named a slightly wrong test file.
- The first review of this branch ran 590 s, used 265,009 tokens, and returned nothing; the second, with a 1200 s limit, took 607 s and 319,381 tokens and found the stale-artefact bug fixed in `3a581df`.
- One failing `node --test` test prints 59 lines, which is why the diagnosis threshold moved from 40 to 150.
- Not fixed, found on the way: `npm run init:project` writes no `verify` commands, so a wizard-started project keeps running this template's suite.
