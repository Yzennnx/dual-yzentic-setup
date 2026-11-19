# Solo and Paired Agent Workflows

Use one agent directly or pair a coding session with Antigravity. The default `classic` preset uses Claude for design and implementation and Antigravity as the Gatekeeper. The same tiers and verification rules apply in every preset.

Run `npm run workflow -- list` to see presets and `npm run workflow -- status` to see who owns the work. Select with `npm run workflow -- <preset>`. For example, `codex-solo`, `claude-solo`, and `agy-solo` keep work in the active session. `codex-agy` pairs Codex with Antigravity. `agy-build` keeps the Antigravity builder workflow. The choice applies to this checkout and switching preserves all tracked rules. `npm run workflow -- reset` restores the blueprint default.

See the [workflow guide](docs/ai/workflows.md) for role assignments, independent checks, and how to resume an in-progress task in another session.

## Who Does What in Classic

| Job | Done by | How it starts |
| :--- | :--- | :--- |
| Planning, design, source code | Claude Code | You ask. Tier 3 plan tasks run on a Sonnet `builder` agent. |
| Finding the files a task touches | Antigravity | `npm run scout -- "<task>"`, only when they are not already known |
| Writing tests for untested changes | Antigravity | Automatic inside `npm run verify:agent` |
| Running the tests | The baton script (no model, no tokens) | `npm run verify:agent` |
| Running end-to-end tests | The baton script | `npm run verify:agent -- --e2e`, never automatically |
| Diagnosing a failure | Antigravity | Automatic when the failure is long or comes from a browser run |
| Reviewing a branch | Antigravity | `npm run review` |

Classic launches Antigravity with `agy --print`. Its Gatekeeper jobs can read the repository, and test-writing jobs can edit test files. They cannot run commands. The baton checks the delegated file scope. If `agy` is missing, logged out, out of quota, or too slow, the existing tests run, the interactive agent gets a trimmed log, and a skipped review remains outstanding.

---

## Starting a Project

**From the design in `docs/rules/`.** Start with the [`wayfinder`](.agents/skills/wayfinder/SKILL.md) skill: it lists the open decisions and either hands off to brainstorming or charts a map of decision tickets in `docs/wayfinder/` to resolve one per session. Either way the design is written straight into [`docs/rules/`](docs/rules/README.md): `invariants.md`, `architecture.md` and one doc per feature, which you review as the spec. Then invoke the [`tailor-setup`](.agents/skills/tailor-setup/SKILL.md) skill. Claude writes a manifest into [`project-blueprint.json`](project-blueprint.json), shows you a dry run, and after your yes runs:

```bash
npm run tailor
```

That archives the skills the project does not need, writes the real roadmap to [`docs/PLAN.md`](docs/PLAN.md), and points the baton at the project's own test commands. Claude then scaffolds `src/` with the stack's own generator and records its files in `architecture.md`.

Each feature doc names the code it owns (`owns:` in its front matter) and numbers its rules (`[feature#1]`). `npm run rules:check` runs in every verify: it fails when owned code changes without its doc, when a new source file has no owner, when an open PLAN task names no feature, and when a changed rule has no test citing its ID. `npm run rules:map` regenerates the feature map in [`docs/rules/README.md`](docs/rules/README.md).

---

## The Loop

```text
session start   a hook injects .agents/sync/session.md and the blueprint status
classify        Tier 1, 2, or 3
scout           npm run scout -- "<task>"            (only when the files are unknown)
build           The selected implementer (Sonnet builder for Tier 3 in classic)
verify          npm run verify:agent
                  The assigned test owner writes missing tests -> baton runs them
                  -> paired presets can request a diagnosis for long or browser failures
e2e             npm run verify:agent -- --e2e        (Tier 3, once, before review)
review          follow the preset's independent review policy (Tier 3, once)
commit          the pre-commit hook blocks a failing commit; it skips the run
                when the same content already passed
hand off        when the next task does not fit (Tier 3, new area, 3 tasks done,
                or compacted), the agent rewrites .agents/sync/session.md; you start a new session
```

---

## Three Tiers

| Tier | Scope | Process | Verification |
| :--- | :--- | :--- | :--- |
| **1: Express** | CSS, copy, Markdown, static assets | `fast-track`: edit and commit | No tests; passes in under a second |
| **2: Standard** | Any change that touches no risky surface, of any size | Chat for short fixes or a [short spec](docs/specs/README.md) for meaningful changes. No review. | The project's tests, or one file with `--scope`; e2e when a user-facing flow changed |
| **3: Risky surface** | Schemas, sync, shared domain rules, API contracts, auth, interfaces between apps | The approved chat design (tasks name their tests) saved as the plan, implement under the selected preset, review once, merge into local `main` | The full suite, plus e2e once before review |

The surface sets the tier, not the number of files.

[`scripts/baton.mjs`](scripts/baton.mjs) picks the tier from the changed files. With a clean working tree it classifies the last commit. To override:

```bash
npm run verify:agent -- --tier 1
npm run verify:agent -- --tier 2 --scope tests/auth.test.ts
npm run verify:agent -- --tier 3
npm run verify:agent -- --e2e
npm run verify:agent -- --no-gatekeeper
```

`--scope` names the test that covers a change, so the Gatekeeper is not asked to write one. Changes to configuration only (dotfiles, `package.json`, lockfiles) never launch it either.

After five failed runs in a row the baton locks until you run `npm run sync:reset`.

### Keeping verification fast

Every setting below is optional in `project-blueprint.json`; unset, the baton behaves as described above.

- **`--tier N`** (1, 2 or 3) overrides detection and is printed as "set by --tier".
- **`project.risky_paths`**: path prefixes of the risky surfaces. When set, all-cosmetic changes are Tier 1, a change under a risky prefix is Tier 3, and anything else is Tier 2 (no file-count rule).
- **`--debug`** (or `BATON_DEBUG=1`): runs the tests and defers eligible Gatekeeper test writing while debugging. The source files are kept in sync state as `tests_owed`, so the next eligible paired verification can include them.
- **`project.verify.routes`**: run only the tests that fit the changed files. Each route has `paths` (prefixes), a `command`, and an optional `setup` that runs once first. The distinct setups and then commands of every matching route run in order; `verify.test` also runs when a changed non-cosmetic file matches no route, or when no route matches. A failure names the command that failed.
- **`project.verify.no_tests_in`**: folders that must hold no tests (for example Expo Router's route folder, which is bundled into the app). The Gatekeeper is told not to write there, and `verify` fails if any changed or newly written test file is under one.
- After the Gatekeeper writes tests, the baton runs just those files once; if they fail, the Gatekeeper gets one round to fix its own tests before the normal run.
- **Fast on branches, full once.** On any branch but `main`/`master`, `verify` (and the commit hook) runs only the routes the change touches and never falls back to `verify.test`. `npm run verify:agent -- --full` runs `verify.test` whatever the tier and, on a clean tree, records a git note (`refs/notes/baton`) on HEAD. `npm run merge -- <branch>` fast-forwards only a branch whose tip carries that note.
- **`template_verify`**: the template's own verify config (same shape as `project.verify`), used while the blueprint is uninitialized; a tailored project's `project.verify` takes over.

```json
{
  "project": {
    "risky_paths": ["apps/api/", "packages/shared/src/domain/"],
    "verify": {
      "test": "npx vitest run",
      "test_scoped": "npx vitest run {scope}",
      "no_tests_in": ["apps/mobile/src/app"],
      "routes": [
        { "paths": ["apps/mobile/"], "command": "npx vitest run --project mobile" },
        { "paths": ["apps/api/"], "setup": "docker compose up -d db", "command": "npx vitest run --project api" },
        { "paths": ["scripts/", "tests/"], "command": "python tests/run_parallel.py" }
      ]
    }
  }
}
```

The last route is how this template runs its own Python tests.

### Worktrees

With Orca, the main session (the orchestrator) can hand a waiting task to a worker Claude in its own worktree while it waits on something slow. Set `workflow.orca_repo_id` and `workflow.max_workers` in the blueprint; CLAUDE.md section 4 has the rules. Workers mark their card `in-review`, and the next session start lists them under `Ready to merge:`. Every `verify:agent` takes a machine-wide lock, so two worktrees never run their suites at once.

---

## What Is Enforced

- **Failing commits are blocked** by the pre-commit hook (`npm run hook:install`). It never runs the end-to-end suite.
- **QA attack tests** (`*.qa.e2e.ts`, `npm run e2e:qa`) need a `qa` Playwright project that matches only those files, and an `e2e` project that excludes them; the template ships no `playwright.config.ts`, so the [`qa-break`](.agents/skills/qa-break/SKILL.md) skill shows the snippet.
- **The test command stays fast.** Browser suites live in `verify.e2e` and run only on request.
- **Full test suites cannot be run directly by Claude.** A hook in [`.claude/settings.json`](.claude/settings.json) blocks them and points at the baton.
- **Every session starts from the handoff.** The same file injects [`.agents/sync/session.md`](.agents/sync/session.md) at session start.
- **Antigravity stays in scope.** Files are compared before and after every launch.
- **Tests never touch your work.** Every script test runs against a temporary fixture repository.

The tier process and the builder hand-off are written rules in [`CLAUDE.md`](CLAUDE.md) and [`AGENTS.md`](AGENTS.md); nothing mechanical checks them.

---

## The Roadmap

[`docs/PLAN.md`](docs/PLAN.md) is the single source of truth for what gets built:

- **`P0` (Must-Have):** required for the core user journey to work.
- **`P1` (Should-Have):** improves the core journey.
- **`P2` (Later):** parked until P0 and P1 are done.

---

## Commands

```bash
# Start a project
npm run tailor -- --dry-run      # preview tailoring from docs/rules
npm run tailor                   # apply it
npm run rules:check              # docs vs code: drift, orphans, rule tests
npm run rules:map                # regenerate the feature map; -- <feature> prints one

# Work
npm run scout -- "<task>"        # Antigravity: which files matter
npm run verify:agent             # tests, written and diagnosed by Antigravity
npm run review                   # Antigravity: review the branch

# State
npm run sync:status              # baton state and Antigravity token use
npm run sync:reset               # clear the failure lock
npm run hook:install             # install the pre-commit hook
```

### Environment Variables

| Variable | Effect |
| :--- | :--- |
| `BATON_GATEKEEPER=0` | Never launch Antigravity from `verify` (the pre-commit hook sets this). |
| `BATON_AGY_MODEL_FAST` | First model of the scout chain. Default `gemini-4-argon-low`, then `claude-sonnet-5-5-low`, then `gpt-oss-120b-medium`. |
| `BATON_AGY_MODEL_DEEP` | First model of the chain for build, qa, test writing, diagnosis and review. Default `gemini-4-argon-medium`, then `claude-sonnet-5-5-medium`, then `gpt-oss-120b-medium`; the next one runs on a quota or model error. |
| `BATON_AGY_MODEL` | One model for every launch, with no fallback, overriding both. |
| `BATON_DIAGNOSE_MIN_LINES` | A failure longer than this many lines gets a diagnosis. Default `150`; `0` means always. |
| `BATON_AGY_TIMEOUT` | Seconds before a launch is abandoned. Default `600`, and `1200` for a review. |
| `BATON_AGY_CMD` | Executable to launch. Default `agy`. |

A launch is not free, and a launch that runs out of time still costs its full time and tokens. Measured in this repository:

| Job | Model | Time | Antigravity tokens |
| :--- | :--- | :--- | :--- |
| Scout | fast | 93 s | 181,000 |
| Scout | deep | 240 s | 121,000 |
| Diagnosis | fast | 13 s | 58,000 |
| Test writing | deep | 128 s | 150,000 |
| Branch review | deep | 374 s | 246,000 |

One review of a smaller branch ran for 590 seconds and returned nothing. `npm run sync:status` shows the running total.

---

## Saving Claude Tokens

- Plan on the session model; let the Sonnet `builder` agent implement.
- Chain up to 3 Tier 1/2 tasks in one area per session, with their designs approved together; Tier 3 gets its own session. The handoff file makes a fresh session cheap.
- Use `/caveman` for terse replies and `/ponytail` for the smallest workable change.
- General skills (`caveman`, `ponytail`, `impeccable`, …) are installed once per machine, not per repo: [`global-skills.json`](global-skills.json) lists them, `npm run skills:global` checks both agents can see them, and `-- --install` copies missing ones from `~/skill-library`. The session start warns when one is missing.
- Keep Tier 1 and Tier 2 work out of the spec-and-plan process.
