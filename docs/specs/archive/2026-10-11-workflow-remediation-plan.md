# Workflow Remediation Implementation Plan

> **For the builder agent:** implement exactly one task per launch. Read this header, "Global Constraints", and your task only. Steps use checkbox (`- [ ]`) syntax; the planner ticks a task when it is merged.

**Goal:** Fix the eight findings of the 2026-10-11 workflow audit, and convert the setup from a two-developer hackathon template to a single-developer one.

**Architecture:** Every script becomes root-aware so tests run against temp fixture repos and never touch the real one. The baton gains a real change set, a working gate, and (Tasks 5 to 7) headless Antigravity launches for scouting, test writing, failure diagnosis, and review. Rules that can be enforced mechanically move into Claude Code hooks (Task 8).

**Tech Stack:** Node 22 ES modules, standard library only. Tests are Python `unittest` driving the scripts through `subprocess`.

**Spec:** [`2026-10-11-antigravity-delegation-design.md`](2026-10-11-antigravity-delegation-design.md) for Tasks 5 to 7. The audit findings below are the requirements for the rest.

## Requirements (Audit Findings)

1. No script launches Antigravity; `active_agent` never changes.
2. The gate does not gate: the pre-commit hook lets failures through; three tests fail on Windows; `verify` on a clean tree passes without running anything.
3. Doc links are absolute paths from other machines (`file:///mnt/LubaDub/...`, `file:///C:/Users/Admin/Yzen/...`).
4. Nothing from 2026-10-11 is on `main`.
5. Rule files contradict each other (test ownership, full-suite runs, session start, plan location).
6. Token rules depend on compliance; the builder agent has never run.
7. Tests modify the real repo: they rewrite the hook, `PLAN.md`, `package.json`, and the blueprint, move skill folders, set git config, and delete `src/`.
8. No project has been started (needs the developer; not addressed here).

New constraints from the developer: the setup is **not for hackathons** and is for **one developer**.

**Root cause of the hook bug (verified by experiment):** the hook script is correct. It fails only when the test suite rewrites `.githooks/pre-commit` with different line endings while `sh` is executing it. Finding 2's hook bug is therefore fixed by Task 2 (tests stop touching the repo) and hardened in Task 4.

## Rulings

- **Sync state is untracked.** With one developer both agents share a filesystem, so `.agents/sync/handoff.json` and `handoff.md` leave git (Task 4). `.agents/sync/session.md` stays tracked.
- **No per-task owner.** Roadmap tasks lose `Owner`; the blueprint's `team` becomes an optional `developer` string.
- **Archetype `minimal-hackathon` is renamed `minimal`.** `pitch-architect` leaves every archetype's `keep_skills`; the skill itself stays installed.
- **Committed docs use relative links.** `file://` links are for chat replies only.
- **Clean tree:** with nothing uncommitted, the baton classifies the files of the last commit; with no files at all it runs Tier 3.
- **Review gains `--spec` and `--plan` flags** beyond the delegation spec, to override auto-detection.
- **A `.mjs` path in `BATON_AGY_CMD` is run with Node.** This is how tests substitute a stub without a shell.
- **The launcher's kill grace is configurable.** The process timeout is the launch timeout plus `BATON_AGY_GRACE` seconds (default 15). Tests set it to 1 so a timeout case does not take 16 seconds.
- **Default launch timeout is 600 seconds.** The first real scout on `gemini-3.8-flash-high` took 240 seconds and 121,403 tokens, too close to the original 300.
- **An explicit `--scope` means no test-writing launch.** Naming the test file that covers a change says its tests exist. Failures are still diagnosed. Without this, every scoped check by a builder would launch Antigravity.
- **The baton creates `.agents/sync/` on demand and never counts its own state as a change,** whether or not the project git-ignores it. Found by the first real Gatekeeper run, in a project that was not a template clone.
- **Prompts ask for plain paths.** Every prompt ends with: `Reply in plain text. Refer to files by repo-relative path with forward slashes. Do not use Markdown links or absolute paths.` The first real brief spent most of its length on absolute `file://` links.

## Global Constraints

- No new npm dependencies.
- Never run `npm test`, `pytest`, `playwright test`, `unittest discover`, or a build. Verify with `npm run verify:agent -- --tier 2 --scope tests/<file>.py`.
- **Tests never touch the real repo.** Every script a test runs gets `--root <fixture>` or `{ root }`. The only real-repo reads allowed are of files the test is about (for example a doc under test).
- Fixture helpers live in `tests/repo_fixture.py`, imported as `from tests import repo_fixture`.
- Paths go into JavaScript snippets through `json.dumps`, never raw f-string interpolation (Windows backslashes).
- Write files with `\n` line endings. Temp directories use `tempfile.TemporaryDirectory(ignore_cleanup_errors=True)`.
- New optional parameters are trailing and defaulted; existing call sites keep working unless the task says otherwise.
- **Commits:** stage only the task's files and commit normally. The pre-commit hook runs the baton (about 30 seconds for a code change) and blocks a failing commit; if it blocks, fix the cause, do not bypass it. (Tasks 1 to 4 used `SKIP_VERIFY=1` while the hook was unreliable.)
- Known baseline: `test_markdown_links_are_valid` fails until Task 1; two tests in `test_e2e_baton_flow` fail until Task 2.

---

### Task 1: Portable links

- [x] **Status** (commit `6198232`)

**Files:**
- Modify: every tracked `*.md` that contains a `file://` Markdown link; `scripts/roadmap.mjs`; `AGENTS.md` (tenet 2 only); `.agents/skills/tailor-setup/SKILL.md` (section 9, last bullet)
- Test: `tests/test_docs_integrity.py`

**Decisions:**
- Two machine prefixes exist: `file:///mnt/LubaDub/Projects/Web/dual-yzentic-setup/dual-yzentic-setup` and `file:///C:/Users/Admin/Yzen/Yzentic-setup`. Each link `](<prefix><path>)` becomes a POSIX relative path from the containing file's directory to `<path>`. A bare prefix (repo root) becomes the relative path to the root. Keep a trailing `/` when the original had one. Do the conversion with a throwaway script; do not commit the script.
- `scripts/roadmap.mjs`: the Sync Protocol link becomes `[\`scripts/baton.mjs\`](../../scripts/baton.mjs)`. Remove the `batonPath` parameter and stop passing it from `scripts/init-project.mjs` and `scripts/tailor.mjs`.
- `AGENTS.md` tenet 2 becomes exactly these three lines (` / ` marks a line break):
  `2. **Navigable file and symbol references:**` / `   - In chat replies, format file paths and code symbols as clickable Markdown links using the \`file://\` scheme with the absolute path on the current machine.` / `   - In committed files, use relative Markdown links. Never commit an absolute machine path.`
- `tailor-setup/SKILL.md` section 9, "Clickable links" bullet becomes: `- **Relative links.** In files you write, link with relative Markdown paths, never absolute machine paths.`

**Tests (in `tests/test_docs_integrity.py`):**
- `test_no_absolute_file_links`: for every file from `git ls-files "*.md"`, the text contains no Markdown link whose target starts with `file://`.
- `test_markdown_links_are_valid`: add `README.md`, `docs/PLAN.md`, and `.agents/skills/tailor-setup/SKILL.md` to `files_to_check`; drop the `file:///` branch; check the path part before any `#`.
- A link in a checked file whose target does not exist: point it at the real path if one obviously exists, otherwise keep the text and drop the link. List each under Deviations.

**Verify:** `--scope tests/test_docs_integrity.py`, then `tests/test_roadmap.py`, `tests/test_rules_integrity.py`, `tests/test_root_rules.py`. All pass.

**Commit:** `fix(docs): replace absolute machine links with relative ones`

---

### Task 2: Root-aware scripts and isolated tests

- [x] **Status** (commit `27074f4`)

**Files:**
- Modify: `scripts/baton.mjs`, `scripts/init-project.mjs`, `scripts/skills-manager.mjs`, `scripts/scaffolder.mjs`, `scripts/install-hooks.mjs`
- Rename: `tests/tailor_fixture.py` to `tests/repo_fixture.py` (update its four importers)
- Rewrite: `tests/test_project_init.py`, `tests/test_e2e_project_blueprint.py`, `tests/test_skills_manager.py`, `tests/test_hooks.py`, `tests/test_scaffolder.py`, `tests/test_e2e_baton_flow.py`

**Interfaces produced:**
- Every CLI accepts `--root <path>` (default: the repo the script lives in). `--root` with no value exits 1.
- `initProject({ preset, name, desc, dev1, dev2, scaffold, root })`; `syncSkillsToArchetype(name, { root } = {})`; `installHooks({ root })` is called by `initProject` only when `<root>/.git` exists.
- `baton.mjs`: `syncPaths(root) -> { json, md }`; `main` resolves `root` once and uses it for git, the test command's `cwd`, the sync files, and `readVerifyConfig`. `readSyncState(filePath)` and `writeSyncState(state, filePath)` keep their signatures.
- `repo_fixture.make_template_repo(tmp) -> Path`: copies the real `project-blueprint.json` and `package.json`, creates a stub `SKILL.md` folder for every real skill name (active and archived) plus `_staging/`, `.agents/sync/handoff.json` (`{}`) and `handoff.md`, and `docs/PLAN.md`. It copies names, not skill contents.
- `repo_fixture.git_init(root)`: `git init`, sets a local `user.name` and `user.email`, commits everything.

**Decisions:**
- No test may reference the real repo's `src/`, `.githooks/`, `.agents/skills*`, `docs/PLAN.md`, `package.json`, `project-blueprint.json`, or `.agents/sync/` for writing. Remove every backup-and-restore `setUp`/`tearDown` and every `shutil.rmtree` on a real-repo path.
- Keep each rewritten test's assertions; only the target changes to a fixture. `test_hooks` uses a `git_init` fixture and asserts `core.hooksPath` there. `test_e2e_baton_flow`'s two CLI tests run with `--root` on a `git_init` fixture; its two snippet tests pass the path through `json.dumps`.
- This task does not change flags or names (`--dev1`, `--dev2`, `minimal-hackathon` stay); Task 3 does.

**Tests added:**
- `tests/test_repo_isolation.py::test_no_test_writes_to_the_real_repo`: scans `tests/test_*.py` and fails if any contains `rmtree(self.src_dir`, `self.root / "src"`, or `write_text(self.` on a path built from `Path(__file__)`. Keep the pattern list in the test, small and literal.
- In `tests/test_e2e_baton_flow.py`: `test_root_flag_isolates_state`: `verify --tier 1 --root <fixture>` changes the fixture's `handoff.json` and leaves the real one byte-identical.

**Verify:** each rewritten file with `--scope`, plus `tests/test_tailor_apply.py`, `tests/test_tailor_validation.py`, `tests/test_skills_sync_list.py`, `tests/test_baton_verify_config.py`. All pass. Then `git status --short` shows only your own edits.

**Commit:** `fix(tests): run every script test against a fixture repo`

---

### Task 3: Single developer, no hackathon (code)

- [x] **Status** (commit `6a5b84e`)

**Files:**
- Modify: `project-blueprint.json`, `package.json`, `scripts/roadmap.mjs`, `scripts/init-project.mjs`, `scripts/scaffolder.mjs`, `scripts/tailor.mjs`, `tests/repo_fixture.py`, `.agents/skills/tailor-setup/SKILL.md` (manifest example and field table only)
- Tests: `tests/test_roadmap.py`, `tests/test_plan_integrity.py`, `tests/test_blueprint_schema.py`, `tests/test_project_init.py`, `tests/test_e2e_project_blueprint.py`, `tests/test_scaffolder.py`, `tests/test_tailor_validation.py`, `tests/test_tailor_apply.py`
- Do **not** edit `docs/PLAN.md`, `README.md`, or other prose docs; the planner rewrites them. `tests/test_plan_integrity.py` will fail against the real `docs/PLAN.md` until then; say so in your report.

**Decisions:**
- **Blueprint:** remove `project.team`; add `"developer": "Developer"`. `project.description` becomes `Dual-agent development setup template for Claude Code and Antigravity`. Rename archetype key `minimal-hackathon` to `minimal`, its `name` to `Lean Starter (Core Essentials Only)`. Remove `pitch-architect` from all four `keep_skills`.
- **`package.json`:** `description` becomes `Dual-agent development setup for one developer: Claude Code builds, Antigravity tests`; `keywords` become `["ai-agents", "claude-code", "antigravity", "dual-agent"]`.
- **Roadmap** (`generateRoadmap({ name, desc, developer, preset, tasks })`, tasks are `{ id, title, priority, description }`): title line unchanged. The blockquote starts `**For ${developer} and the AI agents:**`. Sections, in order: `## Mission & Objective`, `## Rules for Adding Features`, `## Current Focus`, `## P0: Must-Have`, `## P1: Should-Have`, `## P2: Later`. A task renders three bullets: `Priority`, `Status: Backlog`, `Description`. No `Owner` anywhere. The rules list is exactly:
  1. `**Log it first:** Add every new idea below with a Priority and the status \`[ ] Backlog\` before any code is written.`
  2. `**Priorities:**` with sub-bullets `**\`P0\` (Must-Have):** Required for the core user journey to work.`, `**\`P1\` (Should-Have):** Improves the core journey: polish, seed data, secondary flows.`, `**\`P2\` (Later):** Parked until P0 and P1 are done.`
  3. `**One task at a time:** Finish, verify with \`npm run verify:agent\`, and commit a task before starting the next.`
  The focus line is `Active milestone: **Core scaffolding and first feature loop**`.
- **Init:** flags `--dev1`/`--dev2` are replaced by `--dev <name>` (default `Developer`). The wizard asks four questions; the fourth is the developer's name, defaulting to `git config user.name`. Preset choice 4 is `minimal`. Default name `my-app`, default description `New project`. The blueprint gets `project.developer`; any `project.team` is deleted. Placeholder tasks keep their titles and priorities, without owners.
- **Scaffolder:** `scaffoldProject({ preset, name, desc, developer = 'Developer', root })`; CLI `--dev`. In generated files replace the two-developer text: `Header` takes `{ appName, developer }` and shows one name; the card heading `Pair-Programming Status` becomes `Agent Roles` and its third row `Developer: ${developer}`; `config.py` has `DEVELOPER` in place of `DEV1`/`DEV2`; the minimal page's badge reads `Starter`, shows one `Developer:` row, and its button reads `Trigger Action`. CLI default name `MyApp`.
- **Tailor manifest:** remove `team` and roadmap `owner` from validation and rendering. `project.developer` is optional; when present it must be a non-empty string (problem path `project.developer`); when absent the roadmap uses `the developer`. Update the SKILL.md example and field table to match.

**Tests:** update each listed test file to the new names, flags, and shapes. Add: a manifest with `developer: ""` reports `project.developer`; a manifest without `developer` is valid and renders `the developer`; the rendered roadmap contains none of `Owner`, `Hackathon`, `judges`, `Demo`; `init --preset minimal-hackathon` exits 1; after `init --preset fullstack-web` the fixture has 10 active skills and `pitch-architect` is archived.

**Verify:** each listed test file with `--scope`. All pass except `tests/test_plan_integrity.py` (expected, see above).

**Commit:** `refactor: make the setup single-developer and drop hackathon framing`

---

### Task 4: A gate that gates

- [x] **Status** (commit `5e91d28`)

**Files:**
- Create: `scripts/changes.mjs`, `.gitattributes`
- Modify: `scripts/baton.mjs`, `scripts/install-hooks.mjs`, `.gitignore`, `.githooks/pre-commit` (regenerated)
- Untrack: `git rm --cached .agents/sync/handoff.json .agents/sync/handoff.md`; add `.agents/sync/.gitkeep`
- Tests: `tests/test_changes.py` (new), `tests/test_e2e_baton_flow.py`, `tests/test_hooks.py`, `tests/test_sync_schema.py`

**Interfaces produced (`scripts/changes.mjs`):**
- `isCosmeticFile(path) -> boolean`: the baton's existing Tier 1 rule, moved here.
- `getUncommittedFiles(root) -> string[]`: from `git status --porcelain --untracked-files=all`; handles renames (`a -> b` yields `b`) and quoted paths.
- `getLastCommitFiles(root) -> string[]`: from `git show --name-only --format= HEAD`; `[]` when there is no commit.
- `resolveChangeSet(root) -> { files: string[], source: 'working-tree' | 'last-commit' | 'none' }`.

**Decisions:**
- `detectExecutionTier([])` returns `3`. `verify` and `status` use `resolveChangeSet`; when the source is `last-commit` they print `[Baton] Working tree clean: classifying the last commit.`
- `verify` also reads `process.env.npm_config_tier` and `npm_config_scope` when the flags are absent, so `npm run verify:agent --tier 2 --scope x` (no `--`) works.
- **Hook:** `installHooks` writes the script with its whole body inside one function called on the last line, so `sh` parses it fully before running anything. It exports `BATON_GATEKEEPER=0` before calling the baton and no longer runs `git add` on any sync file. Regenerate `.githooks/pre-commit` with it.
- **`.gitattributes`:** exactly `* text=auto eol=lf`.
- **`.gitignore`:** add `.agents/sync/*`, `!.agents/sync/session.md`, `!.agents/sync/.gitkeep`.
- `tests/test_sync_schema.py` validates files the baton generates in a fixture (`status --root`, then `verify --tier 1 --root`), not the real ones. Allowed statuses: `idle`, `ready_for_verification`, `verification_failed`, `verified`, `gatekeeper_out_of_scope`.

**Tests:**
- `test_changes.py`: cosmetic classification; untracked files inside a new directory are listed individually; a rename reports the new path; clean tree after a code commit resolves to `last-commit` with that file; a repo with no commits resolves to `none`.
- `test_e2e_baton_flow.py`: on a clean `git_init` fixture whose last commit changed `src/app.js`, `verify` runs the test command (fixture blueprint is `initialized` with `verify.test` set to `node -e "process.exit(0)"`) and does not print `Express Lane`; with `verify.test` exiting 1, `verify` exits 1 and the fixture's `turn_count` is 1; `npm_config_tier=1` in the environment selects Tier 1.
- `test_hooks.py`: the generated hook contains `BATON_GATEKEEPER=0`, contains no `git add`, and has no CR bytes; run with `sh` in a fixture whose `scripts/baton.mjs` is a stub that **rewrites the hook file** and exits 1, the hook exits 1.

**Verify:** each listed test file with `--scope`, plus `tests/test_baton_runner.py`, `tests/test_baton_verify_config.py`, `tests/test_project_init.py`, `tests/test_tailor_apply.py`. Then `rm .githooks/pre-commit && git checkout -- .githooks/pre-commit` and confirm `git ls-files --eol .githooks/pre-commit` shows `w/lf`.

**Commit:** `fix(baton): close the clean-tree false pass, harden the hook, untrack sync state`

---

### Task 5: Antigravity launcher and scope guard

- [x] **Status** (commit `28d4aab`)

**Files:**
- Create: `scripts/agy.mjs`, `tests/stubs/agy_stub.mjs`, `tests/test_agy_launcher.py`
- Modify: `scripts/changes.mjs`, `scripts/baton.mjs` (`status` output only), `tests/test_changes.py`

**Interfaces produced:**
- `changes.mjs`: `isTestFile(path)` (under `tests/`, `test/`, or `__tests__/`, or file name matching `test_*.py`, `*_test.*`, `*.test.*`, `*.spec.*`); `isSourceFile(path)` (not test, not cosmetic, not under `.agents/`); `snapshotChanges(root) -> Map<path, sha1 | null>` over `getUncommittedFiles`; `checkScope(before, after, { allowEdits }) -> { testsWritten: string[], outOfScope: string[] }` where a path counts as changed when it is new in `after` or its hash differs.
- `agy.mjs`: `launchAgy({ job, prompt, allowEdits = false, timeoutSeconds, root }) -> { ok, response, usage, deniedActions, reason, detail, entry }` and `appendDelegation(state, entry)` (mutates `state.delegations`, keeps the last 20).

**Decisions:**
- Command line: `<cmd> --print <prompt> --output-format json --print-timeout <n>s --model <model>` plus `--mode accept-edits` when `allowEdits`. Spawn with `spawnSync`, no shell, `cwd: root`, process timeout `n + 15` seconds.
- `cmd` is `BATON_AGY_CMD` or `agy`. When it ends in `.mjs`, run `process.execPath` with it as the first argument.
- `model` is `BATON_AGY_MODEL` or `gemini-3.8-flash-high`. `timeoutSeconds` defaults to `BATON_AGY_TIMEOUT` or `300`.
- Result parsing: take the last stdout line that starts with `{` and parses as JSON. `ok` only when `status === 'SUCCESS'` and `response` is non-empty.
- `reason`: `not_installed` (spawn `ENOENT`), `timeout`, `denied` (non-empty `denied_actions`), otherwise `failed` with `detail` set to the first three non-empty output lines. `null` when `ok`.
- `entry` is `{ job, ok, reason, seconds, total_tokens, at }`. The launcher does not write files; callers persist with `appendDelegation`.
- `npm run sync:status` adds one line: `Antigravity:  <n> launches, <tokens> tokens (last 20)`.
- **Stub** (`tests/stubs/agy_stub.mjs`): appends its argv as one JSON line to `$STUB_ARGS_FILE`, then acts on `$STUB_MODE`: `success` (prints a SUCCESS JSON with response `ok` and `usage.total_tokens` 1234), `write_test` (writes `tests/generated.test.js` in cwd, then success), `write_source` (writes `src/rogue.js`, then success), `modify_source` (appends to `src/app.js`, then success), `denied` (SUCCESS JSON, empty response, one `denied_actions` entry), `garbage` (prints text, no JSON), `sleep` (waits `$STUB_SLEEP` seconds), `fail_exit` (prints an error line, exits 3).

**Tests (`test_agy_launcher.py`, each through a Node snippet with `BATON_AGY_CMD` set to the stub):** flags without and with `allowEdits`; default model and `BATON_AGY_MODEL` override; each `reason` (`not_installed` uses a nonexistent command name); `sleep` with a 1-second timeout gives `timeout`; `entry.total_tokens` is 1234 on success; `appendDelegation` caps at 20. In `test_changes.py`: each test-file pattern; `checkScope` read-only rejects any change; with `allowEdits` a new test file is in `testsWritten` and a new source file in `outOfScope`; a file already changed before and modified again is caught by its hash.

**Verify:** `--scope tests/test_agy_launcher.py`, `tests/test_changes.py`, `tests/test_e2e_baton_flow.py`.

**Commit:** `feat(agy): add the headless Antigravity launcher and scope guard`

---

### Task 6: Scout and review commands

- [x] **Status** (commit `9ad90f1`)

**Files:**
- Create: `scripts/scout.mjs`, `scripts/review.mjs`, `tests/test_scout.py`, `tests/test_review.py`
- Modify: `package.json` (`"scout": "node scripts/scout.mjs"`, `"review": "node scripts/review.mjs"`)

**Consumes:** `launchAgy`, `appendDelegation` (Task 5); `snapshotChanges`, `checkScope` (Task 5); `readSyncState`, `writeSyncState`, `syncPaths` from `baton.mjs`.

**Decisions (both):** parse `--root`; take a snapshot before the launch and run `checkScope` read-only after it; on `outOfScope` print the files and exit 1; persist the delegation entry in the fixture's `handoff.json`; print one line `[<Job>] Antigravity unavailable (<reason>).` when not `ok`.

**Scout** (`node scripts/scout.mjs [--root p] "<task>"`): no task text exits 1 with usage. The prompt names the task, `docs/PLAN.md`, and `project.source_spec` when the blueprint has one, and asks for, in at most 40 lines with no introduction: files to change, files to read first, the function or line range in each with one line of why, and existing patterns to follow. It states: read only, edit nothing, run nothing. On `ok`, write the response to `.agents/sync/scout.md` and print it. Unavailable exits 0.

**Review** (`node scripts/review.mjs [--base ref] [--spec path] [--plan path] [--root p]`): base defaults to `git merge-base HEAD main`, or `HEAD~1` when that fails or equals `HEAD`. Write `git diff <base>..HEAD` to `.agents/sync/review.diff`; an empty diff prints `[Review] Nothing to review.` and exits 0 without launching. Spec defaults to `project.source_spec`; plan defaults to the lexically last `docs/specs/*-plan.md`; either may be absent. The prompt names the diff file and those paths and asks for findings under `Critical`, `Important`, `Minor`, each with file and line, what is wrong, and why it matters, then a one-line verdict, in at most 60 lines. It states: read only, edit nothing, run nothing. On `ok`, write `.agents/sync/review.md` and print it. Unavailable exits 1.

**Tests (stub via `BATON_AGY_CMD`, `git_init` fixtures):** the recorded prompt contains the task text and the plan and spec paths, and no `--mode`; the brief file is written and printed; unavailable scout exits 0, unavailable review exits 1; `write_source` mode exits 1 and names `src/rogue.js`; review writes the diff for the given base; an empty diff launches nothing (args file absent); `--spec`/`--plan` override the defaults; a delegation entry lands in the fixture's `handoff.json`.

**Verify:** `--scope tests/test_scout.py`, `tests/test_review.py`.

**Commit:** `feat(agy): add scout and review commands`

---

### Task 7: Gatekeeper in the baton

- [x] **Status** (commit `a2eeaa9`)

**Files:**
- Create: `scripts/gatekeeper.mjs`, `tests/test_gatekeeper.py`
- Modify: `scripts/baton.mjs`

**Consumes:** Tasks 4 and 5.

**Interfaces produced (`gatekeeper.mjs`):** `shouldWriteTests({ tier, files, disabled }) -> boolean`; `writeTests({ root, state, files }) -> { result: 'ran' | 'skipped', testsWritten, outOfScope, reason }`; `diagnoseFailure({ root, state, output }) -> string | null`.

**Decisions:**
- `disabled` is true with `--no-gatekeeper` or `BATON_GATEKEEPER=0`.
- **Write:** launch when tier is 2 or 3, some file `isSourceFile`, and no file `isTestFile`. Set `state.active_agent = 'antigravity'`, write state, launch with `allowEdits: true`, set it back to `'claude'` in a `finally`. The prompt names the Gatekeeper role, the changed source files, `project.source_spec` and `docs/PLAN.md`, and `project.verify.test` when present; rules: write or update tests for the listed changes, touch test files only, run nothing, and where code contradicts the spec, test to the spec and say so in one line. Run `checkScope` whatever the launch result (a killed run may have written files).
- `state.gatekeeper = { result, tests_written }` with `result` one of `ran`, `skipped`, `not_needed`.
- Out of scope: print the files, set `status: 'gatekeeper_out_of_scope'`, exit 1 before running tests. Nothing is reverted.
- Not `ok`: print `[Baton] Gatekeeper skipped (<reason>): tests for this change are still owed.` and run the tests.
- **Diagnose:** when the test command fails on tier 2 or 3 and not disabled, write the full output to `.agents/sync/last-failure.log`, launch read-only with a prompt naming that file plus `test-results/` and `playwright-report/` when they exist, asking for at most 15 lines: failing test, file and line, expected against actual, most likely cause. On `ok` print the response under `--- Gatekeeper Diagnosis ---` in place of the distilled excerpt; otherwise print the excerpt as today.
- After every `verify`, the baton rewrites `.agents/sync/handoff.md` with: `# Agent Handoff Ticket: <task_id>`, status, tier, a `## Changes Implemented by Claude` list of changed files, and a `## Verification Report by Antigravity` section holding the diagnosis, the tests written, or `Not launched.`

**Tests (`git_init` fixtures, blueprint `initialized`, stub via `BATON_AGY_CMD`):** each row of spec section 5.1; `write_test` mode records `tests/generated.test.js` in `gatekeeper.tests_written` and the test command then runs; `write_source` and `modify_source` exit 1 with `gatekeeper_out_of_scope`, and the rogue file still exists; `active_agent` is `claude` after `success`, `fail_exit`, and `sleep` past the timeout; unavailable still runs the tests and prints the owed warning; a failing test command with stub `success` prints the diagnosis heading and not the excerpt; with stub `garbage` it prints the excerpt; `--no-gatekeeper` and `BATON_GATEKEEPER=0` launch nothing; `handoff.md` has both headings.

**Verify:** `--scope tests/test_gatekeeper.py`, `tests/test_e2e_baton_flow.py`, `tests/test_baton_runner.py`, `tests/test_sync_schema.py`.

**Commit:** `feat(baton): launch the Gatekeeper to write and diagnose tests`

---

### Task 9: Fixes from the Antigravity review

- [x] **Status** (commit `557dfae`, plus the handoff wording for launches that wrote nothing)

Findings from `npm run review` on this branch (2026-10-12), re-graded by the planner.

**Files:**
- Modify: `scripts/changes.mjs`, `scripts/gatekeeper.mjs`, `scripts/baton.mjs`, `scripts/review.mjs`
- Tests: `tests/test_changes.py`, `tests/test_gatekeeper.py`, `tests/test_review.py`

**Decisions:**
1. **Disappearing files are changes.** In `checkScope`, a path also counts as changed when it is in `before` and missing from `after` (deleted, or restored to its committed content). Such a path is always `outOfScope`, in both modes.
2. **Configuration is not source.** `isSourceFile` is also false for: any path with a segment that starts with `.` (dot-directories and dotfiles); a file named `package.json` or `project-blueprint.json` at any depth; and the lockfiles `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`, `uv.lock`, `poetry.lock`, `Cargo.lock`, `go.sum`.
3. **Scope violations are recorded.** `state.gatekeeper` gains `out_of_scope` (an array, empty when there is none), set by the write step and by the diagnosis step. The Verification Report in `handoff.md` lists those files under the line `Out of scope (not reverted):` and says `Not launched.` only when no launch happened. A violation during diagnosis keeps the status `verification_failed` (the run has already failed), and the baton prints the files to stderr under `[Baton] The Gatekeeper changed files during a read-only diagnosis:`.
4. **Review honours npm's swallowed flags.** `review.mjs` reads `npm_config_base`, `npm_config_spec`, and `npm_config_plan` when the flags are absent, and prints `[Review] Reviewing <base>..HEAD` before launching. Its prompt gains the sentence `Give line numbers from the file itself, not positions in the diff file.`, placed before the plain-paths rule, which stays last.

**Tests (each must fail before the change):**
- `test_changes.py`: an untracked file in `before` that is deleted is out of scope in both modes; a tracked file modified in `before` and restored to its committed content is out of scope; each configuration path in decision 2 is not source, while `src/app.js` and `config/settings.py` are.
- `test_gatekeeper.py`: a change set of only `package.json` and `.gitignore` at Tier 2 launches nothing; a write-step violation leaves `gatekeeper.out_of_scope == ["src/rogue.js"]` and a `handoff.md` that names the file and does not contain `Not launched.`; a diagnosis-step violation (failing test command, a test file already changed so only the diagnosis launches, stub mode `write_source`) exits 1 with status `verification_failed`, records `src/rogue.js` in `gatekeeper.out_of_scope`, lists it in `handoff.md`, and prints the stderr heading.
- `test_review.py`: `npm_config_base` in the environment selects the base when `--base` is absent, and `--base` wins when both are given; stdout contains the `Reviewing` line; the recorded prompt contains the line-number sentence and still ends with the plain-paths rule.

**Verify:** `--scope` on each of the three test files, plus `tests/test_scout.py` and `tests/test_e2e_baton_flow.py`.

**Commit:** `fix(agy): close scope-guard gaps and stop launching for configuration changes`

---

### Task 8: Enforcement hooks and documentation (planner)

- [x] **Status**

Done inline by the planner, not the builder.

- `.claude/settings.json`: a `SessionStart` hook that injects `.agents/sync/session.md`, the blueprint status, and the tier table; a `PreToolUse` hook on shell tools that blocks full-suite commands and points at the baton. Scripts: `scripts/session-context.mjs`, `scripts/guard-commands.mjs`, with tests.
- Prose: `README.md`, `docs/PLAN.md`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `docs/ai/agent-handbook.md`, `docs/ai/workflows.md`, `docs/ai/architecture.md`, both 2026-10-11 design specs. Single developer, no hackathon framing, one answer each for test ownership, full-suite runs, session start, and plan location, and the delegation commands.
- Final verification in a **fresh clone**, not only the working copy: untracked state files on disk can hide failures (found after Task 4: a link to `.agents/sync/handoff.md` breaks the link test in a clone).
- Whole-branch review with `npm run review`, one fix pass, then merge to `main`.
