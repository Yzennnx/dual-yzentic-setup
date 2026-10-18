# Dual-Agent Setup (Claude Code + Antigravity)

**A single-developer AI workflow that keeps Claude for planning and code, and hands scouting, testing, and review to Antigravity.**

This repository is a project template. **Claude Code** is **the Builder**: it plans and writes source code. **Google Antigravity** is **the Gatekeeper**: it finds the files a task touches, writes and diagnoses tests, and reviews branches. Scripts launch Antigravity headlessly, so you work in one Claude session and your Claude quota is spent on planning and code only.

---

## Who Does What

| Job | Done by | How it starts |
| :--- | :--- | :--- |
| Planning, design, source code | Claude Code | You ask. Tier 3 plan tasks run on a Sonnet `builder` agent. |
| Finding the files a task touches | Antigravity | `npm run scout -- "<task>"`, only when they are not already known |
| Writing tests for untested changes | Antigravity | Automatic inside `npm run verify:agent` |
| Running the tests | The baton script (no model, no tokens) | `npm run verify:agent` |
| Running end-to-end tests | The baton script | `npm run verify:agent -- --e2e`, never automatically |
| Diagnosing a failure | Antigravity | Automatic when the failure is long or comes from a browser run |
| Reviewing a branch | Antigravity | `npm run review` |

Antigravity is launched with `agy --print`. It can read anything and edit test files; it cannot run commands, and a change to any non-test file fails verification. If `agy` is missing, logged out, out of quota, or too slow, each job falls back to plain behaviour: the existing tests run, Claude gets a trimmed log, and the review reports that it did not happen.

---

## Starting a Project

**From a spec (recommended).** Brainstorm the project with Claude into a design spec in [`docs/specs/`](docs/specs/), then invoke the [`tailor-setup`](.agents/skills/tailor-setup/SKILL.md) skill. Claude writes a manifest into [`project-blueprint.json`](project-blueprint.json), shows you a dry run, and after your yes runs:

```bash
npm run tailor
```

That archives the skills the project does not need, writes the real roadmap to [`docs/PLAN.md`](docs/PLAN.md), and points the baton at the project's own test commands. Claude then rewrites the stack rules in [`docs/rules/`](docs/rules/README.md) and scaffolds `src/` with the stack's own generator.

**From an archetype.** When a preset fits, run the wizard:

```bash
npm run init:project
```

It asks for the project name, a one-line mission, an archetype (`fullstack-web`, `ai-agent-app`, `frontend-dashboard`, or `minimal`), and your name.

Either way, skills that are not kept are moved to `.agents/skills-archive/`, not deleted:

```bash
npm run skill:list
npm run skill:enable <skill-name>
npm run skill:disable <skill-name>
```

---

## The Loop

```text
session start   a hook injects .agents/sync/session.md and the blueprint status
classify        Tier 1, 2, or 3
scout           npm run scout -- "<task>"            (only when the files are unknown)
build           Claude; Tier 3 runs its plan in one Sonnet builder run
verify          npm run verify:agent
                  Gatekeeper writes missing tests -> baton runs them
                  -> on a long or browser failure, Gatekeeper writes a root-cause note
e2e             npm run verify:agent -- --e2e        (Tier 3, once, before review)
review          npm run review                       (Tier 3, once; then merge into local main)
commit          the pre-commit hook blocks a failing commit; it skips the run
                when the same content already passed
hand off        Claude rewrites .agents/sync/session.md; you start a new session
```

---

## Three Tiers

| Tier | Scope | Process | Verification |
| :--- | :--- | :--- | :--- |
| **1: Express** | CSS, copy, Markdown, static assets | `fast-track`: edit and commit | No tests; passes in under a second |
| **2: Standard** | Any change that touches no risky surface, of any size | A design in chat, then build; no document, no review | The project's tests, or one file with `--scope`; e2e when a user-facing flow changed |
| **3: Risky surface** | Schemas, sync, shared domain rules, API contracts, auth, interfaces between apps | The approved chat design (tasks name their tests) saved as the plan, one builder run, review once, merge into local `main` | The full suite, plus e2e once before review |

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
- **`--debug`** (or `BATON_DEBUG=1`): runs the tests but never launches the Gatekeeper, so temporary logging does not get tests. The source files are kept in the sync state as `tests_owed`, and the next normal `verify` that writes tests includes them, then clears the list.
- **`project.verify.routes`**: run only the tests that fit the changed files. Each route has `paths` (prefixes), a `command`, and an optional `setup` that runs once first. The distinct setups and then commands of every matching route run in order; `verify.test` also runs when a changed non-cosmetic file matches no route, or when no route matches. A failure names the command that failed.
- **`project.verify.no_tests_in`**: folders that must hold no tests (for example Expo Router's route folder, which is bundled into the app). The Gatekeeper is told not to write there, and `verify` fails if any changed or newly written test file is under one.
- After the Gatekeeper writes tests, the baton runs just those files once; if they fail, the Gatekeeper gets one round to fix its own tests before the normal run.

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

---

## What Is Enforced

- **Failing commits are blocked** by the pre-commit hook (`npm run hook:install`). It never runs the end-to-end suite.
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
npm run tailor -- --dry-run      # preview spec-driven tailoring
npm run tailor                   # apply it
npm run init:project             # archetype wizard

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
| `BATON_AGY_MODEL_FAST` | Model for scout and diagnosis. Default `gemini-4-argon-medium`. |
| `BATON_AGY_MODEL_DEEP` | Model for test writing and review. Default `gemini-4-argon-medium`. |
| `BATON_AGY_MODEL` | One model for every launch, overriding both. |
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
- One task per session. The handoff file makes a fresh session cheap.
- Use `/caveman` for terse replies and `/ponytail` for the smallest workable change.
- Keep Tier 1 and Tier 2 work out of the spec-and-plan process.
