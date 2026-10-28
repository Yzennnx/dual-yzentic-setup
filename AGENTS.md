# AGENTS.md — Universal Agent Instructions

Welcome to the `dual-yzentic-setup` repository. This repository implements a dual-agent development standard for one developer: Claude Code is the Builder (planning and source code) and Google Antigravity is the Gatekeeper (tests, failure diagnosis, scouting, and review). Scripts launch the Gatekeeper headlessly, so the developer works in a single Claude session.

<CRITICAL-DIRECTIVES>
These rules are MANDATORY and NON-NEGOTIABLE. Violating the letter of the rules is violating the spirit of the rules. You CANNOT rationalize bypassing these gates.
</CRITICAL-DIRECTIVES>

---

## 1. Task Tiering & Execution Lanes

To prevent token waste and latency, all tasks are classified into three operational tiers supported natively by the Baton Coordinator (`npm run verify:agent`):

| Tier | Scope | Required Process & Verification |
| :--- | :--- | :--- |
| **Tier 1: Express Lane** *(Micro / Cosmetic)* | Pure CSS/Tailwind tweaks, copy/text edits, icon swaps, single-file non-structural adjustments. | Use [`fast-track`](.agents/skills/fast-track/SKILL.md). Auto-detected by `npm run verify:agent` or explicitly via `-- --tier 1`. **Exempt from tests, full regression runs, and production build.** |
| **Tier 2: Standard Lane** *(Features / Fixes)* | Any change, of any number of files, that touches no risky surface (below): components, pages, layout, pure logic, an isolated bug fix. | A design agreed in chat; no spec or plan file. Verified via `npm run verify:agent` (the Gatekeeper writes missing tests), or `-- --tier 2 --scope <test file>` when the covering test already exists. `npm run verify:agent -- --e2e` when a user-facing flow changed. No review. |
| **Tier 3: Risky Surface Lane** *(Architecture)* | Any change that touches a risky surface: the shape of persisted data (schemas, migrations), sync or replication, domain rules shared across apps, API routes and contracts, authentication, or the interfaces between apps and packages. | A design agreed in chat that includes the task list, each task naming its tests; one approval → that design saved as the plan document → one `builder` run → full suite via `npm run verify:agent -- --tier 3` → `npm run verify:agent -- --e2e` and the build command, when the blueprint defines them → `npm run review` once → merge into local `main`. |

Size does not set the tier; the surface does. The tier the baton detects only chooses which tests run.

**Mockup map.** Any design with mockups ends its task list with a table: mockup file, task, target component, fingerprint. It covers every file in the referenced mockup folder, or marks a row `skip: <reason>`. `npm run mockups:check -- <design.md>` must pass before the developer's yes. The fingerprint is the first 8 hex of the file's sha256; it is updated when a page is rebuilt to match its mockup.

---

## 2. Hard Operational Gates

0. **Gate 0: Fresh Clone & Project Blueprint Intake**
   - At the start of a session, inspect [`project-blueprint.json`](project-blueprint.json).
   - If `status === "uninitialized"`, DO NOT write project code yet. Start with the [`wayfinder`](.agents/skills/wayfinder/SKILL.md) skill (kickoff mode): it surfaces the open decisions and either hands off to brainstorming or charts a map. Brainstorming writes the project design straight into [`docs/rules/`](docs/rules/README.md); then use the [`tailor-setup`](.agents/skills/tailor-setup/SKILL.md) skill (`npm run tailor`).
   - Work on this template itself (`scripts/`, `tests/`, `docs/`, `.agents/`, `.claude/`) is exempt.
1. **Gate 1: Skills on Demand**
   - Consult [`docs/ai/agent-handbook.md`](docs/ai/agent-handbook.md) to pick the domain skill a task needs. Load a skill only when the task needs it.
   - For Tier 1 micro-tasks, use only [`fast-track`](.agents/skills/fast-track/SKILL.md).
2. **Gate 2: Design Before Code, Sized to the Tier**
   - **Tier 2:** state the design in chat, as short as the change allows, and wait for the developer's approval. Do not write a spec or plan file.
   - **Tier 3:** work out the design with the developer in chat, ending with the task list, each task naming the tests it adds. The developer's yes to that is the one approval. Then save the design as it was approved to [`docs/specs/`](docs/specs/), named `YYYY-MM-DD-<name>-plan.md` (design first, tasks after); do not rewrite it or ask again. Do not write a separate spec and plan. A project's kickoff spec, the one `tailor-setup` reads, is the exception: it is a `-design.md`.
   - **Tier 3 finish:** run `npm run review` once. Re-grade each finding, fix what stands, and verify the fixes with `npm run verify:agent`; do not review again. Then merge the branch into local `main` (the developer's standing approval; never push without asking), so the next branch is reviewed on its own.
   - Log all planned work in [`docs/PLAN.md`](docs/PLAN.md).
3. **Gate 3: Tests for Every Logic Change (Tier 2 & Tier 3)**
   - No logic change, mutation, or endpoint is complete until tests for it exist and pass.
   - **Authorship:** in Tier 3 the Builder writes the tests each plan task names, so the Gatekeeper is not launched. Otherwise the Gatekeeper writes them: `npm run verify:agent` launches it when source files changed and no test file did.
   - **Speed:** unit and component tests by default. An end-to-end test is written only for a user journey named in the spec, lives under `e2e/`, and runs only through `npm run verify:agent -- --e2e`.
   - **Self-check:** after the Gatekeeper writes tests, the baton runs just those files once and gives the Gatekeeper one round to fix its own failing tests. `--debug` skips test writing and records `tests_owed`; the blueprint's optional `risky_paths`, `verify.routes` and `verify.no_tests_in` set the tier, the commands and the folders that hold no tests.
   - **Fallback:** when the baton reports the Gatekeeper was skipped (not installed, not logged in, out of quota, or disabled), or when a plan task names the test, the Builder writes the test first and watches it fail (`superpowers:test-driven-development`).
4. **Gate 4: Systematic Root-Cause Debugging**
   - Never guess or blindly patch bugs. Investigate root causes with evidence before touching implementation (`superpowers:systematic-debugging`).
5. **Gate 5: Evidence Before Assertions**
   - Never claim code works without running verification output (`superpowers:verification-before-completion`).
   - Run `npm run verify:agent`. It records the result in `.agents/sync/handoff.json` and `.agents/sync/handoff.md`.
   - Never run a full test suite directly. The baton runs it and distills the output.
   - Worktrees: a worker's branch is reviewed in its own worktree (`npm run review` there). Only the orchestrator merges it into `main`.

---

## 3. Core Behavioral Tenets

1. **Evidence before assertions:**
   - Always verify exit codes and output before declaring completion.
2. **Navigable file and symbol references:**
   - In chat replies, format file paths and code symbols as clickable Markdown links using the `file://` scheme with the absolute path on the current machine.
   - In committed files, use relative Markdown links. Never commit an absolute machine path.
3. **Continuous task tracking:**
   - Keep [`docs/PLAN.md`](docs/PLAN.md) updated: log a task before starting it and mark it done when it is verified.
4. **Non-destructive & non-interactive execution:**
   - Always run commands non-interactively.
5. **Session length:**
   - Start from [`.agents/sync/session.md`](.agents/sync/session.md). After each task, note it on its `docs/PLAN.md` line. Chain further Tier 1 or Tier 2 tasks in the same app and area, up to 3 per session and before any auto-compaction; a Tier 3 task gets a fresh session. When the session ends, overwrite `session.md` with a summary of at most 20 lines (done, branch and commit, decisions, next step, hand tests owed, files to open) so the next session starts small.
6. **Zero secret exposure:**
   - Never print raw `.env` contents, API keys, credentials, or tokens. Use [`varlock`](.agents/skills/varlock/SKILL.md) and review against [`owasp-security`](.agents/skills/owasp-security/SKILL.md).

---

## 4. Skills & Documentation Routing

- [`docs/PLAN.md`](docs/PLAN.md): **Universal Living Roadmap**. The single source of truth for features and priorities.
- [`.agents/sync/`](.agents/sync/): **Dual-Agent Sync Bus**. `session.md` is the committed cross-session handoff. `handoff.json`, `handoff.md`, `scout.md`, `review.md`, and `last-failure.log` are local state written by the scripts and are not committed.
- [`docs/ai/agent-handbook.md`](docs/ai/agent-handbook.md): Skills catalog and routing index.
- [`docs/ai/workflows.md`](docs/ai/workflows.md): The scout, build, verify, and review flow.
- [`.agents/skills/`](.agents/skills/): On-demand domain skills.
- [`docs/rules/`](docs/rules/README.md): The project's design, split by feature: `invariants.md`, `architecture.md`, and `features/<feature>.md` docs that own code paths. Read `invariants.md` plus the one feature doc your task names. `npm run rules:check` keeps docs and code in step.
