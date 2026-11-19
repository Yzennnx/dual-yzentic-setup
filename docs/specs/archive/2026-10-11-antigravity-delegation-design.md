# Design Spec: Antigravity Delegation (Scout, Gatekeeper, Review)

- **Date:** 2026-10-11
- **Status:** Approved and implemented (see Amendments)
- **Repository:** [`dual-yzentic-setup`](../../../)
- **Builds on:** [`2026-10-11-tailor-setup-design.md`](2026-10-11-tailor-setup-design.md) (branch `feat/tailor-setup`)

---

## 1. Objective

### Problem Statement
The repository describes a Builder (Claude Code: planning and source code) and a Gatekeeper (Antigravity: testing), but nothing connects them. [`scripts/baton.mjs`](../../../scripts/baton.mjs) never launches Antigravity, and `active_agent` is always `claude`. In practice Claude explores the codebase, writes the tests, reads the failures, and reviews its own work, all on Claude quota.

### Intended Outcome
Claude plans and writes source code. Three jobs move to Antigravity, launched headlessly by scripts and billed to the Antigravity account, with no manual step:

1. **Scout:** find the files and line ranges a task touches, so Claude does not explore.
2. **Gatekeeper:** write tests for untested code changes, and diagnose test failures.
3. **Review:** review a branch's diff against its spec and plan.

### Success Criteria
1. Each job runs from one command, with no Antigravity window opened by hand.
2. What Claude reads back from each job is short: a brief, a root-cause note, or a findings list.
3. Test pass or fail is decided by the baton running the tests, never by what a model reports.
4. A developer without Antigravity installed, logged in, or in quota is not blocked; each job degrades to today's behaviour.
5. Antigravity cannot silently change source code.
6. Antigravity token use per launch is recorded where the developer can see it.

### Out of Scope
- Antigravity running tests, dev servers, browsers, or any shell command. Headless mode denies commands by default (Section 3); allow-rules are a later decision.
- Test-first ordering (tests written before the Builder implements).
- Antigravity writing source code from a plan.
- Launching the Builder headlessly, or launching through Orca.

### Cost Note
This moves work from Claude quota to Antigravity quota. Total tokens across both agents rise, because Antigravity re-reads files Claude may also read. Running tests costs no tokens on either side.

---

## 2. Probe Findings

Measured on 2026-10-11 with `agy` 1.3.3 on Windows, in a scratch directory. Four launches.

| Question | Finding |
| :--- | :--- |
| Unattended file edits | `--mode accept-edits` is enough. A test file was written with no prompt. `--dangerously-skip-permissions` is **not** needed. |
| Shell commands | Auto-denied in headless mode. The run still reports `status: "SUCCESS"` with an empty `response` and a `denied_actions` list. |
| Output | `--output-format json` prints one JSON object: `status`, `response`, `duration_seconds`, `usage` (`input_tokens`, `output_tokens`, `total_tokens`), and `denied_actions` when any. |
| Working directory | Honoured. Files were read from and written to the launch directory. |
| Write task, default model | 35 seconds, 60,501 tokens (58,412 input) to write a six-line test. |
| Read-only task, `gemini-3.8-flash-low` | 5 seconds, 26,041 tokens. |
| Unknown model name | Prints `error: invalid model selection` and no JSON. |

**Not measured:** the exit code on errors; behaviour when logged out or out of quota; whether an edit is denied when `--mode accept-edits` is absent; whether screenshots can be read; what a token count means in Antigravity quota terms.

**Consequences for the design.**
- Every launch has a fixed overhead of roughly 13,000 to 58,000 input tokens before it reads anything, so launches are for jobs worth that, not for one-line questions.
- Success is detected from the JSON (`status` is `SUCCESS` and `response` is non-empty), not from the exit code.
- Because the undenied-edit case is unmeasured, every launch is followed by a change-set check, including read-only ones.

---

## 3. Shared Launcher

New module `scripts/agy.mjs`. One function:

`launchAgy({ prompt, allowEdits = false, timeoutSeconds = 300, root }) -> { ok, response, usage, deniedActions, reason }`

- Runs `agy --print <prompt> --output-format json --print-timeout <n>s`, adding `--mode accept-edits` when `allowEdits` is true, and always `--model <id>`. It is spawned without a shell, in `root`.
- The executable defaults to `agy` and is overridable with `BATON_AGY_CMD`. Tests set this to a stub.
- `ok` is true only when stdout parses as JSON, `status` is `SUCCESS`, and `response` is non-empty. Otherwise `reason` is one of `not_installed`, `timeout`, `denied` (non-empty `denied_actions`), or `failed` (with the first lines of output).
- Each call appends one entry to a `delegations` list in `handoff.json`: job name, `ok`, `reason`, duration, and `total_tokens`. The list keeps the last 20 entries. `npm run sync:status` prints the token total.
- Prompts carry file paths, never file contents, so they stay far below the Windows command-line limit.

### Model
Every job uses `gemini-3.8-flash-high`, passed as `--model`. It is overridable with `BATON_AGY_MODEL`. The probe measured `gemini-3.8-flash-low` and Antigravity's default model, not this one, so its time and token cost per launch are not yet known; the `delegations` log will show them from the first real run.

### Scope Guard
Used after every launch. Before launching, record the change set from `git status --porcelain` plus a content hash of each changed file. Afterwards:

- With `allowEdits` false: any difference is out of scope.
- With `allowEdits` true: new or modified **test files** are allowed and returned as `testsWritten`; any other difference is out of scope.

Out-of-scope files are reported by name. They are never reverted, because a revert could destroy the Builder's own uncommitted work.

**Test file.** A path under a `tests/`, `test/`, or `__tests__/` directory, or whose file name matches `test_*.py`, `*_test.*`, `*.test.*`, or `*.spec.*`.

---

## 4. Scout

`npm run scout -- "<task description>"`, implemented in `scripts/scout.mjs`.

- Launches read-only. The prompt gives the task description, `docs/PLAN.md`, and `project.source_spec` when the blueprint has one. It asks for: the files to change; the files to read first; for each, the relevant function or line range and one line on why; and existing patterns to follow. At most 40 lines, in a fixed format, with no prose introduction.
- Writes the response to `.agents/sync/scout.md` (overwritten each run, git-ignored) and prints it.
- If the launch is not `ok`, prints one line saying the scout was unavailable and why, and exits 0. The Builder then explores as today.

[`CLAUDE.md`](../../../CLAUDE.md) gains a directive: before a Tier 2 or 3 task, run the scout and open only the files and ranges it lists; explore further only where the brief proves insufficient, and say so when that happens.

---

## 5. Gatekeeper

Runs inside `npm run verify:agent`. Logic lives in `scripts/gatekeeper.mjs`; `baton.mjs` calls it.

### 5.1 Writing Tests

| Condition | Behaviour |
| :--- | :--- |
| Tier 1 | Unchanged. No launch. |
| `--no-gatekeeper` flag, or `BATON_GATEKEEPER=0` | No launch. |
| Tier 2 or 3, source files changed, and at least one test file changed | No launch. |
| Tier 2 or 3, source files changed, and no test file changed | **Launch**, then run tests. |

**Source file.** A changed file that is not a test file, not cosmetic by the baton's existing Tier 1 rule, and not under `.agents/`.

The launch uses `allowEdits: true`. The prompt gives: the Gatekeeper role from [`GEMINI.md`](../../../GEMINI.md); the changed source files; `project.source_spec` and `docs/PLAN.md`; the test command from `project.verify.test`, so tests suit the runner, including Playwright where the project uses it; and the rules: write or update tests covering the listed changes, touch test files only, run nothing, and where code contradicts the spec, test to the spec and say so in one line.

While it runs, `handoff.json` has `active_agent: "antigravity"`. It is set back to `claude` whatever the outcome.

### 5.2 Verdict

The baton then runs the test command exactly as today. Pass sets `verified` and resets the turn count. Fail sets `verification_failed` and increments it. A failing Gatekeeper-written test is an ordinary failure: the Builder fixes the code, or says the test is wrong and fixes the test.

An out-of-scope change from Section 3 fails verification with `status: "gatekeeper_out_of_scope"` and the file list, before tests run.

### 5.3 Diagnosing Failures

When the test command fails on Tier 2 or 3 and the Gatekeeper is not disabled:

- The baton writes the full test output to `.agents/sync/last-failure.log` (git-ignored).
- It launches read-only. The prompt gives the log path and, when they exist, `test-results/` and `playwright-report/`. It asks for a root-cause note of at most 15 lines: failing test, file and line, expected against actual, and the most likely cause in the source.
- The baton prints that note in place of its keyword-filtered excerpt, and writes it to `handoff.md`.
- If the launch is not `ok`, the baton prints its existing excerpt, as today.

### 5.4 Unavailable

A launch that is not `ok` never fails verification by itself. For test writing, the baton warns that tests for the change are still owed and runs the existing tests. A timed-out launch still goes through the scope guard, since a killed run may have written files.

### 5.5 Pre-Commit Hook

The hook generated by `scripts/install-hooks.mjs` sets `BATON_GATEKEEPER=0`. A commit must not stall on a launch; only an explicit `npm run verify:agent` launches Antigravity.

---

## 6. Review

`npm run review -- [--base <ref>]`, implemented in `scripts/review.mjs`.

- `--base` defaults to the merge base with `main`. The script writes `git diff <base>..HEAD` to `.agents/sync/review.diff` (git-ignored), because Antigravity cannot run git itself.
- Launches read-only. The prompt gives the diff path, `project.source_spec`, and the newest `*-plan.md` in `docs/specs/` when one exists. It asks for findings in three groups (Critical, Important, Minor), each with file and line, what is wrong, and why it matters; then a one-line verdict. At most 60 lines.
- Writes the response to `.agents/sync/review.md` and prints it.
- If the launch is not `ok`, prints one line saying so and exits 1, so the caller knows no review happened.

The review is advisory. The Builder re-grades each finding, fixes what stands, and reports what it declined and why. [`docs/ai/workflows.md`](../../ai/workflows.md) names `npm run review` as the default whole-branch review, in place of a second Claude reviewer.

---

## 7. Documentation Changes

- [`GEMINI.md`](../../../GEMINI.md): a "Headless Mode" section. When launched by a script: do only the job in the prompt, run no commands, edit test files only when asked to write tests. Existing directives remain for interactive sessions. The strings `Gatekeeper`, `handoff`, and `project-blueprint.json` stay, as tests assert them.
- [`CLAUDE.md`](../../../CLAUDE.md): the scout directive from Section 4, and a line that the Builder does not write tests for a change unless the Gatekeeper was skipped.
- [`AGENTS.md`](../../../AGENTS.md) Gate 3 (TDD): under the automated Gatekeeper, tests for Tier 2 and 3 changes are authored by the Gatekeeper at verify time; test-first by the Builder still applies when the Gatekeeper is skipped.
- `docs/ai/workflows.md`: the scout, verify, and review flow.
- `.gitignore`: `.agents/sync/scout.md`, `review.md`, `review.diff`, `last-failure.log`.
- `package.json`: `scout` and `review` scripts.

---

## 8. Testing

Python `unittest` in `tests/`, driving the Node scripts through `subprocess`, against temp fixture repos initialised with `git init`. **No test launches the real `agy`.** A stub executable, set through `BATON_AGY_CMD`, records its arguments and is scripted per case to: print a success JSON; write a test file; write or modify a source file; print a `denied_actions` JSON; print non-JSON; sleep past the timeout.

- **Launcher:** flags with and without `allowEdits`; the default model and the `BATON_AGY_MODEL` override; each `reason`; the `delegations` log and its 20-entry cap; `not_installed` when the executable is missing.
- **Scope guard:** read-only launches reject any change; edit launches accept test files and reject others; a further-modified already-changed file is caught by the hash; nothing is reverted.
- **Scout:** the prompt contains the task, plan, and spec paths; the brief is written and printed; an unavailable launch exits 0.
- **Gatekeeper:** each row of the Section 5.1 table; file classification for each pattern; `active_agent` restored after success, failure, and timeout; the diagnosis note replaces the excerpt, and the excerpt returns when the launch is not `ok`.
- **Review:** the diff file is written for the right range; the findings are written and printed; an unavailable launch exits 1.
- **Regression:** the existing baton tests pass unchanged; the generated hook contains `BATON_GATEKEEPER=0`.

---

## 9. Build Order

One plan, in this order, each step usable before the next exists: launcher and scope guard; scout; Gatekeeper test writing; Gatekeeper diagnosis; review; documentation.

---

## Amendments (2026-10-11)

Implemented by Tasks 4 to 7 of [`2026-10-11-workflow-remediation-plan.md`](2026-10-11-workflow-remediation-plan.md). Where this section and the text above differ, this section is what was built.

- **Sync state is untracked.** `.agents/sync/` is git-ignored except `session.md`. `handoff.json`, `handoff.md`, `scout.md`, `review.md`, `review.diff`, and `last-failure.log` are local files.
- **Change set.** File classification lives in `scripts/changes.mjs`. With a clean working tree the baton classifies the files of the last commit; with no files at all it runs Tier 3.
- **Launcher signature.** `launchAgy({ job, prompt, allowEdits, timeoutSeconds, root })` returns `{ ok, response, usage, deniedActions, reason, detail, entry }`. It writes nothing; callers record `entry` with `appendDelegation`.
- **Overrides.** `BATON_AGY_TIMEOUT` sets the timeout. A `BATON_AGY_CMD` ending in `.mjs` is run with Node, which is how the tests substitute a stub.
- **Review flags.** `npm run review` also accepts `--spec <path>` and `--plan <path>` to override auto-detection.
- **Handoff ticket.** After every `verify` the baton rewrites `.agents/sync/handoff.md` with the changed files and the Gatekeeper's report.
- **npm argument trap.** `verify` also honours `npm_config_tier` and `npm_config_scope`, and `review` honours `npm_config_base`, `npm_config_spec`, and `npm_config_plan`, so the flags work without the `--` separator.
- **Explicit scope.** `verify --scope <test file>` never launches the Gatekeeper to write tests; naming the covering test says it exists. Failures are still diagnosed.
- **Configuration is not source.** Dotfiles and dot-directories, `package.json`, `project-blueprint.json`, and lockfiles never trigger a test-writing launch.
- **Scope guard.** A file that was changed before a launch and is gone from the change set after it (deleted, or restored to its committed content) is out of scope. Violations are recorded in `gatekeeper.out_of_scope` and listed in `handoff.md`, for the diagnosis step as well as the write step.
- **Measured cost** on `gemini-3.8-flash-high`: scout 240 s and 121,403 tokens; test writing 128 s and 149,514; diagnosis 22 s and 60,807; a 3,500-line branch review 374 s and about 246,000.

---

## Amendments (2026-10-12)

Changed by [`2026-10-12-faster-verification-plan.md`](2026-10-12-faster-verification-plan.md).

- **Models per job.** Scout and diagnosis use `BATON_AGY_MODEL_FAST` (default `gemini-3.8-flash-low`); test writing and review use `BATON_AGY_MODEL_DEEP` (default `gemini-3.8-flash-high`). `BATON_AGY_MODEL` overrides both.
- **Diagnosis is conditional.** A failed run is diagnosed only when its output is longer than `BATON_DIAGNOSE_MIN_LINES` (default 150; one failing `node --test` test prints 59 lines), when browser artefact folders exist, or when the e2e command failed. Shorter failures are printed as a distilled excerpt.
- **End-to-end tests.** `project.verify.e2e` is a separate command that runs only with `verify --e2e`. The Gatekeeper writes unit or component tests unless a change alters a user journey named in the spec, and puts end-to-end tests under `e2e/`.
- **Commit hook.** In hook mode the baton skips the run when the same content already passed the same command.
- **Scout is on demand,** not a step before every task.
- **Timeouts.** A review launch gets 1200 seconds, every other job 600. A launch that is not `ok` reports the reason and the first line of its detail.
- **The excerpt.** `distillDiagnostics` keeps test names, actual values, and locations, so a short failure is readable without a launch.
- **Measured on the fast model:** scout 93 s and 180,591 tokens (240 s and 121,403 on the deep model); diagnosis 12.5 s and 57,692 (21.8 s and 60,807).
