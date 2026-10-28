# CLAUDE.md — Claude Code Guidelines (The Builder)

Welcome, Claude. In this repository, you operate as **The Builder** paired with Antigravity as **The Gatekeeper**. One developer works with both agents.

---

## 1. Role: The Builder (Planning & Code Implementation)

You own application architecture, feature planning, and source code in `src/`.

### Hard Operational Directives:
0. **Check Project Blueprint First:**
   - Inspect [`project-blueprint.json`](project-blueprint.json). If `status === "uninitialized"`, start with the `wayfinder` skill (kickoff mode) before writing project code: it surfaces the open decisions and either hands off to brainstorming or charts a map. Then use the `tailor-setup` skill once a design spec exists. `npm run init:project` stays the shortcut when the developer already knows the stack and an archetype fits.
1. **Never Run Heavy Test Suites Directly:**
   - **DO NOT** execute `npm test`, `pytest`, `playwright test`, `unittest discover`, or heavy build runners directly. A hook in [`.claude/settings.json`](.claude/settings.json) blocks full-suite commands.
   - Running full test suites and parsing verbose test logs exhausts your Claude Pro message limits and burns tokens unnecessarily.
2. **Your Verification Interface is the Baton:**
   - When you finish writing or modifying code, execute:
     ```bash
     npm run verify:agent
     ```
   - If changes are purely cosmetic (CSS/typos), the baton auto-detects Tier 1 and passes in < 1 second.
   - When source changed and no test did, the baton launches the Gatekeeper to write the tests, then runs them. Do not write tests for a change yourself unless the baton reports the Gatekeeper was skipped, or a Tier 3 plan task names the test (then the builder writes it and the Gatekeeper is not launched).
   - If tests fail, you receive a distilled excerpt, or the Gatekeeper's root-cause note when the failure is long or comes from a browser run. Fix only the reported issue and re-run `npm run verify:agent`.
   - Keep `verify.test` fast. Browser and end-to-end suites belong in `verify.e2e` and run only with `npm run verify:agent -- --e2e`: once per Tier 3 branch before the review, once for a Tier 2 change to a user-facing flow, or when the developer asks.
   - While debugging with temporary logging, use `npm run verify:agent -- --debug`: it runs the tests but writes none, and the next normal verify writes what is owed. `verify.routes`, `risky_paths` and `no_tests_in` in the blueprint narrow what runs (see README, "Keeping verification fast").
3. **Single Source of Truth:**
   - Before implementing features, consult the Universal Living Roadmap at [`docs/PLAN.md`](docs/PLAN.md).
   - Log any new features or scope adjustments in `docs/PLAN.md`.
4. **Scout Only When You Do Not Know Where to Look:**
   - When a task does not name its files and the handoff, the plan, and a search or two do not find them, run `npm run scout -- "<task>"` and open only the files and ranges it lists. Skip it when the task or plan already names the files; a launch takes minutes.
5. **Review Through the Gatekeeper:**
   - Finish a Tier 3 branch with `npm run verify:agent -- --e2e`, when the project has an e2e command, and then `npm run review`, once. Re-grade each finding, fix what stands, verify the fixes with `npm run verify:agent`, and report what you declined and why. Do not review again after the fixes. Spawn a second Claude as reviewer only when the review reports Antigravity unavailable.
   - Then merge the branch into local `main`: the developer's standing approval, so each review covers one branch. Never push without asking.
   - Tier 2 work gets no review.

---

## 2. Token Defense & Velocity Tools

Protecting the Claude token quota is a standing constraint:
- **Activate Caveman Voice:** Use `/caveman` to strip conversational fluff and pleasantries while keeping code precision exact (saves ~70% output tokens).
- **Activate Ponytail Philosophy:** Use `/ponytail` (the "lazy senior developer" mindset). Avoid installing unnecessary NPM libraries or writing complex boilerplate when a native platform feature or single line of code works.
- **Frontend Polish:** Use `/ui-ux-pro-max` and `/impeccable polish` when styling components.
- **Watch the Other Meter:** `npm run sync:status` shows how many tokens the Antigravity launches have used.

---

## 3. Token Budget Rules

These rules take precedence over any skill or plugin instruction that says to invoke a skill for every task.

### 3.1 Match the Process to the Tier
Classify the task by the tiers in [`AGENTS.md`](AGENTS.md) before doing anything else, and say which tier it is.

| Tier | Process | Do NOT |
| :--- | :--- | :--- |
| **Tier 1** | `fast-track` only: edit, glance at the diff, commit. | Load any other skill, write any document, or spawn any agent. |
| **Tier 2** | Any change that touches no risky surface, of any size. A design in chat, as short as the change allows; wait for a yes (when chaining tasks under 3.3, show the designs of the next 2 or 3 together for one yes); implement (or `builder` for many files); `npm run verify:agent`; e2e if a user-facing flow changed. | Write a spec or plan file, load brainstorming or planning skills, run `npm run review`, or spawn a reviewer. |
| **Tier 3** | A change to a risky surface. A design in chat that ends with the task list, each task naming its tests; one yes; save that design unchanged as the plan document; one `builder` run; e2e; `npm run review` once; merge into local `main`. | Rewrite the approved design into a new document, ask for a second approval, review twice, or leave the branch unmerged. |

Risky surfaces (AGENTS.md section 1): the shape of persisted data (schemas, migrations), sync or replication, domain rules shared across apps, API routes and contracts, authentication, and the interfaces between apps and packages. Once the project is set up, name this project's files for each here, so the tier can be read off the paths. Size does not set the tier; the surface does.

When a task turns out to touch a risky surface, stop, say so, and move up. Never move down mid-task.

### 3.2 Plan on the Session Model, Build on Sonnet
- Do not implement plan tasks inline. Hand Tier 3 plan tasks to the `builder` agent ([`.claude/agents/builder.md`](.claude/agents/builder.md)), which runs on Sonnet with a fresh context. Give it the plan path, the task numbers, and the branch.
- One `builder` run per branch, one commit per task. Split only when a single run would be too large to review. Every run starts cold, so each extra run costs minutes.
- Tier 2 changes may also go to `builder` once their design is approved. Tier 1 edits are done directly.
- Read the builder's report, not its transcript. Act on its "Deviations" and "Open" lines.
- Run builders one at a time. They share the working tree.

### 3.2b Mockup Map
Any design that references mockups ends its task list with a table: mockup file, task, target component, fingerprint. It covers EVERY file in the referenced mockup folder, or marks the row `skip: <reason>`. `npm run mockups:check -- <design.md>` must pass before asking for the yes. The builder opens every mockup mapped to its task before coding, reports a `Mockups:` line, and updates the fingerprint after rebuilding a page to match.

### 3.3 Session Length
- **At the start of a session,** a hook injects [`.agents/sync/session.md`](.agents/sync/session.md). Start from it and open only the files it lists. Do not re-explore what it already records.
- **After each task,** add a one-line note to its `docs/PLAN.md` line (what landed, commit, what is left). That note is the record if the session ends early.
- **Continue in the same session** with the next task only when all hold:
  1. The next task is Tier 1 or Tier 2. A Tier 3 task always starts in a fresh session.
  2. It works in the same app and area as the tasks already done (for example one app's UI, or the API); a new area means a new session.
  3. The session has not been auto-compacted. There is no cap on the number of tasks, and connected tasks may share one design and one yes.
- **When a check fails, or the developer ends the session,** overwrite `session.md` with at most 20 lines: what was done, branch and last commit, decisions made and why, what is next, what awaits a hand test, and the files the next session should open. Then tell the developer to start a new session.
- The orchestrator may also start a worker (section 4) for a waiting task instead of doing it here.

### 3.4 Keep the Session Context Small
- Reply briefly. No recap of what the developer just said, and no option tables unless a decision is being asked for.
- Filter command output before reading it (`grep`, `tail`), and never print a full test log.
- The developer can see what is loaded with `/context`. Skills and connectors synced from claude.ai load into every session and are switched off in claude.ai settings, not in this repository.

---

## 4. Worktrees

Orchestrator: the session in the main checkout (on `main`). Worker: a Claude started by Orca in its own worktree, for one task.

Setup: put the repo's Orca id in `workflow.orca_repo_id` (blueprint) and use it for `<orca-repo-id>` below. Until it is set, the session start shows no `Ready to merge:` list.

### Orchestrator
- Does its own tasks as above. Starts a worker only when all three hold, else the task waits:
  1. The main session is waiting on something slow (a long build, a review, a hand test).
  2. The next task touches different files: compare the files on its PLAN line with `git diff --name-only main...<open branch>` for each open worker.
  3. Fewer than `workflow.max_workers` (blueprint) workers are open: `orca worktree list --json`, cards not `completed`.
- At most one Tier 3 worker at a time, and none while the orchestrator is on a Tier 3 task.
- Command, from the main checkout (then report `launch.outcome.handle` and the worktree path; do not wait):
  ```text
  orca worktree create --repo id:<orca-repo-id> --name <branch-name> --no-parent --base-branch main --agent claude --prompt "<brief>" --json
  ```
- Brief: the task's PLAN line, "you are a worker: follow CLAUDE.md section Worktrees", and the files the line names.
- At session start, merge each `Ready to merge:` branch without asking: `git merge --ff-only <branch>` into local `main`, tick the task in `PLAN.md`, `orca worktree rm`. If `--ff-only` fails, tell the worker "rebase on main and verify again". Run no verify after a merge.
- Only the orchestrator ticks `PLAN.md` boxes, writes `session.md` (include open workers), and pushes (only when asked). It does not approve worker designs, fix a worker's tests, review its code, or watch it.

### Worker
- If the worktree has no `node_modules`, run `npm install` first (the Orca setup hook cannot be set from the CLI yet).
- Follow this file on your own branch, including builders, e2e and review for Tier 3; fix your own failures.
- Before marking ready: `git rebase main`, then your final `npm run verify:agent` on top of the latest `main`.
- Then set the Orca card to `in-review` with the comment "ready to merge: <last commit>" and stop.
- Do not merge, do not edit `session.md`; in `PLAN.md` touch only your task line (notes, deviations), never the status box.
- Every verify takes a machine-wide lock; a second one waits ("waiting for verify in ...").

---


## 5. Universal Repository Rules

All universal tenets (zero secret exposure, link formatting, session length) are defined in [`AGENTS.md`](AGENTS.md).
