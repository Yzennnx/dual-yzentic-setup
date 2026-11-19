# Engineering Workflows & The Superpowers Lifecycle

## 1. Workflow presets

The tier selects the required checks. The preset selects who performs the work.

| Preset | Interactive session and implementation | Tests and diagnosis | Tier 3 review |
|---|---|---|---|
| `classic` | Claude leads. One Sonnet builder run implements the Tier 3 plan. | Builder writes named Tier 3 tests. Antigravity takes eligible Gatekeeper jobs. | Antigravity, with the documented Claude fallback. |
| `agy-build` | Claude designs and checks the diff. Antigravity implements in its build job. | Antigravity's separate rule-test job covers changed rules. The build job writes ordinary tests. | Antigravity reviews the branch after Claude's diff check. |
| `codex-agy` | Codex designs and implements directly. | Codex writes named Tier 3 tests. Antigravity takes eligible Gatekeeper jobs. | Antigravity reviews. Codex addresses findings. |
| `codex-solo` | Codex designs and implements directly. | Codex writes tests and diagnoses failures. | Use the solo independent check below. |
| `claude-solo` | Claude designs and implements directly. | Claude writes tests and diagnoses failures. | Use the solo independent check below. |
| `agy-solo` | Interactive Antigravity designs and implements directly. | Antigravity writes tests and diagnoses failures. | Use the solo independent check below. |

### Switching

Use `npm run workflow -- list` to see presets, `npm run workflow -- status` to see the active roles, and `npm run workflow -- <preset>` to set one for the current checkout. The [workflow skill](../../.agents/skills/workflow/SKILL.md) uses the same command. The local selection is Git-ignored. `npm run workflow -- reset` clears it, so the checkout follows `workflow.mode` in the [blueprint](../../project-blueprint.json). The built-in default is `classic` when the blueprint omits a mode.

If the next role belongs to another agent, open its interactive session in the same checkout. Check the preset at task start, after a switch, and when resuming. Wait for the current command to finish before resuming in another agent. Solo runs in that session with headless jobs and subagents disabled.

`agy-build` assigns implementation to the Antigravity build job by default. Paired presets also retain the explicit `npm run agy:build` and `npm run agy:qa` commands for a developer-directed job.

### Handoff while a task is in progress

Before changing sessions mid-task, write `.agents/sync/resume.md` with the task's branch, tier, agreed behavior or approved plan, current changes, verification commands and results, known tests or review still owed, and the next step. This local note survives verification, switching, and `npm run sync:reset`. Start the next session on the same branch, read the note and current diff, and honor the recorded approval for the same design. Note the outcome of any remaining item in the resume note. When the task ends, mark the note complete and record the final state in the session handoff. A switch between tasks only needs the preset selection.

## 2. Tiered execution and testing

- **Tier 1 (Express):** Apply [fast-track](../../.agents/skills/fast-track/SKILL.md) to cosmetic edits and inspect the diff. Tests, full regression, production build, and agent delegation are exempt.
- **Tier 2 (Standard):** Propose a short design in chat and wait for approval. Implement, verify, and commit. Run configured E2E when a user-facing flow changes. Keep this tier in chat and skip branch review.
- **Tier 3 (Risky Surface):** Agree on design and tasks in chat (use brainstorming and `superpowers:writing-plans` where available). Name tests per task, receive one approval, and save the approved design unchanged as `docs/specs/YYYY-MM-DD-<name>-plan.md`. The assigned implementer writes the ordinary named tests and implements the plan. Run `npm run verify:agent -- --tier 3`, configured E2E, and the configured build. Get one independent review, evaluate each finding, fix what stands, and verify the fixes. Run `npm run verify:agent -- --full` once on the clean final tip, then `npm run merge -- <branch>` into local `main`. Update the session handoff. Ask before pushing.

Scout only when the task, handoff, plan, and a focused search have not found the files. In paired modes use `npm run scout -- "<task>"` and open the files and ranges it lists. In solo, the interactive agent searches the repository. Keep test logs in the baton and resolve failures from distilled output or the available diagnosis.

### Test authorship and verification

Every logic change needs covering tests that pass. Use the existing tests if they cover the approved behavior.

- In solo, the interactive agent writes any new ordinary tests and diagnoses failures. A source change without a test edit is a prompt to check coverage. Such a prompt does not establish that a test is missing.
- In eligible paired runs, the baton asks Antigravity to write missing tests when source files changed and no test file did. If Gatekeeper is bypassed or unavailable, the interactive agent owns the ordinary missing tests. A failing delegated test may reveal a code or test error. Verify against the approved behavior.
- `npm run sync:status` reports recorded tests owed and their owner separately from verification. Confirm coverage, then name the covered source on the scoped run, for example `npm run verify:agent -- --tier 2 --scope tests/app.test.js --covers src/app.js`. Repeat `--covers` when that test covers multiple owed paths. A pass clears only the named paths. A full suite pass alone keeps the recorded follow-up visible.
- When the implementer owns a new test, use red-green-refactor. Write a minimal failing test, verify that it fails for the expected reason, implement the behavior, verify it passes, and refactor with green tests.
- Verify through the baton. Use `npm run verify:agent -- --tier 2 --scope <test file>` for a covering file, and `npm run verify:agent -- --tier 3` for the tier-specific fixture or project checks. On feature branches the baton runs configured routes for the change. On the clean final tip `--full` runs the whole suite and records the merge evidence. The hook reuses a matching verification result for the same content.
- Keep unit and component tests fast. End-to-end tests are for user journeys named in the design and live under `e2e/`. Run them through `npm run verify:agent -- --e2e` when defined for the project. The commit hook skips E2E.
- `--debug` lets you verify with temporary logging and defer eligible test writing. The next ordinary paired verification attempts the owed tests. `verify.routes`, `risky_paths`, and `no_tests_in` in the blueprint continue to control routing, tier detection, and permitted test locations.

### Independent checks

**Changed-rule tests.** Use the approved rule text and cite its ID. In `classic` and `codex-agy`, use Antigravity's eligible Gatekeeper job or hand off that rule alone to a separate test author when ordinary tests suppress the automatic job. In `agy-build`, the separate rule-test job runs first. In solo, the developer can independently write the test from the rule, or explicitly arrange a separate test author. Resolve the handoff before declaring the change complete.

**Independent review.** In paired mode, run `npm run review` once on the branch and assess its findings. In solo, inspect the diff yourself and then ask the developer to review independently, or explicitly select a paired preset for the review of that same branch. Record the reviewer, reviewed commit, and disposition in the local resume note. Review evidence and full verification are both needed for the Tier 3 workflow. The merge command checks the full-verification note on the final branch tip.

### Learning mode

When `workflow.learning` is true (the default), keep the learning summary in Tier 2 and Tier 3. Before approval, use up to three lines on the layer touched, the data flow, and one question the developer should be able to answer. After implementation, use up to five lines on the files changed, data flow, one concept with its location, and one line to read in the diff. Explain questions with plain language and a small example. Once a week or on request, offer a small Tier 1 or Tier 2 task for the developer to write and for the agent to review.

### Web Testing Pyramid
Web applications in this repository adhere to a three-tier testing pyramid:
- **Unit & Custom Hook Tests (Vitest):** Millisecond-fast execution of pure business logic, calculations, and custom React hooks.
- **Component & Interaction Tests (React Testing Library):** User-centric verification of UI rendering, form events, and accessibility attributes without mocking internal state.
- **End-to-End User Journeys (Playwright via the global `webapp-testing` skill):** Headless browser automation verifying critical user paths (auth, multi-step checkout, forms, and all 4 UI states).

---

## 3. Systematic Debugging Rules

Enforced via `superpowers:systematic-debugging`:
- **Never guess or patch symptoms.**
- Investigate root causes using minimal reproduction scripts, inspection logs, and stack trace analysis.
- Formulate a testable hypothesis before writing any fix.

---

## 4. Git Hygiene & Branching Strategy

- **Feature Branches:** Create dedicated topic branches from `main`:
  ```bash
  git checkout -b feature/<descriptive-name>
  ```
- **Isolated Worktrees:** For parallel agent work or large refactors, use `superpowers:using-git-worktrees` or the global `orca-cli` skill.
- **Conventional Commits:** Format commit messages with clear semantic types (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`).

### Pull Request & Pre-Merge Checklist
Before completing a task, opening a PR, or merging into `main`:
- [ ] **Automated Tests Green:** `npm run verify:agent -- --tier 3` passes. Do not run the suite directly.
- [ ] **End-to-End Green:** `npm run verify:agent -- --e2e` passes, when the project defines `verify.e2e`.
- [ ] **Reviewed:** The selected preset's required independent review is recorded and its findings are fixed or answered.
- [ ] **Acceptance Criteria Met:** Feature satisfies the rules in its feature doc under [`docs/rules/features/`](../rules/README.md) and every invariant in `docs/rules/invariants.md`.
- [ ] **The 4 UI States Handled:** Loading (skeletons), Empty, Error, and Success states verified.
- [ ] **Accessibility & Web Vitals:** Keyboard operable (WCAG 2.1 AA) with zero layout shift regressions (CLS < 0.1).
- [ ] **Zero Secret Leaks:** Zero credentials, tokens, or `.env` traces in commits or logs.

